from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path


_ARCHIVE_STRUCTURE_NAME = "arkivstruktur.xml"
_DOCUMENT_DIR_NAMES = {"dokument", "dokumenter"}


@dataclass(frozen=True)
class Noark5ExtractionCandidate:
    root: Path
    archive_structure: Path
    document_dir: Path


@dataclass(frozen=True)
class Noark5DiscoveryResult:
    start_root: Path
    candidates: tuple[Noark5ExtractionCandidate, ...]
    scanned_directories: int
    errors: tuple[str, ...] = ()

    @property
    def roots(self) -> tuple[Path, ...]:
        return tuple(candidate.root for candidate in self.candidates)


def _casefold_name(value: str) -> str:
    return value.casefold()


def discover_noark5_extractions(start_root: Path | str) -> Noark5DiscoveryResult:
    """Recursively discover Noark 5 extraction roots below *start_root*.

    A directory is accepted as one extraction root when it contains:

    * ``arkivstruktur.xml`` (case-insensitive file-name comparison), and
    * a direct child directory named ``DOKUMENT`` or ``DOKUMENTER``
      (case-insensitive comparison).

    Document payload directories are deliberately pruned from traversal. They
    can be very large and cannot themselves be an extraction root for this
    discovery contract.
    """

    start = Path(start_root).expanduser()
    if not start.is_dir():
        raise NotADirectoryError(str(start))

    candidates: list[Noark5ExtractionCandidate] = []
    errors: list[str] = []
    scanned = 0

    def onerror(error: OSError) -> None:
        location = getattr(error, "filename", None) or "?"
        errors.append(f"{location}: {error}")

    for dirpath, dirnames, filenames in os.walk(start, topdown=True, onerror=onerror):
        scanned += 1
        root = Path(dirpath)

        document_names = [
            name for name in dirnames
            if _casefold_name(name) in _DOCUMENT_DIR_NAMES
        ]
        archive_names = [
            name for name in filenames
            if _casefold_name(name) == _ARCHIVE_STRUCTURE_NAME
        ]

        if archive_names and document_names:
            archive_name = sorted(archive_names, key=str.casefold)[0]
            document_name = sorted(document_names, key=str.casefold)[0]
            candidates.append(
                Noark5ExtractionCandidate(
                    root=root,
                    archive_structure=root / archive_name,
                    document_dir=root / document_name,
                )
            )

        # Never descend into document payload. Besides being unnecessary for
        # discovery this prevents very large document trees from dominating a
        # recursive search on file servers.
        dirnames[:] = [
            name for name in dirnames
            if _casefold_name(name) not in _DOCUMENT_DIR_NAMES
        ]

    candidates.sort(key=lambda item: os.path.normcase(str(item.root)))
    return Noark5DiscoveryResult(
        start_root=start,
        candidates=tuple(candidates),
        scanned_directories=scanned,
        errors=tuple(errors),
    )
