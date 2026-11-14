"""v0.2.0-a4: read-only Work evidence summary for Reporting / Preservation.

This is a presentation projection, NOT a new approval or package model. The
established depot assessment service verifies the exact source report SHA-256;
archive-part decisions are also report-version-bound. Missing or stale evidence
must never be rendered as an accepted extraction.

No discovery walks Source, creates a Work folder or verifies/creates an AIP.
Integrity verification remains an explicit operation in the existing DIAS link UI.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Mapping


@dataclass(frozen=True)
class ProductionEvidence:
    job_id: str
    job_name: str
    work: Path | None
    depot_report: Path | None
    result_files: int
    technical_status: str
    professional_status: str
    professional_history: int
    archive_parts: int | None
    reviewed_parts: int
    candidate_status: str
    warnings: tuple[str, ...]

    @property
    def has_job(self) -> bool:
        return bool(self.job_id)


def _candidate_status(work: Path) -> str:
    """Existence only. NEVER describe a manifest as verified or as an AIP."""
    stage = work / 'preservation_staging'
    candidate = stage / 'dwm-aip-candidate-v1'
    manifest = candidate / 'manifest-sha256.json'
    try:
        if stage.is_symlink() or candidate.is_symlink() or manifest.is_symlink():
            return 'Utrygg symbolsk lenke – krever kontroll'
        if not candidate.exists():
            return 'Ingen evidenskandidat funnet'
        if not candidate.is_dir():
            return 'Ugyldig plassering for evidenskandidat'
        if not manifest.is_file():
            return 'Evidenskandidat funnet, manifest mangler'
    except (OSError, ValueError):
        return 'Evidenskandidat kan ikke undersøkes'
    return 'Evidenskandidat funnet – integritet IKKE kontrollert'


def _empty(job_id='', job_name='', work=None, *, warning='') -> ProductionEvidence:
    return ProductionEvidence(
        job_id, job_name, work, None, 0, 'Ukjent', 'Ikke faglig vurdert',
        0, None, 0, 'Ikke undersøkt', (warning,) if warning else (),
    )


def inspect_production_evidence(
    job,
    *,
    discovery: Callable | None = None,
    load_assessment: Callable | None = None,
    load_parts: Callable | None = None,
    assessment_labels: Mapping[str, str] | None = None,
) -> ProductionEvidence:
    """Read the active job's already-saved Work without creating or changing it.

    Optional collaborators allow Qt-free regression tests with controlled Work
    reports; normal runtime uses the existing DWM result/depot services.
    """
    if job is None:
        return _empty(warning='Ingen aktiv jobb valgt. Velg en jobb i Kontroll.')
    job_id = str(getattr(job, 'job_id', '') or '')
    name = str(getattr(job, 'name', '') or '')
    value = getattr(job, 'effective_work_operations', None)
    if not value:
        return _empty(job_id, name, warning='Jobben mangler Work operations.')
    try:
        work = Path(value)
        if not work.is_dir():
            return _empty(job_id, name, work,
                          warning='Work operations finnes ikke eller er frakoblet.')
        if work.is_symlink():
            return _empty(job_id, name, work,
                          warning='Work operations er en symbolsk lenke og kan ikke vurderes her.')
    except (OSError, TypeError, ValueError) as exc:
        return _empty(job_id, name, warning='Kunne ikke lese Work: ' + str(exc))

    # Import only when the Work root exists, so opening the application never
    # triggers unused report/preservation engines.
    if discovery is None:
        from app.result_center_v018_a12 import discover_results
        discovery = discover_results
    if load_assessment is None:
        from noark5_workflow.analysis.depot_assessment import load_depot_assessment
    if load_parts is None or assessment_labels is None:
        from app.depot_review_v019_a2 import STATUS_LABELS, load_part_decisions
        if load_parts is None:
            load_parts = load_part_decisions
        if assessment_labels is None:
            assessment_labels = STATUS_LABELS

    warnings = []
    try:
        results = discovery(work)
    except (OSError, ValueError, RuntimeError) as exc:
        return _empty(job_id, name, work, warning='Resultatoversikten kan ikke leses: ' + str(exc))
    warnings.extend(str(w) for w in (getattr(results, 'warnings', ()) or ()))
    artifacts = getattr(results, 'artifacts', ()) or ()
    raw = getattr(results, 'depot_report', None)
    report = getattr(results, 'depot_report_path', None)
    if not isinstance(raw, dict) or report is None:
        warnings.append('Ingen gyldig lagret depotrapport funnet i Work.')
        return ProductionEvidence(
            job_id, name, work, None, len(artifacts), 'Ukjent',
            'Ikke faglig vurdert', 0, None, 0, _candidate_status(work),
            tuple(warnings),
        )

    # DWM's discovery has already checked file containment. Re-check here
    # because callers can pass a mock/custom result provider for testing.
    try:
        real_work = work.resolve(strict=True)
        checked_report = Path(report).resolve(strict=True)
        if (not checked_report.is_relative_to(real_work)
                or checked_report.name != 'depot_validation_report.json'
                or not checked_report.is_file()):
            raise ValueError('Depotrapport ligger ikke i valgt Work.')
    except (OSError, RuntimeError, ValueError) as exc:
        return _empty(job_id, name, work,
                      warning='Rapportreferansen er ugyldig: ' + str(exc))

    tech = raw.get('technical_validation') or {}
    technical = str(tech.get('status') or 'Ukjent') if isinstance(tech, dict) else 'Ukjent'
    parts = raw.get('archive_parts')
    total = sum(isinstance(part, dict) for part in parts) if isinstance(parts, list) else None
    status = 'Ikke faglig vurdert'
    history = 0
    reviewed = 0
    try:
        assessment = load_assessment(checked_report)
        if assessment is not None:
            current = assessment.get('current') if isinstance(assessment, dict) else None
            code = current.get('status') if isinstance(current, dict) else None
            if code in assessment_labels:
                status = assessment_labels[code]
                past = assessment.get('history') or ()
                history = len(past) if isinstance(past, list) else 0
            else:
                status = 'Historikk krever kontroll'
                warnings.append('Lagret depotvurdering mangler gyldig beslutningsstatus.')
    except (OSError, ValueError, TypeError, RuntimeError) as exc:
        status = 'Historikk krever kontroll'
        warnings.append('Faglig vurdering kan ikke knyttes til rapporten: ' + str(exc))

    try:
        document = load_parts(checked_report)
        if document is not None:
            saved = document.get('parts') or {}
            if not isinstance(saved, dict):
                raise ValueError('Arkivdelhistorikken er ugyldig.')
            reviewed = sum(
                isinstance(part, dict) and
                isinstance(part.get('current'), dict) and
                part['current'].get('status') in assessment_labels
                for part in saved.values()
            )
    except (OSError, ValueError, TypeError, RuntimeError) as exc:
        warnings.append('Arkivdelvurderinger må kontrolleres: ' + str(exc))

    return ProductionEvidence(
        job_id, name, work, checked_report, len(artifacts), technical,
        status, history, total, reviewed, _candidate_status(work), tuple(warnings),
    )
