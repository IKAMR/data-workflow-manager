"""Bounded, read-only discovery of known DWM depot report files."""
from __future__ import annotations

from pathlib import Path

REPORT_NAMES = ("depot_validation_report.html", "depot_validation_report.pdf", "index.html")


def latest_depot_report(effective_work_operations: str | Path | None) -> Path | None:
    if effective_work_operations is None:
        return None
    root = Path(effective_work_operations) / "noark5_reports" / "depot_validation"
    if not root.is_dir():
        return None
    # Only one known report area; never walk Source or DOKUMENT.
    choices = []
    try:
        for directory in root.iterdir():
            if not directory.is_dir():
                continue
            for filename in REPORT_NAMES:
                file = directory / filename
                if file.is_file():
                    choices.append(file)
                    break
    except OSError:
        return None
    if not choices:
        return None
    try:
        return max(choices, key=lambda p: (p.stat().st_mtime_ns, str(p)))
    except OSError:
        return None
