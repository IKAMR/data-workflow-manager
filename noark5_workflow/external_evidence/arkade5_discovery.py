
from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from .arkade5 import import_arkade5_report, list_arkade5_imports


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


def _candidate(path: Path, data: dict) -> Arkade5Candidate:
    summary = data.get("Summary") or {}

    def as_int(name: str) -> int:
        try:
            return int(summary.get(name) or 0)
        except (TypeError, ValueError):
            return 0

    return Arkade5Candidate(
        path=path.resolve(),
        test_date=str(summary.get("DateOfTesting") or ""),
        tests_run=as_int("NumberOfTestsRun"),
        errors=as_int("NumberOfErrors"),
        warnings=as_int("NumberOfWarnings"),
        sha256=_sha256(path),
    )


def infer_job_root_from_depot_report(report_path: str | Path) -> Path:
    """Infer the extraction/job root from a depot report path."""
    path = Path(report_path).resolve()
    for ancestor in path.parents:
        if ancestor.name.casefold() == "repository_operations":
            return ancestor.parent
    raise ValueError("Kunne ikke finne jobbroten fra depotrapportens plassering.")


def _is_inside_external_evidence(path: Path) -> bool:
    return "external_evidence" in {part.casefold() for part in path.parts}


def discover_arkade5_reports(
    report_path: str | Path,
    *,
    max_files: int = 25000,
) -> list[Arkade5Candidate]:
    """Established GUI/API: discover reports relative to one depot report.

    Kept backwards compatible for A11/A7 GUI and tests.
    """
    job_root = infer_job_root_from_depot_report(report_path)

    candidates: list[Arkade5Candidate] = []
    seen_sha: set[str] = set()
    scanned = 0

    for path in job_root.rglob("*.json"):
        scanned += 1
        if scanned > max_files:
            break

        if _is_inside_external_evidence(path):
            continue

        ok, data = _looks_like_arkade5_report(path)
        if not ok:
            continue

        digest = _sha256(path)
        if digest in seen_sha:
            continue
        seen_sha.add(digest)
        candidates.append(_candidate(path, data))

    return sorted(
        candidates,
        key=lambda item: (item.test_date, str(item.path).casefold()),
        reverse=True,
    )


_PRUNE_DIRS = {
    ".git",
    "__pycache__",
    "content",
    "aip",
    "external_evidence",
}


def _walk_report_candidates(
    root: Path,
    *,
    max_depth: int,
    prune_heavy: bool,
) -> Iterable[Path]:
    root = Path(root)
    if not root.is_dir():
        return

    root_depth = len(root.parts)
    for current, dirs, files in os.walk(root):
        current_path = Path(current)

        # Never re-discover DWM's preserved copies.
        if _is_inside_external_evidence(current_path):
            dirs[:] = []
            continue

        depth = len(current_path.parts) - root_depth
        if depth >= max_depth:
            dirs[:] = []
        else:
            dirs[:] = [
                name
                for name in dirs
                if name.casefold() != "external_evidence"
                and (
                    not prune_heavy
                    or name.casefold() not in _PRUNE_DIRS
                )
            ]

        for name in files:
            if not name.casefold().endswith(".json"):
                continue
            path = current_path / name
            if _is_inside_external_evidence(path):
                continue

            # Keep the automatic scan cheap. Validate all plausible JSON names.
            lower = name.casefold()
            if not (
                lower.startswith("arkade-testrapport")
                or "arkade" in lower
                or current_path.name.casefold().startswith("arkade-testrapporter")
            ):
                continue
            yield path


def discover_arkade5_reports_in_roots(
    *,
    work_operations: str | Path | None,
    work_root: str | Path | None,
    source_root: str | Path | None,
    configured_roots: Iterable[str | Path] = (),
) -> list[Arkade5Candidate]:
    """Automatic workflow discovery, independent of a depot-report path."""
    roots: list[tuple[Path, int, bool]] = []

    def add(value, max_depth: int, prune: bool) -> None:
        if value is None:
            return
        path = Path(value)
        key = str(path).casefold()
        if any(str(existing[0]).casefold() == key for existing in roots):
            return
        roots.append((path, max_depth, prune))

    # Effective work area first.
    add(work_operations, 6, False)
    # Job root is the most useful place for Arkade reports stored beside DWM.
    add(work_root, 5, True)
    # Source root may equal job root in some layouts; scan conservatively.
    add(source_root, 4, True)
    # Explicit user/configured roots are trusted search anchors.
    for value in configured_roots:
        text = str(value or "").strip()
        if text:
            add(Path(text), 8, False)

    candidates: list[Arkade5Candidate] = []
    seen_sha: set[str] = set()

    for root, max_depth, prune in roots:
        for path in _walk_report_candidates(
            root,
            max_depth=max_depth,
            prune_heavy=prune,
        ) or ():
            ok, data = _looks_like_arkade5_report(path)
            if not ok:
                continue
            digest = _sha256(path)
            if digest in seen_sha:
                continue
            seen_sha.add(digest)
            candidates.append(_candidate(path, data))

    return sorted(
        candidates,
        key=lambda item: (item.test_date, str(item.path).casefold()),
        reverse=True,
    )


def import_discovered_arkade5_reports(
    *,
    work_operations: str | Path,
    work_root: str | Path | None = None,
    source_root: str | Path | None = None,
    configured_roots: Iterable[str | Path] = (),
    imported_by: dict[str, str] | None = None,
) -> dict:
    work = Path(work_operations)
    candidates = discover_arkade5_reports_in_roots(
        work_operations=work,
        work_root=work_root,
        source_root=source_root,
        configured_roots=configured_roots,
    )

    existing = list_arkade5_imports(work)
    existing_sha = {
        str((row.get("source") or {}).get("sha256") or "").casefold()
        for row in existing
    } - {""}

    imported = []
    skipped = []
    failed = []

    for candidate in candidates:
        digest = candidate.sha256
        if digest.casefold() in existing_sha:
            skipped.append({
                "file": str(candidate.path),
                "reason": "already_imported",
                "sha256": digest,
            })
            continue

        try:
            manifest = import_arkade5_report(
                candidate.path,
                work_operations=work,
                imported_by=imported_by,
            )
            imported.append({
                "file": str(candidate.path),
                "import_id": manifest.get("import_id"),
                "sha256": digest,
            })
            existing_sha.add(digest.casefold())
        except Exception as exc:
            failed.append({
                "file": str(candidate.path),
                "error": str(exc),
            })

    return {
        "found": len(candidates),
        "imported": len(imported),
        "skipped": len(skipped),
        "failed": len(failed),
        "imports": imported,
        "skipped_files": skipped,
        "failed_files": failed,
        "search_roots": {
            "work_operations": str(work_operations) if work_operations else None,
            "work_root": str(work_root) if work_root else None,
            "source_root": str(source_root) if source_root else None,
            "configured_roots": [str(value) for value in configured_roots],
        },
    }
