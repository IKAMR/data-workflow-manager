from __future__ import annotations

import json
import re
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable

from app.storage_layouts import suggest_storage_roles
from noark5_workflow.core.job import Job
from noark5_workflow.external_evidence.arkade5_discovery import (
    Arkade5Candidate,
    discover_arkade5_reports_in_roots,
)


_STORAGE_ROLE_ATTRS = (
    "source_root",
    "source_tar",
    "source_unzipped",
    "source_extraction",
    "work_root",
    "work_content",
    "work_operations",
    "archive_root",
)

_GENERIC_EXTRACTION_NAMES = {
    "avleveringspakke",
    "extraction",
    "uttrekk",
    "content",
}


@dataclass(frozen=True)
class StorageSuggestionJobResult:
    job_id: str
    filled: tuple[str, ...]
    preserved: tuple[str, ...]
    suggested: tuple[str, ...]


@dataclass(frozen=True)
class StorageSuggestionBatchResult:
    selected_jobs: int
    changed_jobs: int
    filled_fields: int
    jobs_without_suggestions: int
    job_results: tuple[StorageSuggestionJobResult, ...]


@dataclass(frozen=True)
class StorageSuggestionPreviewJob:
    job_id: str
    job_name: str
    fillable: tuple[tuple[str, Path], ...]
    preserved: tuple[str, ...]


def preview_missing_storage_suggestions(
    jobs: Iterable[Job],
    *,
    layout_id: str | None,
) -> tuple[StorageSuggestionPreviewJob, ...]:
    """Calculate the exact non-destructive changes without mutating jobs."""
    rows: list[StorageSuggestionPreviewJob] = []
    for job in jobs:
        suggestions = suggest_storage_roles(
            source_root=Path(job.source_root) if job.source_root is not None else None,
            extraction_root=(
                Path(job.source_extraction)
                if job.source_extraction is not None
                else None
            ),
            layout_id=layout_id,
        )
        fillable: list[tuple[str, Path]] = []
        preserved: list[str] = []
        for attr, value in suggestions.items():
            if attr not in _STORAGE_ROLE_ATTRS or value is None:
                continue
            if getattr(job, attr, None) is None:
                fillable.append((attr, Path(value)))
            else:
                preserved.append(attr)
        rows.append(
            StorageSuggestionPreviewJob(
                job_id=job.job_id,
                job_name=str(job.name or job.job_id),
                fillable=tuple(fillable),
                preserved=tuple(preserved),
            )
        )
    return tuple(rows)


@dataclass(frozen=True)
class Arkade5DiscoveryJobResult:
    job_id: str
    job_name: str
    candidates: tuple[Arkade5Candidate, ...]
    error: str = ""

    @property
    def found(self) -> int:
        return len(self.candidates)


@dataclass(frozen=True)
class Arkade5DiscoveryBatchResult:
    selected_jobs: int
    jobs_with_results: int
    reports_found: int
    jobs_without_results: int
    failed_jobs: int
    unmatched_reports: int
    job_results: tuple[Arkade5DiscoveryJobResult, ...]


def fill_missing_storage_suggestions(
    jobs: Iterable[Job],
    *,
    layout_id: str | None,
) -> StorageSuggestionBatchResult:
    """Fill only empty storage roles for a collection of jobs.

    This intentionally reuses the same suggestion engine as the Mapper dialog,
    but batch mode never overwrites an existing role. Conflicts remain untouched
    and can still be reviewed per job in Mapper.
    """
    selected = list(jobs)
    results: list[StorageSuggestionJobResult] = []
    changed_jobs = 0
    filled_fields = 0
    without_suggestions = 0

    for job in selected:
        suggestions = suggest_storage_roles(
            source_root=Path(job.source_root) if job.source_root is not None else None,
            extraction_root=(
                Path(job.source_extraction)
                if job.source_extraction is not None
                else None
            ),
            layout_id=layout_id,
        )
        suggestions = {
            name: Path(value)
            for name, value in suggestions.items()
            if name in _STORAGE_ROLE_ATTRS and value is not None
        }

        if not suggestions:
            without_suggestions += 1

        filled: list[str] = []
        preserved: list[str] = []
        for attr, suggested in suggestions.items():
            current = getattr(job, attr, None)
            if current is None:
                setattr(job, attr, suggested)
                filled.append(attr)
            else:
                preserved.append(attr)

        if filled:
            changed_jobs += 1
            filled_fields += len(filled)

        results.append(
            StorageSuggestionJobResult(
                job_id=job.job_id,
                filled=tuple(filled),
                preserved=tuple(preserved),
                suggested=tuple(suggestions),
            )
        )

    return StorageSuggestionBatchResult(
        selected_jobs=len(selected),
        changed_jobs=changed_jobs,
        filled_fields=filled_fields,
        jobs_without_suggestions=without_suggestions,
        job_results=tuple(results),
    )


