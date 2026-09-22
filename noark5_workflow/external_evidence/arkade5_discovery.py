from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


@dataclass(frozen=True)
class Arkade5Candidate:
    path: Path
    test_date: str
    tests_run: int
    errors: int
    warnings: int
    sha256: str


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _looks_like_arkade5_report(path: Path) -> tuple[bool, dict]:
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return False, {}

    if not isinstance(data, dict):
        return False, {}

    summary = data.get("Summary")
    tests = data.get("TestsResults")
    if not isinstance(summary, dict) or not isinstance(tests, list):
        return False, {}

    if not tests:
        return False, {}

    for item in tests:
        if not isinstance(item, dict):
            return False, {}
        if not str(item.get("TestId") or "").startswith("N5."):
            return False, {}

    return True, data


def infer_job_root_from_depot_report(report_path: str | Path) -> Path:
    """Infer the extraction/job root from a depot report path.

    Typical current layout:
      <job root>/repository_operations/dwm/<run-subfolder>/noark5_reports/...

    We deliberately stop at repository_operations and search inside the job root,
    so historic Arkade 5 output can live in parallel folders.
    """
    path = Path(report_path).resolve()
    for ancestor in path.parents:
        if ancestor.name.casefold() == "repository_operations":
            return ancestor.parent
    raise ValueError("Kunne ikke finne jobbroten fra depotrapportens plassering.")


def discover_arkade5_reports(
    report_path: str | Path,
    *,
    max_files: int = 25000,
) -> list[Arkade5Candidate]:
    job_root = infer_job_root_from_depot_report(report_path)

    candidates: list[Arkade5Candidate] = []
    seen_sha: set[str] = set()
    scanned = 0

    for path in job_root.rglob("*.json"):
        scanned += 1
        if scanned > max_files:
            break

        # Never re-discover evidence already copied into DWM.
        parts = {part.casefold() for part in path.parts}
        if "external_evidence" in parts:
            continue

        ok, data = _looks_like_arkade5_report(path)
        if not ok:
            continue

        digest = _sha256(path)
        if digest in seen_sha:
            continue
        seen_sha.add(digest)

        summary = data.get("Summary") or {}
        try:
            tests_run = int(summary.get("NumberOfTestsRun") or 0)
        except (TypeError, ValueError):
            tests_run = 0
        try:
            errors = int(summary.get("NumberOfErrors") or 0)
        except (TypeError, ValueError):
            errors = 0
        try:
            warnings = int(summary.get("NumberOfWarnings") or 0)
        except (TypeError, ValueError):
            warnings = 0

        candidates.append(
            Arkade5Candidate(
                path=path,
                test_date=str(summary.get("DateOfTesting") or ""),
                tests_run=tests_run,
                errors=errors,
                warnings=warnings,
                sha256=digest,
            )
        )

    return sorted(
        candidates,
        key=lambda item: (item.test_date, str(item.path).casefold()),
        reverse=True,
    )
