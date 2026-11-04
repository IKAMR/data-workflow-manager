"""Bounded, read-only result overview for one independent DWM Work directory.

The UI does not need the original .n5jobs: every lookup stays inside known
DWM result locations. Source, AIP and unrecognized directories are never walked.
The index distinguishes results saved in Work from professional approval.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class ResultArtifact:
    category: str
    title: str
    path: Path
    relative_path: str
    modified_at: float
    size: int


@dataclass(frozen=True)
class ResultOverview:
    work: Path | None
    artifacts: tuple[ResultArtifact, ...]
    depot_report: dict[str, Any] | None
    depot_report_path: Path | None
    warnings: tuple[str, ...]
    @property
    def by_category(self) -> dict[str, tuple[ResultArtifact, ...]]:
        return {name: tuple(item for item in self.artifacts if item.category == name)
                for name in CATEGORY_ORDER}


CATEGORY_ORDER = (
    "Depotrapporter", "XPath / Noark 5", "Analysevisninger", "XML / XSD", "Arkade 5",
    "PRONOM", "KDRS Query", "Andre resultater",
)

# Only explicitly known DWM Work data, and deliberately bounded results.
# Exact globs are chosen to avoid visiting a large DOKUMENT or file-inventory tree.
_PATTERNS = {
    "Depotrapporter": (
        "noark5_reports/depot_validation/*/depot_validation_report.html",
        "noark5_reports/depot_validation/*/depot_validation_report.json",
        "noark5_reports/depot_validation/*/depot_validation_report.pdf",
        "noark5_reports/depot_validation/*/depot-derived-evidence-report.html",
    ),
    "XPath / Noark 5": (
        "noark5_tests/xpath/*/master-results.json",
        "noark5_tests/xpath/*/index.json",
        "noark5_tests/xpath/*/results/*.json",
        "noark5_views/*/index.html",
        "noark5_views/*/artifact_manifest.json",
    ),
    "Analysevisninger": (
        "noark5_views/*/index.json",
        "noark5_views/*/whole_extraction_overview.json",
        "noark5_views/*/archive_part_overview.json",
        "noark5_views/*/validation_evidence.json",
        "noark5_views/*/depot_control_summary.json",
        "noark5_views/*/presentations/*.json",
    ),
    "XML / XSD": (
        "noark5_tests/schema/*/xml-validation-*.json",
        "noark5_tests/schema/*/artifact_manifest.json",
    ),
    "Arkade 5": (
        "external_evidence/arkade5/*/manifest.json",
        "external_evidence/arkade5/*/normalized/arkade5_results.json",
        "external_evidence/arkade5/*/source/arkade-testrapport*.json",
    ),
    "PRONOM": (
        "external_evidence/arkade5/*/normalized/pronom_statistics.json",
        "external_evidence/arkade5/*/source/*filformatinfo-statistikk.csv",
    ),
    "KDRS Query": (
        "external_evidence/kdrs_query/*/manifest.json",
        "external_evidence/kdrs_query/*/normalized/*.json",
        "external_evidence/kdrs_query/*/*.json",
        "external_evidence/result-bank.json",
        "external_evidence/kdrs-query-report-selections.json",
    ),
    "Andre resultater": (
        "wf/results/raw-results.jsonl",
        "run_history/operations.jsonl",
        "job-state.json",
        "job-events.jsonl",
    ),
}

MAX_ITEMS = 700
MAX_PER_GROUP = 250
MAX_REPORT_BYTES = 12_000_000


def _safe_file(root: Path, item: Path) -> bool:
    """Reject symlink escapes, including symlink directories and file aliases."""
    try:
        return item.is_file() and item.resolve(strict=True).is_relative_to(root)
    except (OSError, RuntimeError, ValueError):
        return False


def _json_report(path: Path) -> dict[str, Any] | None:
    try:
        if path.stat().st_size > MAX_REPORT_BYTES:
            return None
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError):
        return None
    return value if isinstance(value, dict) and value.get("report_type") == "noark5_depot_validation" else None


def discover_results(work: str | Path | None) -> ResultOverview:
    if work is None:
        return ResultOverview(None, (), None, None, ("Work operations er ikke angitt.",))
    folder = Path(work)
    if not folder.is_dir():
        return ResultOverview(folder, (), None, None, ("Work operations er ikke tilgjengelig eller er frakoblet.",))
    try:
        root = folder.resolve(strict=True)
    except (OSError, RuntimeError):
        return ResultOverview(folder, (), None, None, ("Work operations kunne ikke åpnes.",))

    artifacts: list[ResultArtifact] = []
    warnings: list[str] = []
    seen: set[Path] = set()
    for group in CATEGORY_ORDER:
        candidates: list[Path] = []
        for pattern in _PATTERNS[group]:
            try:
                candidates.extend(root.glob(pattern))
            except (OSError, ValueError):
                warnings.append(f"Kunne ikke lese en del av området {group}.")
        kept = 0
        for item in sorted(candidates, key=lambda p: str(p).casefold()):
            if kept >= MAX_PER_GROUP or len(artifacts) >= MAX_ITEMS:
                if f"Resultatlisten for {group} er avkortet." not in warnings:
                    warnings.append(f"Resultatlisten for {group} er avkortet.")
                break
            if not _safe_file(root, item):
                continue
            canonical = item.resolve(strict=True)
            if canonical in seen:
                continue
            try:
                stat = item.stat()
                relative = item.relative_to(root).as_posix()
            except (OSError, ValueError):
                continue
            seen.add(canonical)
            kept += 1
            artifacts.append(ResultArtifact(
                group, item.name, canonical, relative,
                stat.st_mtime, stat.st_size,
            ))

    # Most recently written *valid* depot report, not just the newest filename.
    depot = None
    depot_file = None
    report_files = sorted((entry for entry in artifacts
                           if entry.category == "Depotrapporter" and entry.title == "depot_validation_report.json"),
                          key=lambda a: (a.modified_at, a.relative_path), reverse=True)
    for item in report_files:
        model = _json_report(item.path)
        if model is not None:
            depot, depot_file = model, item.path
            break
        warnings.append("En lagret depotrapport er ugyldig eller for stor: " + item.relative_path)

    if depot is not None and any(a.category == "PRONOM" for a in artifacts):
        reported = (((depot.get("external_validation") or {}).get("arkade5") or {})
                    .get("pronom_summary") or {}).get("statistics_imports", 0)
        if not reported:
            warnings.append(
                "PRONOM-filer finnes i Work, men lagret depotrapport oppgir "
                "0 statistikkimporter. Rapporten kan være eldre enn evidensen."
            )
    return ResultOverview(root, tuple(artifacts), depot, depot_file, tuple(warnings))


def depot_facts(model: dict[str, Any] | None) -> tuple[tuple[str, str], ...]:
    if not model:
        return ()
    summary = model.get("summary") or {}
    technical = model.get("technical_validation") or {}
    external = ((model.get("external_validation") or {}).get("arkade5") or {})
    a5 = external.get("summary") or {}
    pronom = external.get("pronom_summary") or {}
    assessment = model.get("assessment") or {}
    deviations = model.get("deviations") or []
    return tuple((label, str(value)) for label, value in (
        ("Arkiver", summary.get("archive_count", "Ikke angitt")),
        ("Arkivdeler", summary.get("archive_part_count", "Ikke angitt")),
        ("Mapper", summary.get("folder_count", "Ikke angitt")),
        ("Registreringer", summary.get("registration_count", "Ikke angitt")),
        ("Dokumentobjekter", summary.get("document_object_count", "Ikke angitt")),
        ("Teknisk status", technical.get("status", "Ikke angitt")),
        ("Vurderingsstatus", assessment.get("status", "Ikke vurdert")),
        ("Vurderingspunkter", len(deviations)),
        ("Arkade 5-importer", a5.get("imports", 0)),
        ("PRONOM-statistikkimporter", pronom.get("statistics_imports", 0)),
        ("PRONOM-filer", pronom.get("total_files", 0)),
    ))


def archive_part_rows(model: dict[str, Any] | None) -> tuple[dict[str, Any], ...]:
    """Keep archive-part data as recorded; never invent per-part status."""
    if not model:
        return ()
    return tuple(part for part in model.get("archive_parts", ()) if isinstance(part, dict))
