"""Local-only Noark 5 experience matches, assessment events and optional policy.

The shipped catalogue is advisory, never an XSD validation or test result.
Work assessments are append-only events with atomic whole-file replacement.
A local override is a separate file outside the repository and Source.
"""
from __future__ import annotations
from datetime import datetime, timezone
from pathlib import Path
import json
import os
import tempfile
import uuid

CASES = Path(__file__).resolve().parents[1] / 'config/noark5/experience/known_cases_v1.json'
SCHEMA_VERSION = '1.0'
MAX_FILE_BYTES = 3_000_000
STATUSES = ('reviewed_equivalent', 'needs_follow_up', 'not_accepted')


def local_catalog_path() -> Path:
    """A user-local area independent of any extraction or job."""
    base = os.environ.get('LOCALAPPDATA')
    if base:
        return Path(base) / 'DataWorkflowManager' / 'noark5' / 'experience' / 'local_practice.json'
    return Path.home() / '.local' / 'share' / 'DataWorkflowManager' / 'noark5' / 'experience' / 'local_practice.json'


def _read(path: Path, kind: str, key: str) -> dict:
    if not path.is_file():
        return {'schema_version': SCHEMA_VERSION, 'catalog_type': kind, key: []}
    if path.stat().st_size > MAX_FILE_BYTES:
        raise ValueError('Erfaringsfilen er for stor; ingen endringer er gjort')
    data = json.loads(path.read_text(encoding='utf8'))
    if data.get('schema_version') != SCHEMA_VERSION or data.get('catalog_type') != kind or not isinstance(data.get(key), list):
        raise ValueError('Ukjent erfaringsfilformat; ingen endringer er gjort')
    return data


def _write(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix='.experience-', suffix='.tmp', dir=path.parent)
    try:
        with os.fdopen(fd, 'w', encoding='utf8') as handle:
            json.dump(data, handle, ensure_ascii=False, indent=2)
            handle.write('\n')
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def known_cases() -> tuple[dict, ...]:
    return tuple(_read(CASES, 'dwm_noark5_experiences', 'cases')['cases'])


def find_known_cases(*, metadata_id: str, field: str, noark_version: str | None, observed_values: dict) -> tuple[dict, ...]:
    """Only compare against the *extraction's confirmed* version.

    Caller must pass None when version confidence is not confirmed.
    The saved test's *historical comparison version* is NOT this argument.
    """
    if not noark_version:
        return ()
    results = []
    local = _read(local_catalog_path(), 'dwm_noark5_local_practice', 'overrides')
    overrides = {x.get('case_id'): x for x in local['overrides'] if isinstance(x,dict)}
    for record in known_cases():
        if (record['metadata_id'] != metadata_id or record['field'] != field
            or noark_version not in record['noark_versions'] or record['observed_value'] not in observed_values):
            continue
        if record['match_type'] != 'exact':
            continue
        entry = dict(record)
        override = overrides.get(record['case_id'])
        if override:
            entry['suggested_note'] = override['suggested_note']
            entry['local_practice'] = True
        entry['observed_count'] = observed_values[record['observed_value']]
        results.append(entry)
    return tuple(results)


def assessment_path(work: Path) -> Path:
    return Path(work) / 'noark5_evidence' / 'experience_assessments.json'


def _check_work(work: Path, source: Path | None = None) -> Path:
    work = Path(work).resolve()
    if not work.is_dir() or not (work/'job.json').is_file():
        raise ValueError('Gyldig jobb-Work med job.json er nødvendig')
    if source is not None:
        source = Path(source).resolve()
        if work == source or source in work.parents or work in source.parents:
            raise ValueError('Work må være adskilt fra Source')
    return work


def save_assessment(work: Path, *, case_id: str, noark_version: str, observed_value: str,
                    observed_count: int, status: str, note: str,
                    test_id: str, source: Path | None = None,
                    timestamp: str | None = None) -> Path:
    """Append an independently identified human assessment, never modify observations.

    Deduplication is not applied to assessment events; changed opinions remain
    history. A source file path is intentionally not copied to the ledger.
    """
    work = _check_work(work,source)
    record = next((c for c in known_cases() if c['case_id']==case_id),None)
    if record is None or noark_version not in record['noark_versions'] or observed_value != record['observed_value']:
        raise ValueError('Erfaringssaken samsvarer ikke med verifisert versjon og verdi')
    if status not in STATUSES or not note.strip() or len(note)>10000:
        raise ValueError('Kontrolløren må velge vurdering og angi en merknad (maks 10 000 tegn)')
    if not isinstance(observed_count,int) or isinstance(observed_count,bool) or observed_count<1:
        raise ValueError('Ugyldig observasjonstall')
    if not test_id.strip():
        raise ValueError('Test-ID mangler')
    target = assessment_path(work)
    data = _read(target,'dwm_noark5_assessments','events')
    data['events'].append({
        'event_id':str(uuid.uuid4()),'event_type':'human_assessment',
        'recorded_at': timestamp or datetime.now(timezone.utc).isoformat(timespec='seconds'),
        'case_id':case_id,'noark_version':noark_version,'metadata_id':record['metadata_id'],
        'test_id':test_id,'observed_value':observed_value,'observed_count':observed_count,
        'decision':status,'note':note.strip(),'assessment_scope':'job_work',
        'automatic_test_status_modified':False,
    })
    _write(target,data)
    return target


def save_local_practice(*, case_id: str, note: str, path: Path | None = None) -> Path:
    """Persist explicitly chosen reusable local wording, never source evidence."""
    if case_id not in {x['case_id'] for x in known_cases()}:
        raise ValueError('Ukjent erfaringssak')
    if not note.strip() or len(note)>10000:
        raise ValueError('Tom eller for lang merknad')
    path = Path(path) if path is not None else local_catalog_path()
    data = _read(path,'dwm_noark5_local_practice','overrides')
    data['overrides'] = [x for x in data['overrides'] if x.get('case_id')!=case_id]
    data['overrides'].append({'case_id':case_id,'suggested_note':note.strip(),
                             'updated_at':datetime.now(timezone.utc).isoformat(timespec='seconds')})
    _write(path,data)
    return path
