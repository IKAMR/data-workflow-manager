"""Read-only, job-bound progress for the DWM depot production line.

A stage is a projection of saved job state or Work evidence, NOT a new workflow
state machine. Opening an area never marks a stage done or writes to Work.
Historical events are read only from bounded, already-existing Work metadata.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable
from uuid import UUID

from app.production_review_v020_a4 import ProductionEvidence, inspect_production_evidence

STAGE_NAMES = (
    ('ingest', 'Ingest'),
    ('antivirus', 'Antiviruskontroll'),
    ('workspace', 'Til arbeidsomr\u00e5de'),
    ('control', 'Kontroll'),
    ('report', 'Rapportering'),
    ('preserve', 'Bevaring'),
    ('crm', 'Mot intern CRM'),
    ('access', 'Innsyn'),
)
STAGE_KEYS = frozenset(key for key, _ in STAGE_NAMES)
NAVIGABLE_KEYS = frozenset(('ingest', 'antivirus', 'workspace', 'control', 'report', 'preserve'))
_RUN_ID = re.compile(r'^\d{8}T\d{6}Z-[0-9a-f]{8}$')
_JOB_ID = re.compile(r'^[A-Za-z0-9_-]{1,80}$')
MAX_HISTORY = 35


@dataclass(frozen=True)
class StageProgress:
    key: str
    title: str
    state: str
    label: str
    detail: str


@dataclass(frozen=True)
class StageEvent:
    at: str
    stage: str
    kind: str
    detail: str


@dataclass(frozen=True)
class PipelineProgress:
    job_id: str
    job_name: str
    job_status: str
    operation_percent: int
    completed_operations: int
    operation_count: int
    technical_status: str
    professional_status: str
    work: Path | None
    stages: tuple[StageProgress, ...]
    events: tuple[StageEvent, ...]
    notes: tuple[str, ...]

    @property
    def has_job(self):
        return bool(self.job_id)


def stable_job_key(job_id: str, *, job_uid: str = '', job_list_path: str = '') -> str:
    """Bound the resume marker to the exact job, not reusable JOB-001 alone.

    Unprovisioned jobs need a saved job-list path; otherwise resume is disabled.
    """
    job_id = str(job_id or '').strip()
    if not job_id:
        return ''
    try:
        uid = str(UUID(str(job_uid))) if job_uid else ''
    except (TypeError, ValueError, AttributeError):
        uid = ''
    if uid:
        identity = 'work:' + uid
    elif job_list_path:
        identity = 'joblist:' + str(Path(job_list_path).absolute()) + '\x00' + job_id
    else:
        return ''
    return hashlib.sha256(identity.encode('utf-8')).hexdigest()


def resume_section(*, current_key: str, stored_key: str, stored_section: str) -> str:
    """A stale marker must never resume a different job or a planned stage."""
    if current_key and stored_key == current_key and stored_section in NAVIGABLE_KEYS:
        return stored_section
    return ''


def _clean(value, limit=160) -> str:
    return ' '.join(str(value or '').split())[:limit]


def _read_object(path: Path, *, size_limit: int = 65_536):
    if not path.is_file() or path.is_symlink() or path.stat().st_size > size_limit:
        return None
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, UnicodeError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def _work_is_safe(work: Path | None) -> bool:
    try:
        return bool(work and work.is_dir() and not work.is_symlink()
                    and work.resolve(strict=True).is_dir())
    except (OSError, RuntimeError, ValueError):
        return False


def _tail_events(path: Path, *, limit_bytes: int = 1_500_000) -> list[dict]:
    """Read a tail of one known event file; never traverse/source-scan a tree."""
    if not path.is_file() or path.is_symlink():
        return []
    with path.open('rb') as handle:
        size = handle.seek(0, 2)
        start = max(0, size - limit_bytes)
        handle.seek(start)
        block = handle.read(limit_bytes)
    if start:
        block = block.partition(b'\n')[2]
    result = []
    for raw in block.splitlines()[-200:]:
        if not raw or len(raw) > 65_536:
            continue
        try:
            data = json.loads(raw.decode('utf-8'))
        except (ValueError, UnicodeError):
            continue
        if isinstance(data, dict):
            result.append(data)
    return result


def _event_stage(kind: str) -> str:
    if kind.startswith(('run.', 'subjob.')) or kind in ('job.workflow_changed', 'job.checkpoint_changed'):
        return 'control'
    return 'workspace'


def _run_log_aliases(work: Path, uid: str, current_id: str) -> tuple[str, ...]:
    """Follow only verified aliases of the same durable Work job ID."""
    aliases = [current_id] if _JOB_ID.fullmatch(str(current_id or '')) else []
    definition = _read_object(work / 'job.json', size_limit=1_000_000)
    if not definition or definition.get('file_type') != 'dwm-work-job':
        return tuple(aliases)
    if definition.get('job_uid') != uid:
        return tuple(aliases)
    for value in (definition.get('job_list_aliases') or [])[:12]:
        if isinstance(value, str) and _JOB_ID.fullmatch(value) and value not in aliases:
            aliases.append(value)
    return tuple(aliases)


def _run_log_events(work: Path, job_id: str, uid: str) -> list[StageEvent]:
    """Only linked run metadata; no log content, and no unrelated JOB-001."""
    if not _JOB_ID.fullmatch(str(job_id or '')):
        return []
    folder = work / 'run_logs' / job_id
    if not folder.is_dir() or folder.is_symlink():
        return []
    found = []
    # The run ID sorts chronologically, but list a bounded subset to avoid a
    # costly unlimited metadata scan on network Work drives.
    from itertools import islice
    for meta in sorted(islice(folder.glob('*.json'), 600), reverse=True):
        if len(found) >= 15:
            break
        if not _RUN_ID.fullmatch(meta.stem):
            continue
        data = _read_object(meta)
        if not data or data.get('job_id') != job_id or data.get('run_id') != meta.stem:
            continue
        if data.get('job_uid') != uid:
            continue
        status = _clean(data.get('status'))
        moment = _clean(data.get('completed_at') or data.get('started_at'), 45)
        desc = _clean(data.get('operation_name') or data.get('run_kind'), 90)
        found.append(StageEvent(moment, 'control', 'Kj\u00f8relogg: ' + status, desc))
    return found


def _assessment_events(report: Path, work: Path) -> list[StageEvent]:
    """Use the established report-hash-bound loaders, never raw stale sidecars."""
    try:
        if not report.resolve(strict=True).is_relative_to(work.resolve(strict=True)):
            return []
        if report.name != 'depot_validation_report.json':
            return []
    except (OSError, RuntimeError, ValueError):
        return []
    from noark5_workflow.analysis.depot_assessment import load_depot_assessment
    from app.depot_review_v019_a2 import load_part_decisions, STATUS_LABELS
    events = []
    for filename in ('depot_assessment.json', 'depot_assessment_parts.json'):
        path = report.with_name(filename)
        try:
            if path.is_symlink() or (path.exists() and path.stat().st_size > 8_000_000):
                return []  # suspicious metadata must not be interpreted
        except OSError:
            return []
    try:
        assessment = load_depot_assessment(report)
        if isinstance(assessment, dict):
            for row in (assessment.get('history') or ())[-25:]:
                if isinstance(row, dict) and row.get('status') in STATUS_LABELS:
                    events.append(StageEvent(
                        _clean(row.get('assessed_at'), 45), 'report',
                        'Faglig depotvurdering: ' + STATUS_LABELS[row['status']],
                        'Hele uttrekket',
                    ))
    except (OSError, ValueError, TypeError, UnicodeError):
        pass  # stale/corrupt/changed assessment is not historical proof here
    try:
        part_document = load_part_decisions(report)
        if isinstance(part_document, dict):
            parts = part_document.get('parts') or {}
            if isinstance(parts, dict):
                for part in list(parts.values())[:100]:
                    if not isinstance(part, dict):
                        continue
                    for row in (part.get('history') or ())[-8:]:
                        if isinstance(row, dict) and row.get('status') in STATUS_LABELS:
                            events.append(StageEvent(
                                _clean(row.get('assessed_at'), 45), 'report',
                                'Arkivdelvurdering: ' + STATUS_LABELS[row['status']],
                                _clean(part.get('title') or part.get('system_id'), 110),
                            ))
    except (OSError, ValueError, TypeError, UnicodeError):
        pass
    return events


def saved_history(work: Path | None, *, job_uid: str = '',
                  job_id: str = '', report: Path | None = None) -> tuple[StageEvent, ...]:
    """Read only relevant, bounded metadata; unbound old logs are not guessed."""
    if not _work_is_safe(work):
        return ()
    try:
        uid = str(UUID(str(job_uid)))
    except (TypeError, ValueError, AttributeError):
        return ()
    work = Path(work)
    events = []
    try:
        for row in _tail_events(work / 'job-events.jsonl'):
            if row.get('job_uid') != uid:
                continue
            kind = str(row.get('kind') or '')
            if not kind or len(kind) > 100:
                continue
            events.append(StageEvent(
                _clean(row.get('at'), 45), _event_stage(kind),
                kind, _clean(row.get('detail'), 170),
            ))
        for alias in _run_log_aliases(work, uid, job_id):
            events.extend(_run_log_events(work, alias, uid))
    except (OSError, ValueError, RuntimeError):
        pass
    if report is not None:
        events.extend(_assessment_events(Path(report), work))
    def order(item):
        try:
            return datetime.fromisoformat(item.at.replace('Z', '+00:00')).timestamp()
        except (ValueError, OverflowError, OSError):
            return 0.0
    return tuple(sorted(events, key=order, reverse=True)[:MAX_HISTORY])


def _progress_percent(value) -> int:
    try:
        result = float(value or 0)
        if not math.isfinite(result):
            return 0
        return round(100 * max(0., min(1., result)))
    except (TypeError, ValueError, OverflowError):
        return 0


def project_pipeline(job, *, evidence: ProductionEvidence | None = None,
                     job_uid: str = '', read_history: bool = True,
                     history: Iterable[StageEvent] | None = None) -> PipelineProgress:
    """Project all eight steps from one existing JobView and saved Work evidence."""
    if job is None:
        stages = tuple(StageProgress(k, n, 'unknown', 'Ingen aktiv jobb',
                                     'Velg en jobb i Kontroll f\u00f8rst.')
                       for k, n in STAGE_NAMES)
        return PipelineProgress('', '', '', 0, 0, 0, 'Ukjent',
                                'Ikke faglig vurdert', None, stages, (), ())
    if evidence is None:
        evidence = inspect_production_evidence(job)
    status = str(getattr(job, 'status', '') or '')
    job_id = str(getattr(job, 'job_id', '') or '')
    name = str(getattr(job, 'name', '') or '')
    try:
        count = max(0, int(getattr(job, 'operation_count', 0) or 0))
        completed = max(0, min(count, int(getattr(job, 'current_operation', 0) or 0)))
    except (ValueError, TypeError):
        count, completed = 0, 0
    percent = _progress_percent(getattr(job, 'progress', 0))
    work = evidence.work
    have_work = _work_is_safe(work)
    has_report = evidence.depot_report is not None
    report_status = evidence.technical_status
    decision = evidence.professional_status
    work_status = ('Tilgjengelig' if have_work else
                   'Frakoblet / mangler' if work else 'Ikke klargjort')
    control_state = 'pending'
    control_title = 'Ingen fullf\u00f8rt kj\u00f8ring dokumentert'
    if status == 'Kj\u00f8rer':
        control_state, control_title = 'active', 'Kj\u00f8ring p\u00e5g\u00e5r'
    elif status == 'Venter ved kontrollpunkt':
        control_state, control_title = 'attention', 'Venter ved kontrollpunkt'
    elif status == 'Feil':
        control_state, control_title = 'attention', 'Kj\u00f8ring har feilstatus'
    elif status.startswith('Frakoblet'):
        control_state, control_title = 'attention', 'Lagret jobb er frakoblet'
    elif status == 'Ferdig' and count > 0 and completed == count:
        control_state, control_title = 'done', 'Jobbkj\u00f8ring lagret som ferdig'
    elif completed > 0:
        control_state, control_title = 'partial', 'Delvis utf\u00f8rt kontroll'
    elif has_report:
        control_state, control_title = 'partial', 'Lagret depotrapport finnes'
    report_state = 'ready' if has_report else ('partial' if evidence.result_files else 'pending')
    preservation_state = ('partial' if 'Evidenskandidat funnet' in evidence.candidate_status
                          else 'attention' if 'Utrygg' in evidence.candidate_status
                          or 'Ugyldig' in evidence.candidate_status else 'pending')
    stages = (
        StageProgress('ingest', 'Ingest', 'unknown', 'Ikke knyttet til jobb',
                      'Mottaksevidens kobles enn\u00e5 ikke automatisk til jobben.'),
        StageProgress('antivirus', 'Antiviruskontroll', 'unknown', 'Ikke dokumentert i DWM',
                      'Ingen integrert skanner; ingen godkjent skanning kan utledes.'),
        StageProgress('workspace', 'Til arbeidsomr\u00e5de',
                      'ready' if have_work else 'attention' if work else 'pending',
                      work_status, str(work) if work else 'Work operations er ikke valgt.'),
        StageProgress('control', 'Kontroll', control_state, control_title,
                      f'Lagret jobbstatus: {status or "Ukjent"}; {completed}/{count} operasjoner ({percent} %). '
                      f'Depotrapportens tekniske status: {report_status}.'),
        StageProgress('report', 'Rapportering', report_state,
                      'Depotrapport funnet' if has_report else
                      'Andre resultatfiler finnes' if evidence.result_files else 'Ingen depotrapport',
                      f'{evidence.result_files} indekserte resultatfiler. '
                      f'Faglig depotstatus: {decision}.'),
        StageProgress('preserve', 'Bevaring', preservation_state,
                      evidence.candidate_status,
                      'Kandidat er ikke en verifisert DIAS AIP. Pakking starter ikke her.'),
        StageProgress('crm', 'Mot intern CRM', 'unknown', 'Ikke integrert',
                      'Ingen tilkobling eller eksportstatus.'),
        StageProgress('access', 'Innsyn', 'unknown', 'Ikke integrert',
                      'Ingen publisering eller innsynsstatus.'),
    )
    if history is not None:
        events = tuple(history)[:MAX_HISTORY]
    elif read_history and have_work:
        events = saved_history(work, job_uid=job_uid, job_id=job_id,
                               report=evidence.depot_report)
    else:
        events = ()
    return PipelineProgress(job_id, name, status, percent, completed, count,
                            report_status, decision, work, stages, events,
                            tuple(evidence.warnings))
