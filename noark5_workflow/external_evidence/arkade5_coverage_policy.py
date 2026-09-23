
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .arkade5_gap_analysis import build_gap_overlap_analysis


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _policy_path() -> Path:
    return (
        _repo_root()
        / "config"
        / "noark5"
        / "external"
        / "arkade5_coverage_policy.json"
    )


def load_arkade5_coverage_policy() -> dict[str, Any]:
    return json.loads(_policy_path().read_text(encoding="utf-8"))


def validate_arkade5_coverage_policy(
    policy: dict[str, Any] | None = None,
    gap_analysis: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Validate that the current policy matches documented Arkade-only gaps."""
    policy = policy or load_arkade5_coverage_policy()
    gap_analysis = gap_analysis or build_gap_overlap_analysis()

    expected = set(gap_analysis.get("dwm_gaps_covered_by_arkade") or [])
    rows = policy.get("documented_dwm_gaps") or []
    configured = {
        str(row.get("arkade_test_id") or "").upper()
        for row in rows
        if str(row.get("arkade_test_id") or "").strip()
    }

    invalid_strategy = sorted(
        str(row.get("arkade_test_id") or "")
        for row in rows
        if row.get("current_coverage_strategy") != "use_arkade_external"
        or row.get("dwm_internal_implementation") != "deferred"
    )

    return {
        "valid": (
            configured == expected
            and not invalid_strategy
            and len(configured) == len(rows)
        ),
        "expected_gap_count": len(expected),
        "configured_gap_count": len(configured),
        "missing_from_policy": sorted(expected - configured),
        "extra_in_policy": sorted(configured - expected),
        "invalid_strategy": invalid_strategy,
    }