def _path_key(value: str | Path | None) -> str:
    if value is None:
        return ""
    return str(Path(value)).replace("/", "\\").casefold().rstrip("\\")


def _search_signature(job: Job, configured_roots: tuple[str | Path, ...]) -> tuple:
    """Return the physical search-area identity for de-duplicating scans.

    Multiple archive-part jobs commonly share one Work root/repository_operations.
    Scanning that area once is both faster and necessary before correlating reports
    back to the individual job.
    """
    return (
        _path_key(job.work_operations),
        _path_key(job.work_root),
        _path_key(job.source_root or job.source_extraction),
        tuple(_path_key(value) for value in configured_roots),
    )


def _identity_aliases(job: Job) -> tuple[str, ...]:
    """Stable job/extraction labels usable for report-to-job correlation."""
    values: list[str] = []

    def add(value: str | Path | None) -> None:
        text = str(value or "").strip()
        if not text:
            return
        folded = text.casefold()
        if folded not in values:
            values.append(folded)

    add(job.name)

    extraction = Path(job.source_extraction) if job.source_extraction else None
    if extraction is not None:
        if extraction.name.casefold() not in _GENERIC_EXTRACTION_NAMES:
            add(extraction.name)
        if extraction.parent.name:
            add(extraction.parent.name)

    # Discovery-created Noark 5 job names often end in a timestamp. Keep a
    # shorter prefix as a secondary signal, but never use it ahead of the full
    # extraction/job identity.
    for current in list(values):
        short = re.sub(
            r"[-_ ]20\d{2}[-_]\d{2}[-_]\d{2}(?:[-_ ]\d{2}){2,3}[-_ ]\d+$",
            "",
            current,
        ).strip("-_ ")
        if len(short) >= 3 and short not in values:
            values.append(short)

    return tuple(values)


def _candidate_summary_text(path: Path) -> str:
    """Read only small Arkade Summary identity fields for correlation.

    The report has already been validated by Arkade discovery. Failure to read
    optional identity metadata must not make discovery fail; the path identity
    remains available.
    """
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        return ""
    summary = data.get("Summary") if isinstance(data, dict) else None
    if not isinstance(summary, dict):
        return ""
    parts = []
    for key in (
        "SystemName",
        "SystemType",
        "ArchiveType",
        "ArchiveCreators",
        "Uuid",
    ):
        value = summary.get(key)
        if isinstance(value, (list, tuple)):
            parts.extend(str(item) for item in value)
        elif value is not None:
            parts.append(str(value))
    return " ".join(parts).casefold()


def _match_score(job: Job, candidate: Arkade5Candidate) -> int:
    aliases = _identity_aliases(job)
    if not aliases:
        return 0

    path_text = str(candidate.path).replace("/", "\\").casefold()
    parts = [part.casefold() for part in Path(candidate.path).parts]
    stem = candidate.path.stem.casefold()
    summary_text = _candidate_summary_text(candidate.path)

    score = 0
    for index, alias in enumerate(aliases):
        primary = index < 2
        weight = 120 if primary else 55
        # A complete path component is strongest: Arkade result directories
        # frequently keep the exact extraction identity even when report file
        # names are shorter or use another local abbreviation.
        if alias in parts:
            score = max(score, weight + 80)
        elif f"\\{alias}\\" in f"\\{path_text}\\":
            score = max(score, weight + 70)
        elif alias in stem:
            score = max(score, weight + 45)
        elif alias in path_text:
            score = max(score, weight + 30)
        elif alias in summary_text:
            score = max(score, weight + 20)

    return score


