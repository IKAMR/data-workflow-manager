
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

from .arkade5_coverage_policy import validate_arkade5_coverage_policy


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _add(checks, check_id, ok, expected=None, actual=None, detail=""):
    checks.append({
        "check_id": check_id,
        "status": "OK" if ok else "ERROR",
        "expected": expected,
        "actual": actual,
        "detail": detail,
    })


def build_arkade5_integration_health(*, repo_root: str | Path | None = None) -> dict[str, Any]:
    root = Path(repo_root) if repo_root is not None else _repo_root()
    contract = _read_json(root / "config/noark5/external/arkade5_integration_contract.json")
    expected = contract["expected"]
    checks = []

    missing_files = sorted(
        rel for rel in contract.get("required_files") or []
        if not (root / rel).is_file()
    )
    _add(checks, "required_files", not missing_files,
         "all required files exist", missing_files)

    profile = _read_json(root / "config/noark5/profile.json")
    profile_paths = set()
    for values in (profile.get("definitions") or {}).values():
        if isinstance(values, list):
            profile_paths.update(str(v) for v in values)
    profile_paths.update(str(v) for v in profile.get("documentation") or [])

    required_profile_paths = {
        "config/noark5/external/arkade5_test_catalog.json",
        "config/noark5/external/dwm_arkade5_mapping.json",
        "config/noark5/external/combined_coverage_model.json",
        "config/noark5/external/gap_overlap_model.json",
        "config/noark5/external/arkade5_coverage_policy.json",
        "config/noark5/external/arkade5_integration_contract.json",
        "docs/ARKADE5-NOARK5-TESTS.md",
        "docs/ARKADE5-DWM-MAPPING.md",
        "docs/ARKADE5-IMPORT-MODEL.md",
        "docs/ARKADE5-COMBINED-COVERAGE.md",
        "docs/ARKADE5-DEPOT-REPORT.md",
        "docs/ARKADE5-GUI-COVERAGE.md",
        "docs/ARKADE5-GUI-DRILLDOWN.md",
        "docs/ARKADE5-PORTABLE-EVIDENCE.md",
        "docs/ARKADE5-DWM-GAP-OVERLAP.md",
        "docs/ARKADE5-DWM-GAP-OVERLAP-GUI.md",
        "docs/ARKADE5-COVERAGE-POLICY.md",
        "docs/ARKADE5-INTEGRATION-CONTRACT.md",
    }
    missing_profile = sorted(required_profile_paths - profile_paths)
    _add(checks, "profile_discoverability", not missing_profile,
         "all integration files discoverable from profile", missing_profile)

    catalog = _read_json(root / "config/noark5/external/arkade5_test_catalog.json")
    mapping = _read_json(root / "config/noark5/external/dwm_arkade5_mapping.json")
    policy = _read_json(root / "config/noark5/external/arkade5_coverage_policy.json")
    dwm_catalog = _read_json(root / "config/noark5/tests/xpath_catalog_2026_05_26.json")

    catalog_tests = catalog.get("tests") or []
    catalog_ids = [str(r.get("arkade_test_id") or "").upper() for r in catalog_tests]
    _add(checks, "arkade_catalog_count",
         len(catalog_ids) == expected["arkade_test_count"],
         expected["arkade_test_count"], len(catalog_ids))
    _add(checks, "arkade_catalog_unique_ids",
         len(catalog_ids) == len(set(catalog_ids)),
         expected["arkade_test_count"], len(set(catalog_ids)))

    mapped_rows = mapping.get("arkade_to_dwm") or []
    mapped_ids = [str(r.get("arkade_test_id") or "").upper() for r in mapped_rows]
    _add(checks, "mapping_has_one_row_per_arkade_test",
         len(mapped_ids) == expected["arkade_test_count"]
         and len(mapped_ids) == len(set(mapped_ids))
         and set(mapped_ids) == set(catalog_ids),
         sorted(catalog_ids), sorted(mapped_ids))

    relation_counts = Counter(
        str(r.get("relation") or r.get("coverage") or "") for r in mapped_rows
    )
    _add(checks, "mapping_relation_counts",
         dict(relation_counts) == expected["relations"],
         expected["relations"], dict(relation_counts))

    dwm_only = mapping.get("dwm_only") or []
    _add(checks, "dwm_only_count",
         len(dwm_only) == expected["dwm_only_count"],
         expected["dwm_only_count"], len(dwm_only))

    dwm_ids = {
        str(r.get("test_id") or "")
        for r in dwm_catalog.get("tests") or []
        if str(r.get("test_id") or "")
    }
    referenced = {
        str(dwm_id)
        for r in mapped_rows
        for dwm_id in r.get("dwm_test_ids") or []
    } | {
        str(r.get("dwm_test_id") or "")
        for r in dwm_only
        if str(r.get("dwm_test_id") or "")
    }
    missing_dwm = sorted(referenced - dwm_ids)
    _add(checks, "mapped_dwm_ids_exist", not missing_dwm,
         "all referenced DWM IDs exist", missing_dwm)

    policy_validation = validate_arkade5_coverage_policy(policy=policy)
    _add(checks, "coverage_policy_matches_gaps",
         policy_validation["valid"]
         and policy_validation["configured_gap_count"] == expected["policy_gap_count"],
         expected["policy_gap_count"], policy_validation)

    expected_version = str(contract["arkade_version"])
    versions = {
        "contract": contract.get("arkade_version"),
        "catalog": catalog.get("arkade_version"),
        "mapping": mapping.get("arkade_version"),
        "policy": policy.get("arkade_version"),
    }
    _add(checks, "arkade_version_consistency",
         all(str(v) == expected_version for v in versions.values()),
         expected_version, versions)

    expected_commit = str(contract["arkade_source_commit"])
    commits = {
        "contract": contract.get("arkade_source_commit"),
        "catalog": (catalog.get("source") or {}).get("commit"),
        "mapping": mapping.get("arkade_source_commit"),
        "policy": (policy.get("basis") or {}).get("arkade_source_commit"),
    }
    _add(checks, "arkade_source_commit_consistency",
         all(str(v) == expected_commit for v in commits.values()),
         expected_commit, commits)

    provenance_commits = {
        str((r.get("source_provenance") or {}).get("commit") or "")
        for r in catalog_tests
    }
    _add(checks, "catalog_test_provenance_commit",
         provenance_commits == {expected_commit},
         [expected_commit], sorted(provenance_commits))

    errors = [r for r in checks if r["status"] != "OK"]
    return {
        "format_version": 1,
        "health_model_id": "dwm.arkade5.integration-health.v1",
        "contract_id": contract.get("contract_id"),
        "scope": "repository_integration_integrity",
        "arkade_version": expected_version,
        "arkade_source_commit": expected_commit,
        "status": "OK" if not errors else "ERROR",
        "summary": {
            "checks": len(checks),
            "ok": len(checks) - len(errors),
            "errors": len(errors),
        },
        "checks": checks,
    }


def write_arkade5_integration_health(output_path: str | Path, *, repo_root=None) -> Path:
    result = build_arkade5_integration_health(repo_root=repo_root)
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8")
    return path
