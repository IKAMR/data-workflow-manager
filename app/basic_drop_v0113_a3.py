"""Local drag-and-drop routing for the existing Basic file/folder controls."""
from __future__ import annotations

from pathlib import Path


def classify_basic_drop(path: str | Path, target: str) -> tuple[str, Path]:
    """Return (action, path) for one local item; reject unsuitable drops."""
    if target not in {"source", "work", "joblist", "info"}:
        raise ValueError("Ukjent felt")
    candidate = Path(path)
    if candidate.is_file():
        suffix = candidate.suffix.casefold()
        if suffix == ".xml" and target in {"source", "info"}:
            if candidate.stat().st_size > 8_000_000:
                raise ValueError("info.xml er større enn 8 MB")
            return "info", candidate
        if suffix == ".n5jobs" and target == "joblist":
            return "joblist", candidate
        raise ValueError("Feil filtype for feltet")
    if candidate.is_dir():
        if target == "work":
            return "work", candidate
        if target == "source":
            return "source", candidate
        raise ValueError("Dette feltet tar imot en fil")
    raise ValueError("Filen eller mappen finnes ikke")
