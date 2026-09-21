from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ResultInventory:
    work_operations: Path
    source_extraction: Path | None
    manifests: int = 0
    schema_runs: int = 0
    xpath_runs: int = 0
    view_runs: int = 0
    depot_report_runs: int = 0
    other_runs: int = 0
    legacy_artifacts: int = 0
    raw_result_stores: int = 0

    @property
    def has_results(self) -> bool:
        return any((
            self.manifests,
            self.schema_runs,
            self.xpath_runs,
            self.view_runs,
            self.depot_report_runs,
            self.other_runs,
            self.legacy_artifacts,
            self.raw_result_stores,
        ))

    @property
    def summary(self) -> str:
        if not self.has_results:
            return "Ingen resultater funnet"

        parts = []
        if self.schema_runs:
            parts.append(f"XML {self.schema_runs}")
        if self.xpath_runs:
            parts.append(f"XPath {self.xpath_runs}")
        if self.view_runs:
            parts.append(f"Views {self.view_runs}")
        if self.depot_report_runs:
            parts.append(f"Rapport {self.depot_report_runs}")
        if self.other_runs:
            parts.append(f"Andre {self.other_runs}")
        if self.raw_result_stores:
            parts.append(f"Råresultat {self.raw_result_stores}")
        if self.legacy_artifacts:
            parts.append(f"Legacy/ukjent {self.legacy_artifacts}")
        return " | ".join(parts)


def _norm(path: Path | str | None) -> str:
    if path is None:
        return ""
    value = str(path).replace("/", "\\").rstrip("\\").casefold()
    return value


def _manifest_matches_source(data: dict, source_extraction: Path | None) -> bool:
    if source_extraction is None:
        return True
    manifest_source = str(data.get("source_extraction", "") or "").strip()
    if not manifest_source:
        return True
    return _norm(manifest_source) == _norm(source_extraction)


def _classify_manifest(data: dict, manifest_path: Path) -> str:
    operation_id = str(data.get("operation_id", "") or "").casefold()
    parts = {part.casefold() for part in manifest_path.parts}

    if operation_id == "validate_xml_schema" or "schema" in parts:
        return "schema"
    if "xpath" in operation_id or "xpath" in parts:
        return "xpath"
    if operation_id == "compose_noark5_views" or "noark5_views" in parts:
        return "views"
    if operation_id == "build_noark5_depot_report" or "depot_validation" in parts:
        return "report"
    return "other"


def scan_result_inventory(
    work_operations: Path | None,
    *,
    source_extraction: Path | None = None,
) -> ResultInventory:
    """Inspect one Work - operations tree without modifying it.

    New a16.4.7+ artifacts are matched by artifact_manifest.json and, when
    possible, source_extraction. Legacy files without manifests are reported
    separately and are deliberately not claimed to belong to a specific source.
    """
    if work_operations is None:
        return ResultInventory(Path("."), source_extraction)

    root = Path(work_operations)
    if not root.is_dir():
        return ResultInventory(root, source_extraction)

    manifests = 0
    schema = 0
    xpath = 0
    views = 0
    reports = 0
    other = 0
    manifest_dirs: set[Path] = set()

    for manifest in root.rglob("artifact_manifest.json"):
        try:
            data = json.loads(manifest.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(data, dict):
            continue
        if not _manifest_matches_source(data, source_extraction):
            continue

        manifests += 1
        manifest_dirs.add(manifest.parent)
        kind = _classify_manifest(data, manifest)
        if kind == "schema":
            schema += 1
        elif kind == "xpath":
            xpath += 1
        elif kind == "views":
            views += 1
        elif kind == "report":
            reports += 1
        else:
            other += 1

    raw_stores = sum(
        1 for path in root.rglob("raw-results.jsonl")
        if path.is_file()
    )

    # Recognise pre-a16.4.7 output only as legacy/unknown. Do not claim that a
    # legacy shared result belongs to this source when no source identity exists.
    legacy_candidates: set[Path] = set()
    patterns = (
        "xml-validation-arkivstruktur.json",
        "index.json",
        "depot_validation_report.json",
        "depot_validation_report.html",
    )
    for pattern in patterns:
        for path in root.rglob(pattern):
            if not path.is_file():
                continue
            if any(parent in manifest_dirs for parent in (path.parent, *path.parents)):
                continue
            legacy_candidates.add(path)

    return ResultInventory(
        work_operations=root,
        source_extraction=source_extraction,
        manifests=manifests,
        schema_runs=schema,
        xpath_runs=xpath,
        view_runs=views,
        depot_report_runs=reports,
        other_runs=other,
        legacy_artifacts=len(legacy_candidates),
        raw_result_stores=raw_stores,
    )
