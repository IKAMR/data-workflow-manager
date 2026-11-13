"""Auditable, opt-in context for canonical Noark 5 result snapshots.

The a1 canonical JSON contract is immutable in a4. This companion index links
human assessments and external evidence to its hash without changing historical
results or promoting imported evidence to master observations.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path, PureWindowsPath
import tempfile
from datetime import datetime, timezone
from typing import Any

MODEL = 'noark5.canonical-context.v1'
OUT = 'noark5_evidence/canonical-context.json'
MAX_INPUT = 30_000_000
MAX_EVENTS = 50_000
MAX_EXTERNAL = 500

class ContextError(ValueError):
    pass

def _sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()

def _inside(work: Path, value: str | Path) -> tuple[Path, str]:
    raw = str(value)
    if PureWindowsPath(raw).is_absolute() and os.name != 'nt':
        raise ContextError('Windows-absoluttsti kan ikke leses paa denne plattformen')
    candidate = Path(value)
    candidate = (candidate if candidate.is_absolute() else work / candidate).resolve()
    root = work.resolve()
    try:
        rel = candidate.relative_to(root).as_posix()
    except ValueError as exc:
        raise ContextError('Kilden ligger utenfor valgt Work') from exc
    if not candidate.is_file() or candidate.stat().st_size > MAX_INPUT:
        raise ContextError(f'Mangler eller for stor kildefil i Work: {rel}')
    return candidate, rel

def _json(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding='utf-8-sig'))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ContextError(f'Kan ikke lese JSON {path.name}: {exc}') from exc
    if not isinstance(value, dict):
        raise ContextError('JSON-rot maa vaere objekt')
    return value

def _fingerprint(path: Path, rel: str) -> dict:
    return {'work_relative_path': rel, 'sha256': _sha(path), 'bytes': path.stat().st_size}

def _assessment_events(path: Path, canonical: dict) -> tuple[list[dict], int]:
    doc = _json(path)
    if doc.get('schema_version') != '1.0' or doc.get('catalog_type') != 'dwm_noark5_assessments' or not isinstance(doc.get('events'), list):
        raise ContextError('Ukjent format for faglige vurderinger')
    if len(doc['events']) > MAX_EVENTS:
        raise ContextError('For mange vurderinger')
    known = {(str(x.get('test_id')), str(x.get('metadata_id'))) for x in canonical['observations'] if isinstance(x, dict)}
    tests = {str(x.get('test_id')) for x in canonical['observations'] if isinstance(x, dict)}
    seen = set()
    result = []
    for event in doc['events']:
        if not isinstance(event, dict) or event.get('event_type') != 'human_assessment':
            raise ContextError('Ukjent hendelse i vurderingsfil')
        uid = str(event.get('event_id') or '')
        if not uid or uid in seen:
            raise ContextError('Manglende/duplisert vurderings-ID')
        seen.add(uid)
        test_id = str(event.get('test_id') or '')
        metadata_id = str(event.get('metadata_id') or '') or None
        # Test-ID alone is NOT a reliable assertion that M300 was calculated
        # in that particular canonical observation. Preserve honest link state.
        match = 'test_id_only' if test_id in tests else 'unlinked'
        if (test_id, metadata_id or 'None') in known and metadata_id:
            match = 'test_and_metadata_id'
        result.append({
            'event_id': uid, 'test_id': test_id or None, 'metadata_id': metadata_id,
            'case_id': event.get('case_id'), 'recorded_at': event.get('recorded_at'),
            'decision': event.get('decision'), 'note': event.get('note'),
            'observed_value': event.get('observed_value'), 'observed_count': event.get('observed_count'),
            'noark_version': event.get('noark_version'), 'link_status': match,
            'automatic_test_status_modified': False,
        })
    return result, len(result)

def build_context(work: str | Path, *, assessments_path: str | Path | None = None,
                  external_paths: tuple[str | Path, ...] = (), write: bool = True,
                  generated_at: str | None = None) -> dict[str, Any]:
    """Build a separate, explicit and hashed extension to canonical-results.json.

    External files are recorded as opaque evidence files, NOT parsed as results:
    a future adapter must formally support the source format before promoting
    it to an observation. No recursive discovery or implicit provenance claims.
    """
    from noark5_workflow.analysis.canonical_results import _validate_work
    root, identity = _validate_work(Path(work))
    canonical_path, canonical_rel = _inside(root, 'noark5_evidence/canonical-results.json')
    canonical = _json(canonical_path)
    if canonical.get('model_id') != 'noark5.canonical-results.v1' or not isinstance(canonical.get('observations'), list):
        raise ContextError('Ugyldig kanonisk resultatindeks')
    if canonical.get('extraction', {}).get('stable_id') != identity['job_uid']:
        raise ContextError('Kanonisk resultatindeks tilhoerer en annen jobb')
    if not assessments_path and not external_paths:
        raise ContextError('Velg minst en vurderingsfil eller ekstern evidensfil')
    seen = {canonical_rel}
    assessments = []
    assessment_ref = None
    if assessments_path is not None:
        path, rel = _inside(root, assessments_path)
        if rel in seen:
            raise ContextError('Samme fil er valgt flere ganger')
        seen.add(rel)
        assessments, _ = _assessment_events(path, canonical)
        assessment_ref = _fingerprint(path, rel)
    external = []
    if len(external_paths) > MAX_EXTERNAL:
        raise ContextError('For mange eksterne filer')
    for name in external_paths:
        path, rel = _inside(root, name)
        if rel in seen or rel == OUT:
            raise ContextError('Duplisert eller ugyldig ekstern evidens')
        seen.add(rel)
        external.append({'source_kind': 'external_opaque', 'evidence': _fingerprint(path, rel),
                         'interpretation': 'not_parsed', 'authoritative_internal_master': False})
    document = {
        'model_id': MODEL, 'schema_version': '1.0',
        'generated_at': generated_at or datetime.now(timezone.utc).isoformat(timespec='seconds'),
        'extraction_stable_id': identity['job_uid'],
        'canonical_reference': _fingerprint(canonical_path, canonical_rel),
        'assessment_source': assessment_ref, 'assessments': assessments,
        'external_evidence': external,
        'summary': {'human_assessments': len(assessments), 'external_unparsed_files': len(external),
                    'unlinked_assessments': sum(x['link_status'] == 'unlinked' for x in assessments),
                    'is_approval': False},
        'limitations': [
            'Vurderinger endrer aldri teknisk kontrollstatus',
            'Kobling paa test-ID alene er ikke dokumentasjon paa konkret XML-forekomst',
            'Eksterne filer beholdes som opak evidens inntil formatadapter er godkjent',
            'Endret kanonisk fil krever ny kontekstindeks med ny SHA-256',
        ],
    }
    if write:
        target = root / OUT
        if target.parent.resolve() != (root / 'noark5_evidence').resolve():
            raise ContextError('Ugyldig utmappe')
        if target.is_symlink():
            raise ContextError('Utfilen er en symbolsk lenke')
        fd, tmp = tempfile.mkstemp(prefix='.canonical-context-', suffix='.tmp', dir=target.parent)
        try:
            with os.fdopen(fd, 'w', encoding='utf-8') as f:
                json.dump(document, f, ensure_ascii=False, indent=2, allow_nan=False)
                f.write('\n')
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp, target)
        finally:
            if os.path.exists(tmp):
                os.unlink(tmp)
    return document
