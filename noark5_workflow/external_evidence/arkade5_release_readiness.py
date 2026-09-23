
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .arkade5_acceptance import build_arkade5_practical_acceptance
from .arkade5_integration_health import build_arkade5_integration_health


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _read_test_summary(path: Path) -> dict[str, int]:
    if not path.is_file():
        return {}
    values: dict[str, int] = {}
    for raw in path.read_text(encoding="utf-8-sig").splitlines():
        if "=" not in raw:
            continue
        key, value = raw.split("=", 1)
        key = key.strip().upper()
        try:
            values[key] = int(value.strip())
        except ValueError:
            continue
    return values


def build_v015_release_readiness(
    *,
    work_operations: str | Path,
    repo_root: str | Path | None = None,
    test_summary_path: str | Path | None = None,
) -> dict[str, Any]:
    """Aggregate the existing release checks for the Arkade 5 v0.1.5 work."""
    root = Path(repo_root) if repo_root is not None else _repo_root()
    summary_path = (
        Path(test_summary_path)
        if test_summary_path is not None
        else root / "docs/test-results/.last-test-summary.txt"
    )

    tests = _read_test_summary(summary_path)
    tests_ok = bool(tests) and tests.get("FAILED") == 0 and tests.get("ERRORS") == 0

    health = build_arkade5_integration_health(repo_root=root)
    acceptance = build_arkade5_practical_acceptance(
        work_operations=work_operations,
        repo_root=root,
    )

    gates = [
        {
            "gate_id": "full_test_suite",
            "status": "OK" if tests_ok else "BLOCKED",
            "detail": {
                "summary_file": str(summary_path),
                "total": tests.get("TOTAL"),
                "passed": tests.get("PASSED"),
                "failed": tests.get("FAILED"),
                "errors": tests.get("ERRORS"),
                "skipped": tests.get("SKIPPED"),
            },
        },
        {
            "gate_id": "arkade_integration_health",
            "status": "OK" if health.get("status") == "OK" else "BLOCKED",
            "detail": {
                "status": health.get("status"),
                "summary": health.get("summary"),
            },
        },
        {
            "gate_id": "arkade_practical_acceptance",
            "status": "OK" if acceptance.get("status") == "READY" else "BLOCKED",
            "detail": {
                "status": acceptance.get("status"),
                "summary": acceptance.get("summary"),
            },
        },
    ]

    blocked = [row for row in gates if row["status"] != "OK"]
    return {
        "format_version": 1,
        "release_readiness_model_id": "dwm.v0.1.5.arkade-release-readiness.v1",
        "target_release": "0.1.5",
        "status": (
            "READY_FOR_V0.1.5"
            if not blocked
            else "NOT_READY_FOR_V0.1.5"
        ),
        "summary": {
            "gates": len(gates),
            "ok": len(gates) - len(blocked),
            "blocked": len(blocked),
        },
        "gates": gates,
        "test_summary": tests,
        "arkade_integration_health": health,
        "arkade_practical_acceptance": acceptance,
    }


def write_v015_release_readiness(
    output_path: str | Path,
    *,
    work_operations: str | Path,
    repo_root: str | Path | None = None,
    test_summary_path: str | Path | None = None,
) -> Path:
    result = build_v015_release_readiness(
        work_operations=work_operations,
        repo_root=repo_root,
        test_summary_path=test_summary_path,
    )
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return path
