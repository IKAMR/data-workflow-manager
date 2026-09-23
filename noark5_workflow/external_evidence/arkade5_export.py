
from __future__ import annotations

import hashlib
import json
import shutil
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .arkade5 import list_arkade5_imports, load_arkade5_import
from .arkade5_gap_analysis import build_gap_overlap_analysis
from .arkade5_coverage_policy import (
    load_arkade5_coverage_policy,
    validate_arkade5_coverage_policy,
)
from .combined_coverage import build_combined_coverage


PACKAGE_FORMAT_VERSION = 2
PACKAGE_TYPE = "dwm.noark5.arkade5-portable-evidence"


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _record(
    path: Path,
    *,
    package_root: Path,
    records: list[dict[str, Any]],
    role: str,
) -> None:
    records.append({
        "path": path.relative_to(package_root).as_posix(),
        "role": role,
        "sha256": _sha256(path),
        "size": path.stat().st_size,
    })


def _copy_with_record(
    source: Path,
    target: Path,
    *,
    package_root: Path,
    records: list[dict[str, Any]],
    role: str,
) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)
    _record(target, package_root=package_root, records=records, role=role)


def _dwm_test_ids_present(depot_model: dict[str, Any] | None) -> list[str]:
    tests = (((depot_model or {}).get("technical_validation") or {}).get("tests") or [])
    return sorted({
        str(row.get("test_id") or "").strip()
        for row in tests
        if str(row.get("test_id") or "").strip()
    })


