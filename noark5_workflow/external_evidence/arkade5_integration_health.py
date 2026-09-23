
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

from .arkade5_coverage_policy import validate_arkade5_coverage_policy


EXPECTED_BASE_VERSION = "2.13.0"
EXPECTED_BASE_COMMIT = "40a32ee0ae84ddf44d1f3c35f1860567ca262733"
EXPECTED_CURRENT_VERSION = "2.13.1"
EXPECTED_CURRENT_COMMIT = "b27136ede491d3ec8b9e0ec9973ba455a0febbdf"
EXPECTED_RUNTIME_AFFECTED = {
    "N5.28", "N5.30", "N5.32", "N5.33", "N5.64"
}
EXPECTED_INSPECTED_NOT_AFFECTED = {"N5.29", "N5.34"}


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _add(checks, check_id, ok, expected=None, actual=None, detail=""):
    checks.append({
        "check_id": check_id,
        "status": "OK" if ok else "ERROR",
        "expected": expected,
        "actual": actual,
        "detail": detail,
    })


def build_arkade5_integration_health(
    *,
    repo_root: str | Path | None = None,
) -> dict[str, Any]:
    root = Path(repo_root) if repo_root is not None else _repo_root()

    contract = _read_json(
        root / "config/noark5/external/arkade5_integration_contract.json"
    )
    expected = contract["expected"]
    catalog = _read_json(
        root / "config/noark5/external/arkade5_test_catalog.json"
    )
    mapping = _read_json(
        root / "config/noark5/external/dwm_arkade5_mapping.json"
    )
    policy = _read_json(
        root / "config/noark5/external/arkade5_coverage_policy.json"
    )
    release_delta = _read_json(
        root / "config/noark5/external/arkade5_release_delta_2_13_1.json"
    )
    dwm_catalog = _read_json(
        root / "config/noark5/tests/xpath_catalog_2026_05_26.json"
    )
    profile = _read_json(root / "config/noark5/profile.json")

    checks = []

    required_files = list(contract.get("required_files") or [])
    required_files.extend([
        "config/noark5/external/arkade5_release_delta_2_13_1.json",
        "docs/ARKADE5-V2.13.1-CHANGE-IMPACT.md",
    ])
    missing_files = sorted(
        rel for rel in dict.fromkeys(required_files)
        if not (root / rel).is_file()
    )
    _add(
        checks, "required_files", not missing_files,
        "all required files exist", missing_files
    )

    profile_paths = set()
    for values in (profile.get("definitions") or {}).values():
        if isinstance(values, list):
            profile_paths.update(str(v) for v in values)
    profile_paths.update(str(v) for v in profile.get("documentation") or [])
    required_profile_paths = {
        "config/noark5/external/arkade5_release_delta_2_13_1.json",
        "docs/ARKADE5-V2.13.1-CHANGE-IMPACT.md",
    }
    missing_profile = sorted(required_profile_paths - profile_paths)
    _add(
        checks, "profile_discoverability", not missing_profile,
        "v2.13.1 release delta discoverable from profile", missing_profile
    )

    catalog_tests = catalog.get("tests") or []
    catalog_ids = [
        str(row.get("arkade_test_id") or "").upper()
        for row in catalog_tests
    ]
    _add(
        checks, "arkade_catalog_count",
        len(catalog_ids) == expected["arkade_test_count"],
        expected["arkade_test_count"], len(catalog_ids)
    )
    _add(
        checks, "arkade_catalog_unique_ids",
        len(catalog_ids) == len(set(catalog_ids)),
        expected["arkade_test_count"], len(set(catalog_ids))
    )

    mapped_rows = mapping.get("arkade_to_dwm") or []
    mapped_ids = [
        str(row.get("arkade_test_id") or "").upper()
        for row in mapped_rows
    ]
    _add(
        checks,
        "mapping_has_one_row_per_arkade_test",
        len(mapped_ids) == expected["arkade_test_count"]
        and len(mapped_ids) == len(set(mapped_ids))
        and set(mapped_ids) == set(catalog_ids),
        sorted(catalog_ids),
        sorted(mapped_ids),
    )

    relation_counts = Counter(
        str(row.get("relation") or row.get("coverage") or "")
        for row in mapped_rows
    )
    _add(
        checks, "mapping_relation_counts",
        dict(relation_counts) == expected["relations"],
        expected["relations"], dict(relation_counts)
    )

    dwm_only = mapping.get("dwm_only") or []
    _add(
        checks, "dwm_only_count",
        len(dwm_only) == expected["dwm_only_count"],
        expected["dwm_only_count"], len(dwm_only)
    )

    dwm_ids = {
        str(row.get("test_id") or "")
        for row in dwm_catalog.get("tests") or []
        if str(row.get("test_id") or "")
    }
    referenced = {
        str(dwm_id)
        for row in mapped_rows
        for dwm_id in row.get("dwm_test_ids") or []
    } | {
        str(row.get("dwm_test_id") or "")
        for row in dwm_only
        if str(row.get("dwm_test_id") or "")
    }
    missing_dwm = sorted(referenced - dwm_ids)
    _add(
        checks, "mapped_dwm_ids_exist", not missing_dwm,
        "all referenced DWM IDs exist", missing_dwm
    )

    policy_validation = validate_arkade5_coverage_policy(policy=policy)
    _add(
        checks, "coverage_policy_matches_gaps",
        policy_validation["valid"]
        and policy_validation["configured_gap_count"]
        == expected["policy_gap_count"],
        expected["policy_gap_count"], policy_validation
    )

    base_versions = {
        "contract": contract.get("arkade_version"),
        "catalog": catalog.get("arkade_version"),
        "mapping": mapping.get("arkade_version"),
        "policy": policy.get("arkade_version"),
    }
    _add(
        checks, "arkade_version_consistency",
        all(str(v) == EXPECTED_BASE_VERSION for v in base_versions.values()),
        EXPECTED_BASE_VERSION, base_versions
    )

    base_commits = {
        "contract": contract.get("arkade_source_commit"),
        "catalog": (catalog.get("source") or {}).get("commit"),
        "mapping": mapping.get("arkade_source_commit"),
        "policy": (policy.get("basis") or {}).get("arkade_source_commit"),
    }
    _add(
        checks, "arkade_source_commit_consistency",
        all(str(v) == EXPECTED_BASE_COMMIT for v in base_commits.values()),
        EXPECTED_BASE_COMMIT, base_commits
    )

    provenance_commits = {
        str((row.get("source_provenance") or {}).get("commit") or "")
        for row in catalog_tests
    }
    _add(
        checks, "catalog_test_provenance_commit",
        provenance_commits == {EXPECTED_BASE_COMMIT},
        [EXPECTED_BASE_COMMIT], sorted(provenance_commits)
    )

    runtime_affected = set(
        release_delta.get("runtime_affected_test_ids") or []
    )
    inspected_not_affected = set(
        release_delta.get("inspected_not_runtime_affected_test_ids") or []
    )
    _add(
        checks, "v2131_release_delta",
        release_delta.get("current_arkade_version")
        == EXPECTED_CURRENT_VERSION
        and release_delta.get("current_arkade_commit")
        == EXPECTED_CURRENT_COMMIT
        and release_delta.get("noark5_test_implementations_changed") == 0
        and release_delta.get("semantic_catalog_changed") is False
        and release_delta.get("mapping_changed") is False,
        {
            "version": EXPECTED_CURRENT_VERSION,
            "commit": EXPECTED_CURRENT_COMMIT,
            "test_implementations_changed": 0,
        },
        {
            "version": release_delta.get("current_arkade_version"),
            "commit": release_delta.get("current_arkade_commit"),
            "test_implementations_changed":
                release_delta.get("noark5_test_implementations_changed"),
        },
    )
    _add(
        checks, "v2131_runtime_affected_tests",
        runtime_affected == EXPECTED_RUNTIME_AFFECTED,
        sorted(EXPECTED_RUNTIME_AFFECTED), sorted(runtime_affected)
    )
    _add(
        checks, "v2131_inspected_not_affected_tests",
        inspected_not_affected == EXPECTED_INSPECTED_NOT_AFFECTED,
        sorted(EXPECTED_INSPECTED_NOT_AFFECTED),
        sorted(inspected_not_affected)
    )

    errors = [row for row in checks if row["status"] != "OK"]
    return {
        "format_version": 2,
        "health_model_id": "dwm.arkade5.integration-health.v2",
        "contract_id": contract.get("contract_id"),
        "scope": "repository_integration_integrity",
        # Preserve a12 contract fields for backwards compatibility.
        "arkade_version": EXPECTED_BASE_VERSION,
        "arkade_source_commit": EXPECTED_BASE_COMMIT,
        "current_arkade_version": EXPECTED_CURRENT_VERSION,
        "current_arkade_source_commit": EXPECTED_CURRENT_COMMIT,
        "status": "OK" if not errors else "ERROR",
        "summary": {
            "checks": len(checks),
            "ok": len(checks) - len(errors),
            "errors": len(errors),
        },
        "release_delta": release_delta,
        "checks": checks,
    }


def write_arkade5_integration_health(
    output_path: str | Path,
    *,
    repo_root=None,
) -> Path:
    result = build_arkade5_integration_health(repo_root=repo_root)
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return path
