from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path, PureWindowsPath
import re
from typing import Iterable


INDICATOR_FILES = {
    "arkivstruktur.xml",
    "arkivuttrekk.xml",
    "loependejournal.xml",
    "offentligjournal.xml",
    "endringslogg.xml",
}

EXCLUDED_COMPONENTS = {
    "repository_operations",
    "schema",
    "_debug",
    "_work",
    "_test",
    "_temp",
    "report",
    "reports",
}

_DIR_RE = re.compile(
    r"^\s*(?:New Dir|Existing Dir|\*EXTRA Dir)\s+\d+\s+(.+?)\s*$",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class DiscoveredSource:
    path: Path
    suggested_name: str
    confidence: str
    evidence: tuple[str, ...]
    origin: str

    @property
    def safe_default(self) -> bool:
        return self.confidence == "Sikker"


def _decode_robocopy_log(path: Path) -> str:
    data = Path(path).read_bytes()
    if data.startswith((b"\xff\xfe", b"\xfe\xff")):
        return data.decode("utf-16")
    for encoding in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace")


def _normalise_windows_path(raw: str) -> str:
    value = raw.strip().strip('"')
    while len(value) > 3 and value.endswith(("\\", "/")):
        value = value[:-1]
    return value


def _is_excluded(raw_path: str) -> bool:
    parts = [part.casefold() for part in PureWindowsPath(raw_path).parts]
    for part in parts:
        if part in EXCLUDED_COMPONENTS:
            return True
        if part.startswith("arkade5_"):
            return True
    return False


def _suggested_name(raw_path: str) -> str:
    path = PureWindowsPath(raw_path)
    if path.name.casefold() == "avleveringspakke" and path.parent.name:
        return path.parent.name

    lowered = [part.casefold() for part in path.parts]
    if len(lowered) >= 3 and lowered[-3:] == ["content", "sip", "content"]:
        parents = list(path.parents)
        if len(parents) >= 3 and parents[2].name:
            return parents[2].name

    return path.name or raw_path


def _confidence(files: set[str]) -> str:
    if {"arkivstruktur.xml", "arkivuttrekk.xml"} <= files:
        return "Sikker"
    if "arkivstruktur.xml" in files and (
        "loependejournal.xml" in files or "offentligjournal.xml" in files
    ):
        return "Sannsynlig"
    return "Kontroller"


def discover_from_robocopy_text(
    text: str,
    *,
    origin: str = "Robocopy-logg",
) -> list[DiscoveredSource]:
    current_dir: str | None = None
    files_by_dir: dict[str, set[str]] = {}

    for raw_line in text.splitlines():
        match = _DIR_RE.match(raw_line)
        if match:
            current_dir = _normalise_windows_path(match.group(1))
            files_by_dir.setdefault(current_dir, set())
            continue

        if current_dir is None:
            continue

        lowered = raw_line.strip().casefold()
        for filename in INDICATOR_FILES:
            if lowered.endswith(filename):
                files_by_dir[current_dir].add(filename)
                break

    found: list[DiscoveredSource] = []
    for raw_path, files in files_by_dir.items():
        if "arkivstruktur.xml" not in files:
            continue
        if _is_excluded(raw_path):
            continue

        found.append(
            DiscoveredSource(
                path=Path(raw_path),
                suggested_name=_suggested_name(raw_path),
                confidence=_confidence(files),
                evidence=tuple(sorted(files)),
                origin=origin,
            )
        )

    found.sort(key=lambda item: str(item.path).casefold())
    return found


def discover_from_robocopy_log(path: Path) -> list[DiscoveredSource]:
    path = Path(path)
    return discover_from_robocopy_text(
        _decode_robocopy_log(path),
        origin=path.name,
    )


def discover_from_robocopy_logs(paths: Iterable[Path]) -> list[DiscoveredSource]:
    by_path: dict[str, DiscoveredSource] = {}
    rank = {"Kontroller": 0, "Sannsynlig": 1, "Sikker": 2}

    for path in paths:
        for candidate in discover_from_robocopy_log(Path(path)):
            key = str(candidate.path).replace("/", "\\").rstrip("\\").casefold()
            previous = by_path.get(key)
            if previous is None or rank[candidate.confidence] > rank[previous.confidence]:
                by_path[key] = candidate

    return sorted(by_path.values(), key=lambda item: str(item.path).casefold())