def _assign_candidates_to_jobs(
    jobs: list[Job],
    candidates: Iterable[Arkade5Candidate],
) -> tuple[dict[str, list[Arkade5Candidate]], list[Arkade5Candidate]]:
    """Assign each discovered report to at most one job.

    A report is only assigned when one selected job is the unique best identity
    match. Ambiguous/unmatched reports are retained in the aggregate count but
    are deliberately not repeated under every job.
    """
    assigned: dict[str, list[Arkade5Candidate]] = {
        job.job_id: [] for job in jobs
    }
    unmatched: list[Arkade5Candidate] = []

    if len(jobs) == 1:
        only = jobs[0]
        assigned[only.job_id].extend(candidates)
        return assigned, unmatched

    for candidate in candidates:
        scored = [(job, _match_score(job, candidate)) for job in jobs]
        best = max((score for _job, score in scored), default=0)
        winners = [job for job, score in scored if score == best and score > 0]
        if len(winners) == 1:
            assigned[winners[0].job_id].append(candidate)
        else:
            unmatched.append(candidate)

    return assigned, unmatched


def discover_arkade5_results_for_jobs(
    jobs: Iterable[Job],
    *,
    configured_roots: Iterable[str | Path] = (),
    on_progress: Callable[[str], None] | None = None,
) -> Arkade5DiscoveryBatchResult:
    """Discover and correlate existing Arkade 5 reports without importing them.

    Shared Source/Work areas are scanned only once. The resulting reports are
    then correlated to the selected job by its job/extraction identity. This
    avoids the a25.1 behaviour where every report in a shared Work area was
    repeated under every selected job.
    """
    selected = list(jobs)
    roots = tuple(configured_roots)
    results_by_id: dict[str, Arkade5DiscoveryJobResult] = {}
    unmatched_reports = 0

    def progress(text: str) -> None:
        if on_progress is not None:
            on_progress(text)

    progress(f"Forbereder Arkade 5-søk for {len(selected)} jobb(er) …")

    groups: dict[tuple, list[Job]] = defaultdict(list)
    for job in selected:
        groups[_search_signature(job, roots)].append(job)

    group_items = list(groups.values())
    for group_no, group_jobs in enumerate(group_items, start=1):
        anchor = group_jobs[0]
        names = ", ".join(str(job.name or job.job_id) for job in group_jobs[:2])
        if len(group_jobs) > 2:
            names += f" + {len(group_jobs) - 2}"
        progress(
            f"Søker Arkade 5-resultater i mappeområde {group_no} av "
            f"{len(group_items)}: {names} …"
        )

        try:
            candidates = discover_arkade5_reports_in_roots(
                work_operations=anchor.work_operations,
                work_root=anchor.work_root,
                source_root=anchor.source_root or anchor.source_extraction,
                configured_roots=roots,
            )
        except Exception as exc:
            for job in group_jobs:
                results_by_id[job.job_id] = Arkade5DiscoveryJobResult(
                    job_id=job.job_id,
                    job_name=str(job.name or job.job_id),
                    candidates=(),
                    error=str(exc),
                )
            continue

        assigned, unmatched = _assign_candidates_to_jobs(group_jobs, candidates)
        unmatched_reports += len(unmatched)

        for job_no, job in enumerate(group_jobs, start=1):
            progress(
                f"Kobler Arkade 5-resultater {job_no} av {len(group_jobs)}: "
                f"{job.name or job.job_id} …"
            )
            results_by_id[job.job_id] = Arkade5DiscoveryJobResult(
                job_id=job.job_id,
                job_name=str(job.name or job.job_id),
                candidates=tuple(assigned.get(job.job_id, ())),
            )

    results = [
        results_by_id.get(
            job.job_id,
            Arkade5DiscoveryJobResult(
                job_id=job.job_id,
                job_name=str(job.name or job.job_id),
                candidates=(),
                error="Ingen søkeresultat ble produsert.",
            ),
        )
        for job in selected
    ]

    jobs_with_results = sum(bool(row.candidates) for row in results)
    failed_jobs = sum(bool(row.error) for row in results)
    reports_found = sum(len(row.candidates) for row in results)
    jobs_without_results = sum(
        not row.candidates and not row.error for row in results
    )

    progress(
        f"Arkade 5-søk ferdig: {reports_found} rapportkobling(er) for "
        f"{jobs_with_results} av {len(selected)} jobb(er)."
    )

    return Arkade5DiscoveryBatchResult(
        selected_jobs=len(selected),
        jobs_with_results=jobs_with_results,
        reports_found=reports_found,
        jobs_without_results=jobs_without_results,
        failed_jobs=failed_jobs,
        unmatched_reports=unmatched_reports,
        job_results=tuple(results),
    )