def write_arkade5_evidence_package(
    *,
    work_operations: str | Path,
    output_dir: str | Path,
    depot_model: dict[str, Any] | None = None,
) -> Path:
    """Write portable Arkade evidence plus the semantic knowledge used by DWM."""
    work = Path(work_operations)
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)

    imports = list_arkade5_imports(work)
    if not imports:
        raise ValueError("Ingen importerte Arkade 5-rapporter er tilgjengelige for eksport.")

    gap_analysis = build_gap_overlap_analysis()
    policy = load_arkade5_coverage_policy()
    policy_validation = validate_arkade5_coverage_policy(
        policy=policy,
        gap_analysis=gap_analysis,
    )
    if not policy_validation["valid"]:
        raise ValueError(
            "Arkade 5-dekningspolicy samsvarer ikke med dokumentert gap-analyse."
        )

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    zip_path = output / f"arkade5-evidence-{stamp}.zip"

    repo_root = _repo_root()
    knowledge_sources = [
        ("config/noark5/external/arkade5_test_catalog.json", "arkade_test_catalog"),
        ("config/noark5/external/dwm_arkade5_mapping.json", "dwm_arkade5_mapping"),
        ("config/noark5/external/combined_coverage_model.json", "combined_coverage_model"),
        ("config/noark5/external/gap_overlap_model.json", "gap_overlap_model"),
        ("config/noark5/external/arkade5_coverage_policy.json", "coverage_policy"),
    ]

    dwm_ids = _dwm_test_ids_present(depot_model)
    records: list[dict[str, Any]] = []
    import_rows: list[dict[str, Any]] = []

    with tempfile.TemporaryDirectory(prefix="dwm-arkade5-export-") as td:
        package_root = Path(td) / "arkade5-evidence"
        package_root.mkdir(parents=True, exist_ok=True)

        for relative, role in knowledge_sources:
            src = repo_root / relative
            if not src.is_file():
                raise FileNotFoundError(
                    f"Mangler kunnskapsfil for Arkade-eksport: {relative}"
                )
            dst = package_root / "knowledge" / Path(relative).name
            _copy_with_record(
                src, dst, package_root=package_root, records=records, role=role
            )

        gap_target = package_root / "analysis" / "gap_overlap_analysis.json"
        _write_json(gap_target, gap_analysis)
        _record(
            gap_target,
            package_root=package_root,
            records=records,
            role="gap_overlap_analysis",
        )

        policy_validation_target = (
            package_root / "analysis" / "coverage_policy_validation.json"
        )
        _write_json(policy_validation_target, policy_validation)
        _record(
            policy_validation_target,
            package_root=package_root,
            records=records,
            role="coverage_policy_validation",
        )

        for manifest in imports:
            import_id = str(manifest.get("import_id") or "").strip()
            if not import_id:
                continue

            loaded = load_arkade5_import(work, import_id)
            normalized = loaded.get("normalized") or {}
            reconciliation = loaded.get("reconciliation")
            source_meta = manifest.get("source") or {}

            import_root = package_root / "imports" / import_id
            source_relative = str(source_meta.get("preserved_file") or "").strip()
            if not source_relative:
                raise ValueError(f"Arkade-import {import_id} mangler preserved_file.")
            source_path = work / source_relative
            if not source_path.is_file():
                raise FileNotFoundError(
                    f"Bevart Arkade-kildefil finnes ikke for {import_id}: {source_path}"
                )

            raw_target = import_root / "source" / source_path.name
            _copy_with_record(
                source_path,
                raw_target,
                package_root=package_root,
                records=records,
                role="arkade_raw_source",
            )

            normalized_target = import_root / "normalized" / "arkade5_results.json"
            _write_json(normalized_target, normalized)
            _record(
                normalized_target,
                package_root=package_root,
                records=records,
                role="arkade_normalized",
            )

            if reconciliation is not None:
                rec_target = (
                    import_root
                    / "reconciliation"
                    / "arkade5_dwm_reconciliation.json"
                )
                _write_json(rec_target, reconciliation)
                _record(
                    rec_target,
                    package_root=package_root,
                    records=records,
                    role="arkade_dwm_reconciliation",
                )

            coverage = build_combined_coverage(
                arkade_normalized=normalized,
                dwm_test_ids_present=dwm_ids,
            )
            coverage_target = import_root / "combined_coverage.json"
            _write_json(coverage_target, coverage)
            _record(
                coverage_target,
                package_root=package_root,
                records=records,
                role="combined_coverage",
            )

            manifest_target = import_root / "import_manifest.json"
            portable_manifest = {
                key: value
                for key, value in manifest.items()
                if key != "manifest_path"
            }
            _write_json(manifest_target, portable_manifest)
            _record(
                manifest_target,
                package_root=package_root,
                records=records,
                role="arkade_import_manifest",
            )

            import_rows.append({
                "import_id": import_id,
                "source_file": source_path.name,
                "source_sha256": source_meta.get("sha256"),
                "source_version": normalized.get("source_version"),
                "date_of_testing": (normalized.get("summary") or {}).get(
                    "date_of_testing"
                ),
                "tests": len(normalized.get("tests") or []),
                "coverage_summary": coverage.get("summary"),
            })

        readme = package_root / "README.md"
        readme.write_text(
            "# Arkade 5 portable evidence package\n\n"
            "Pakken er eksportert av Data Workflow Manager og bevarer Arkade 5 "
            "som ekstern evidens. `source/` er original kilderapport, "
            "`normalized/` er tapsfri DWM-normalisering og `knowledge/` "
            "inneholder testkatalog, mapping, gapmodell og gjeldende "
            "dekningspolicy. `analysis/` inneholder materialisert statisk "
            "gap-/overlappanalyse og policykontroll.\n\n"
            "Arkade-resultater blir ikke DWM-masterresultater. Dokumenterte "
            "DWM-gap kan dekkes av Arkade som ekstern validator uten at "
            "kontrollen må reimplementeres i DWM.\n",
            encoding="utf-8",
        )
        _record(
            readme,
            package_root=package_root,
            records=records,
            role="package_readme",
        )

        package_manifest = {
            "format_version": PACKAGE_FORMAT_VERSION,
            "package_type": PACKAGE_TYPE,
            "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "principles": {
                "raw_source_preserved": True,
                "normalization_separate_from_source": True,
                "semantic_mapping_separate_from_results": True,
                "same_test_number_is_not_equivalence": True,
                "arkade_does_not_become_dwm_master": True,
                "arkade_can_close_documented_dwm_gap": True,
                "internal_reimplementation_not_required_for_current_coverage": True,
                "no_automatic_depot_decision": True,
            },
            "knowledge": {
                "gap_analysis_model_id": gap_analysis.get("model_id"),
                "coverage_policy_id": policy.get("policy_id"),
                "coverage_policy_valid": policy_validation["valid"],
            },
            "dwm_test_ids_present": dwm_ids,
            "imports": import_rows,
            "files": sorted(records, key=lambda row: row["path"]),
        }
        manifest_path = package_root / "manifest.json"
        _write_json(manifest_path, package_manifest)

        with zipfile.ZipFile(
            zip_path, "w", compression=zipfile.ZIP_DEFLATED
        ) as archive:
            for path in sorted(package_root.rglob("*")):
                if path.is_file():
                    archive.write(
                        path,
                        path.relative_to(package_root).as_posix(),
                    )

    return zip_path
