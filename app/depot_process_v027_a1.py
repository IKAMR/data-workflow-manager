"""Read-only depot process projection from the existing DWM Work evidence.

Never writes to Source, Work, decision journals or job lists. A status in this
projection is not a substitute for a technical test, a professional assessment,
or formal approval. Large depot reports use the existing A17 streaming reader.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import Path
from typing import Any, Iterable

MAX_SMALL_REPORT = 12_000_000
MAX_METADATA = 2_000_000
MAX_REPORT_CANDIDATES = 256
DEPOT_STATUS = {
    'accepted': 'Akseptert (faglig vurdering)',
    'accepted_with_deviation': 'Akseptert med avvik (faglig vurdering)',
    'requires_clarification': 'Krever avklaring',
    'new_extraction_required': 'Nytt uttrekk kreves',
}
EVIDENCE_STATUS = {
    'sources_linked_needs_review': 'Kilder koblet – krever faglig vurdering',
    'internal_only_needs_review': 'Kun intern evidens – krever faglig vurdering',
    'missing_expected_sources': 'Mangler forventet evidens',
}


@dataclass(frozen=True)
class DepotProcessRow:
    job_uid: str
    job_id: str
    job_name: str
    scope: str
    system_id: str
    title: str
    technical: str
    evidence: str
    findings: str
    assessment: str
    basis: str
    warnings: tuple[str, ...]
    work: Path
    report_path: Path | None
    archive_part_count: int | None = None
    run_status: str = 'Ukjent'

    @property
    def key(self) -> tuple[str, str]:
        return self.job_uid, self.system_id


def _safe_path(root: Path, relative: str) -> Path:
    """Resolve the Work boundary once; reject symlinks *inside* Work.

    On Windows a parent of a legitimate Work path may be a junction/reparse
    point (for example a redirected temporary directory). Comparing the
    resolved candidate to the unresolved root incorrectly reported the file as
    outside Work. Both sides must use the same canonical root identity.
    """
    if (not isinstance(relative, str) or not relative or '\\' in relative
            or relative.startswith('/') or '//' in relative or ':' in relative):
        raise ValueError('Utrygg Work-relativ evidenssti')
    parts = relative.split('/')
    if any(part in ('', '.', '..') for part in parts):
        raise ValueError('Utrygg Work-relativ evidenssti')
    requested_root = Path(root)
    if requested_root.is_symlink() or not requested_root.is_dir():
        raise ValueError('Ugyldig Work-katalog')
    canonical_root = requested_root.resolve(strict=True)
    path = canonical_root
    for part in parts:
        path = path / part
        if path.is_symlink():
            raise ValueError('Symbolsk lenke i Work-evidenssti')
    if not path.resolve(strict=False).is_relative_to(canonical_root):
        raise ValueError('Evidens utenfor Work')
    return path


def _json(work: Path, relative: str) -> dict | None:
    path = _safe_path(work, relative)
    if not path.is_file():
        return None
    if path.stat().st_size > MAX_METADATA:
        raise ValueError('For stor evidensmetadata: ' + relative)
    data = json.loads(path.read_text(encoding='utf-8-sig'))
    if not isinstance(data, dict):
        raise ValueError('Evidensmetadata må være et JSON-objekt')
    return data


def _hash(path: Path) -> str:
    result = sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            result.update(chunk)
    return result.hexdigest()


def _report_candidates(snapshot: Any, root: Path) -> tuple[Path, ...]:
    """Inspect only known report locations, never walk Source or DOKUMENT."""
    paths: list[Path] = []
    stored = getattr(snapshot.results, 'depot_report_path', None)
    if stored is not None:
        paths.append(Path(stored))
    for artifact in getattr(snapshot.results, 'artifacts', ()):
        if getattr(artifact, 'title', None) == 'depot_validation_report.json':
            paths.append(Path(artifact.path))
    folder = root / 'noark5_reports' / 'depot_validation'
    if folder.is_dir() and not folder.is_symlink():
        children = sorted((p for p in folder.iterdir() if p.is_dir() and not p.is_symlink()),
                          key=lambda p: (p.stat().st_mtime_ns, p.name), reverse=True)[:MAX_REPORT_CANDIDATES]
        for child in children:
            paths.append(child / 'depot_validation_report.json')
    unique: dict[str, Path] = {}
    for path in paths:
        try:
            candidate = path.resolve(strict=True)
            if (path.is_symlink() or not candidate.is_file()
                    or not candidate.is_relative_to(root)
                    or candidate.name != 'depot_validation_report.json'):
                continue
            unique[str(candidate)] = candidate
        except (OSError, ValueError, RuntimeError):
            continue
    return tuple(sorted(unique.values(), key=lambda p: (p.stat().st_mtime_ns, str(p)), reverse=True))


def _load_report(snapshot: Any, root: Path) -> tuple[Path | None, dict | None, str, str]:
    """Return selected report and a complete or explicitly failed projection."""
    candidates = _report_candidates(snapshot, root)
    if not candidates:
        return None, None, '', 'Ingen original depotrapport funnet i kjent Work-plassering'
    errors = []
    for report in candidates:
        try:
            before = report.stat()
            if before.st_size <= MAX_SMALL_REPORT:
                # Hash exactly the bytes parsed, not a separate file version.
                raw = report.read_bytes()
                if len(raw) != before.st_size:
                    raise ValueError('Depotrapport endret under lesing')
                value = json.loads(raw.decode('utf-8-sig'))
                if not isinstance(value, dict) or value.get('report_type') != 'noark5_depot_validation':
                    raise ValueError('Ukjent depotrapportformat')
                if (not isinstance(value.get('archive_parts'), list)
                        or not isinstance(value.get('summary'), dict)
                        or not isinstance(value.get('technical_validation'), dict)):
                    raise ValueError('Depotrapport mangler obligatoriske arkivdel- eller kontrollseksjoner')
                digest = sha256(raw).hexdigest()
            else:
                from noark5_workflow.reporting.qa_depot_stream_v023_a17 import project_depot_report
                value, digest = project_depot_report(report)
            after = report.stat()
            if ((before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns) !=
                    (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns)):
                raise ValueError('Depotrapport endret under lesing')
            # Never silently treat an older, valid report as the latest run.
            note = ('Nyere depotrapport kunne ikke leses; viser eldre rapport. '
                    + ' | '.join(errors[:2])) if errors else ''
            return report, value, digest, note
        except (OSError, UnicodeError, ValueError, TypeError, OverflowError) as exc:
            errors.append(str(report) + ': ' + str(exc))
    return candidates[0], None, '', 'Ingen lesbar depotrapport: ' + ' | '.join(errors[:2])


def _run_state(root: Path, uid: str) -> tuple[str, tuple[str, ...]]:
    """Keep execution status separate from the last saved depot report."""
    try:
        data = _json(root, 'job-state.json')
        if data is None:
            return 'Ukjent', ('Lagret Work-jobbstatus finnes ikke',)
        if (data.get('file_type') != 'dwm-work-job-state'
                or data.get('job_uid') != uid
                or not isinstance(data.get('state'), dict)):
            raise ValueError('Jobbstatus gjelder feil Work eller ukjent format')
        status = data['state'].get('status')
        if not isinstance(status, str) or not status:
            raise ValueError('Work-jobbstatus mangler gyldig status')
        return status, ()
    except (OSError, UnicodeError, ValueError, TypeError) as exc:
        return 'Ukjent', ('Jobbstatus krever kontroll: ' + str(exc),)


def _audit(root: Path, uid: str) -> tuple[str, str, tuple[str, ...]]:
    try:
        data = _json(root, 'noark5_evidence/evidence-audit.json')
        if data is None:
            return 'A230 ikke dokumentert', '', ()
        if data.get('model_id') != 'dwm.noark5.evidence-audit.a7.v1' or data.get('job_uid') != uid:
            raise ValueError('A230-rapport gjelder feil jobb eller ukjent format')
        state = str(data.get('status') or '')
        if state not in EVIDENCE_STATUS:
            raise ValueError('Ukjent A230-evidensstatus')
        missing = data.get('missing_source_families') or []
        if not isinstance(missing, list) or any(not isinstance(x, str) for x in missing):
            raise ValueError('Ugyldig liste over manglende evidenskilder')
        label = EVIDENCE_STATUS[state]
        if missing:
            label += ': ' + ', '.join(missing)
        if state == 'missing_expected_sources' and not missing:
            raise ValueError('A230 varsler manglende evidens uten kildenavn')
        return label, _hash(_safe_path(root, 'noark5_evidence/evidence-audit.json')), ()
    except (OSError, UnicodeError, ValueError, TypeError) as exc:
        return 'A230 krever kontroll', '', (str(exc),)


def _a260(root: Path, uid: str, report_sha: str, audit_sha: str) -> tuple[str, tuple[str, ...]]:
    """Count only a fully verified A260 export, never a bounded HTML preview.

    The SHA check is intentionally an expensive background operation; callers
    must not invoke this on the Qt UI thread for a large Work.
    """
    try:
        basis = _json(root, 'noark5_evidence/qa-basis-draft.json')
        if basis is None:
            return 'A260 ikke dokumentert', ()
        if (basis.get('model_id') != 'dwm.noark5.qa-basis.draft.a7.v1'
                or basis.get('job_uid') != uid
                or basis.get('automatic_approval') is not False):
            raise ValueError('A260-grunnlaget har ukjent identitet eller format')
        if not report_sha or not audit_sha:
            raise ValueError('A260 kan ikke bindes til verifisert rapport og A230')
        if basis.get('evidence_audit_sha256') != audit_sha:
            raise ValueError('A260 viser til en annen A230-evidensrevisjon')
        manifest_rel = basis.get('export_manifest')
        manifest = _json(root, manifest_rel)
        if (manifest is None or manifest.get('model_id') != 'dwm.noark5.a260.complete-findings.a6.v1'
                or manifest.get('job_uid') != uid
                or manifest.get('depot_report_sha256') != report_sha):
            raise ValueError('A260-manifestet gjelder en annen depotrapport')
        files = manifest.get('files') or {}
        refs = basis.get('exports') or {}
        for name, key in (('funn.jsonl', 'jsonl'), ('funn.csv', 'csv')):
            relative = refs.get(key)
            path = _safe_path(root, relative)
            if (path.parent != _safe_path(root, manifest_rel).parent or path.name != name
                    or not path.is_file() or not isinstance(files.get(name), dict)
                    or path.stat().st_size != files[name].get('bytes')
                    or _hash(path) != files[name].get('sha256')):
                raise ValueError('A260-funnregister er endret eller mangler: ' + name)
        summary = manifest.get('summary') or {}
        base_summary = basis.get('findings') or {}
        total = summary.get('total')
        if (type(total) is not int or total < 0 or base_summary.get('total') != total
                or summary.get('automatic_approval') is not False):
            raise ValueError('A260-funntall er ufullstendig eller avvikende')
        return f'{total} (komplett A260-register)', ()
    except (OSError, ValueError, TypeError, UnicodeError) as exc:
        return 'A260 krever kontroll', (str(exc),)


def _depot_assessment(report: Path | None) -> tuple[str, tuple[str, ...]]:
    if report is None:
        return 'Ikke vurdert', ()
    try:
        from noark5_workflow.analysis.depot_assessment import load_depot_assessment
        data = load_depot_assessment(report)
        if data is None:
            return 'Ikke vurdert', ()
        current = data.get('current') or {}
        status = current.get('status')
        if status not in DEPOT_STATUS:
            raise ValueError('Ukjent depotvurderingsstatus')
        return DEPOT_STATUS[status], ()
    except (OSError, UnicodeError, ValueError, TypeError) as exc:
        return 'Tidligere vurdering – kontroller rapportrevisjon', (str(exc),)


def _part_decisions(report: Path | None) -> tuple[dict, tuple[str, ...]]:
    if report is None:
        return {}, ()
    try:
        from app.depot_review_v019_a2 import load_part_decisions
        data = load_part_decisions(report)
        return (data.get('parts') or {}) if data else {}, ()
    except (OSError, UnicodeError, ValueError, TypeError) as exc:
        return {}, ('Arkivdelvurderinger krever kontroll: ' + str(exc),)


def build_depot_process_rows(snapshots: Iterable[Any]) -> tuple[DepotProcessRow, ...]:
    """Create a read-only per-extraction / per-native-part operator overview.

    All result and evidence sources remain separate. Missing/unreadable data
    stays unknown; it is never converted to zero findings or approval.
    """
    rows: list[DepotProcessRow] = []
    seen: set[str] = set()
    for shot in snapshots:
        job = shot.job
        root = Path(job.work)
        uid = str(job.job_uid)
        if uid in seen:
            continue
        seen.add(uid)
        warnings: list[str] = []
        try:
            root = root.resolve(strict=True)
            if not root.is_dir() or root.is_symlink():
                raise ValueError('Work er ikke en tilgjengelig, sikker katalog')
            actual = _json(root, 'job.json')
            if (not actual or actual.get('file_type') != 'dwm-work-job'
                    or actual.get('job_uid') != uid):
                raise ValueError('Work-identitet er ikke verifisert mot valgt jobb')
            report, model, digest, report_error = _load_report(shot, root)
            if report_error:
                warnings.append(report_error)
            run_status, run_warnings = _run_state(root, uid)
            warnings.extend(run_warnings)
            evidence, audit_sha, audit_warnings = _audit(root, uid)
            warnings.extend(audit_warnings)
            findings, qa_warnings = _a260(root, uid, digest, audit_sha)
            warnings.extend(qa_warnings)
            professional, professional_warnings = (_depot_assessment(report) if model
                                                  else ('Ikke verifisert', ()))
            warnings.extend(professional_warnings)
            parts, parts_warnings = (_part_decisions(report) if model else ({}, ()))
            warnings.extend(parts_warnings)
            archive_parts = (model or {}).get('archive_parts') or []
            if not isinstance(archive_parts, list):
                raise ValueError('Ukjent arkivdelstruktur i depotrapport')
            technical = str(((model or {}).get('technical_validation') or {}).get('status') or 'Ukjent')
            basis = ('Depotrapport verifisert (strømmelesing)' if report and model and
                     report.stat().st_size > MAX_SMALL_REPORT else
                     'Depotrapport lest' if model else 'Depotrapport mangler / kan ikke leses')
            rows.append(DepotProcessRow(
                uid, str(job.job_id), str(job.name), 'uttrekk', '', 'Hele uttrekket',
                technical, evidence, findings, professional, basis, tuple(warnings),
                root, report, len(archive_parts) if model else None,
                run_status=run_status,
            ))
            counts: dict[str, int] = {}
            for part in archive_parts:
                if not isinstance(part, dict):
                    continue
                native = str((part.get('archive_part') or {}).get('system_id') or '')
                counts[native] = counts.get(native, 0) + 1
            for index, part in enumerate(archive_parts, 1):
                if not isinstance(part, dict):
                    continue
                meta = part.get('archive_part') or {}
                native = str(meta.get('system_id') or '')
                unique = bool(native and counts.get(native) == 1)
                entry = (parts.get(native) or {}).get('current') or {} if unique else {}
                current = str(entry.get('status') or '')
                part_status = (
                    'Kan ikke vurderes: system-ID mangler/duplisert' if not unique else
                    'Tidligere arkivdelvurdering – kontroller rapportrevisjon' if parts_warnings else
                    DEPOT_STATUS.get(current, 'Ikke vurdert')
                )
                part_warnings = tuple(warnings + ([] if unique else ['Arkivdelen mangler en entydig native system-ID']))
                rows.append(DepotProcessRow(
                    uid, str(job.job_id), str(job.name), 'arkivdel', native if unique else f'ukjent:{index}',
                    str(meta.get('title') or native or f'Arkivdel {index}'),
                    str(part.get('status') or 'Ukjent'), 'A230 på uttrekksnivå',
                    'Antall per arkivdel ikke dokumentert', part_status,
                    'Arkivdel i original depotrapport', part_warnings, root, report,
                    run_status=run_status,
                ))
        except (OSError, ValueError, TypeError, UnicodeError) as exc:
            rows.append(DepotProcessRow(
                uid, str(job.job_id), str(job.name), 'uttrekk', '', 'Hele uttrekket',
                'Ukjent', 'Ukjent', 'Ukjent', 'Ikke verifisert',
                'Work / rapport krever kontroll', (str(exc),), root, None,
            ))
    return tuple(rows)