@dataclass(frozen=True)
class Arkade5DiscoveryImportState:
    job_id: str
    report_path: Path
    sha256: str
    status: str
    import_id: str = ""


def classify_arkade5_discovery_import_state(
    jobs: Iterable[Job],
    result: Arkade5DiscoveryBatchResult,
) -> tuple[Arkade5DiscoveryImportState, ...]:
    """Classify discovered reports as new/already imported per target job.

    Import identity is source SHA-256 within the job's Work - operations area.
    This mirrors the real import duplicate guard so the review dialog can show
    the state *before* the user presses import.
    """
    job_by_id = {job.job_id: job for job in jobs}
    cache: dict[str, dict[str, dict]] = {}
    states: list[Arkade5DiscoveryImportState] = []

    def existing_for(work: Path) -> dict[str, dict]:
        key = _path_key(work)
        if key not in cache:
            manifests = _list_arkade5_imports(work)
            cache[key] = {
                str((row.get("source") or {}).get("sha256") or "").casefold(): row
                for row in manifests
                if str((row.get("source") or {}).get("sha256") or "").strip()
            }
        return cache[key]

    for job_result in result.job_results:
        job = job_by_id.get(job_result.job_id)
        existing: dict[str, dict] = {}
        if job is not None and job.work_operations is not None:
            existing = existing_for(Path(job.work_operations))
        for candidate in job_result.candidates:
            digest = str(candidate.sha256 or "").casefold()
            manifest = existing.get(digest) if digest else None
            states.append(
                Arkade5DiscoveryImportState(
                    job_id=job_result.job_id,
                    report_path=Path(candidate.path),
                    sha256=digest,
                    status="already_imported" if manifest is not None else "new",
                    import_id=str((manifest or {}).get("import_id") or ""),
                )
            )
    return tuple(states)


def _list_arkade5_imports(work_operations: Path):
    from noark5_workflow.external_evidence.arkade5 import list_arkade5_imports
    return list_arkade5_imports(work_operations)


def _import_arkade5_report(*args, **kwargs):
    from noark5_workflow.external_evidence.arkade5 import import_arkade5_report
    return import_arkade5_report(*args, **kwargs)


def _attach_arkade5_pronom_evidence(*args, **kwargs):
    from noark5_workflow.external_evidence.arkade5_pronom import attach_arkade5_pronom_evidence
    return attach_arkade5_pronom_evidence(*args, **kwargs)


@dataclass(frozen=True)
class Arkade5ImportItemResult:
    job_id: str
    report_path: Path
    status: str
    import_id: str = ""
    error: str = ""
    pronom_attached: bool = False
    pronom_error: str = ""


@dataclass(frozen=True)
class Arkade5ImportBatchResult:
    selected_reports: int
    selected_jobs: int
    imported: int
    already_imported: int
    failed: int
    pronom_attached: int
    pronom_failed: int
    item_results: tuple[Arkade5ImportItemResult, ...]


def import_selected_arkade5_results(
    jobs: Iterable[Job],
    selected: Iterable[tuple[str, Arkade5Candidate]],
    *,
    imported_by: dict[str, str] | None = None,
    on_progress: Callable[[str], None] | None = None,
) -> Arkade5ImportBatchResult:
    """Import exactly the user-selected Arkade 5 reports to their jobs.

    The caller supplies the explicit job/report correlation produced by the
    discovery/review step. Reports are imported into each job's own
    ``work_operations`` external-evidence area. Existing imports are detected
    by source SHA-256 and are not duplicated.
    """
    job_by_id = {job.job_id: job for job in jobs}
    choices = list(selected)
    rows: list[Arkade5ImportItemResult] = []
    cache: dict[str, dict[str, dict]] = {}

    def progress(text: str) -> None:
        if on_progress is not None:
            on_progress(text)

    def existing_for(work: Path) -> dict[str, dict]:
        key = _path_key(work)
        if key not in cache:
            manifests = _list_arkade5_imports(work)
            cache[key] = {
                str((row.get("source") or {}).get("sha256") or "").casefold(): row
                for row in manifests
                if str((row.get("source") or {}).get("sha256") or "").strip()
            }
        return cache[key]

    total = len(choices)
    for index, (job_id, candidate) in enumerate(choices, start=1):
        job = job_by_id.get(job_id)
        progress(
            f"Importerer Arkade 5-resultat {index} av {total}: "
            f"{getattr(job, 'name', '') or job_id} …"
        )
        if job is None:
            rows.append(
                Arkade5ImportItemResult(
                    job_id=job_id,
                    report_path=Path(candidate.path),
                    status="failed",
                    error="Jobben finnes ikke lenger i jobblisten.",
                )
            )
            continue
        if job.work_operations is None:
            rows.append(
                Arkade5ImportItemResult(
                    job_id=job_id,
                    report_path=Path(candidate.path),
                    status="failed",
                    error="Work - operations er ikke definert for jobben.",
                )
            )
            continue

        work = Path(job.work_operations)
        digest = str(candidate.sha256 or "").casefold()
        existing = existing_for(work)
        manifest = existing.get(digest) if digest else None
        status = "already_imported" if manifest is not None else "imported"

        try:
            if manifest is None:
                provenance = dict(imported_by or {})
                provenance.update({
                    "mode": "job_batch_action",
                    "job_id": job.job_id,
                })
                manifest = _import_arkade5_report(
                    candidate.path,
                    work_operations=work,
                    imported_by=provenance,
                )
                manifest_digest = str(
                    (manifest.get("source") or {}).get("sha256") or digest
                ).casefold()
                if manifest_digest:
                    existing[manifest_digest] = manifest

            import_id = str((manifest or {}).get("import_id") or "")
            pronom_attached = False
            pronom_error = ""
            if import_id:
                try:
                    pronom = _attach_arkade5_pronom_evidence(
                        candidate.path,
                        work_operations=work,
                        import_id=import_id,
                    )
                    pronom_attached = bool(pronom)
                except Exception as exc:
                    # PRONOM is additional evidence. Failure to attach it must
                    # not turn an otherwise successful Arkade report import into
                    # a failed import.
                    pronom_error = str(exc)

            rows.append(
                Arkade5ImportItemResult(
                    job_id=job_id,
                    report_path=Path(candidate.path),
                    status=status,
                    import_id=import_id,
                    pronom_attached=pronom_attached,
                    pronom_error=pronom_error,
                )
            )
        except Exception as exc:
            rows.append(
                Arkade5ImportItemResult(
                    job_id=job_id,
                    report_path=Path(candidate.path),
                    status="failed",
                    error=str(exc),
                )
            )

    imported = sum(row.status == "imported" for row in rows)
    already = sum(row.status == "already_imported" for row in rows)
    failed = sum(row.status == "failed" for row in rows)
    pronom_attached = sum(row.pronom_attached for row in rows)
    pronom_failed = sum(bool(row.pronom_error) for row in rows)
    selected_jobs = len({job_id for job_id, _candidate in choices})

    progress(
        f"Arkade 5-import ferdig: {imported} importert, "
        f"{already} allerede importert, {failed} feil."
    )
    return Arkade5ImportBatchResult(
        selected_reports=total,
        selected_jobs=selected_jobs,
        imported=imported,
        already_imported=already,
        failed=failed,
        pronom_attached=pronom_attached,
        pronom_failed=pronom_failed,
        item_results=tuple(rows),
    )
