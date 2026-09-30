from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
import re
from typing import Iterable


_DEFAULT_DEFINITION_PATH = (
    Path(__file__).resolve().parents[1] / "config" / "extraction_types.json"
)
_WINDOWS_ABSOLUTE_RE = re.compile(r"(?i)(?:[A-Z]:[\\/][^\r\n\t\"]+|\\\\[^\r\n\t\"]+)")


@dataclass(frozen=True)
class ExtractionTypeDefinition:
    type_id: str
    label: str
    profile_id: str
    candidate_kind: str
    case_sensitive: bool
    match: dict
    prune_directories: tuple[str, ...]
    list_reader: str
    job_name: str = "name"
    source_root_rule: dict | None = None


@dataclass(frozen=True)
class ExtractionCandidate:
    path: Path
    type_id: str
    label: str
    profile_id: str
    suggested_name: str
    evidence: tuple[str, ...] = ()
    origin: str = ""
    source_root_hint: Path | None = None


@dataclass(frozen=True)
class ExtractionDiscoveryResult:
    definition: ExtractionTypeDefinition
    source_kind: str
    source_label: str
    candidates: tuple[ExtractionCandidate, ...]
    scanned_directories: int = 0
    errors: tuple[str, ...] = ()


class ExtractionDefinitionError(ValueError):
    pass


def load_extraction_definitions(
    path: Path | str | None = None,
) -> tuple[ExtractionTypeDefinition, ...]:
    definition_path = Path(path) if path is not None else _DEFAULT_DEFINITION_PATH
    payload = json.loads(definition_path.read_text(encoding="utf-8"))
    if int(payload.get("schema_version", 0)) != 1:
        raise ExtractionDefinitionError("Ukjent schema_version for extraction_types.json")

    result: list[ExtractionTypeDefinition] = []
    seen: set[str] = set()
    for raw in payload.get("extraction_types", []):
        type_id = str(raw.get("id", "")).strip()
        label = str(raw.get("label", "")).strip()
        candidate_kind = str(raw.get("candidate_kind", "")).strip().lower()
        if not type_id or not label:
            raise ExtractionDefinitionError("Uttrekkstype mangler id eller label")
        if type_id in seen:
            raise ExtractionDefinitionError(f"Duplikat uttrekkstype: {type_id}")
        if candidate_kind not in {"directory", "file"}:
            raise ExtractionDefinitionError(
                f"{type_id}: candidate_kind må være directory eller file"
            )
        seen.add(type_id)
        result.append(
            ExtractionTypeDefinition(
                type_id=type_id,
                label=label,
                profile_id=str(raw.get("profile_id", type_id) or type_id),
                candidate_kind=candidate_kind,
                case_sensitive=bool(raw.get("case_sensitive", False)),
                match=dict(raw.get("match") or {}),
                prune_directories=tuple(str(v) for v in raw.get("prune_directories", [])),
                list_reader=str(raw.get("list_reader", "path_lines") or "path_lines"),
                job_name=str(raw.get("job_name", "name") or "name"),
                source_root_rule=dict(raw.get("source_root") or {}),
            )
        )
    return tuple(result)


def extraction_definition(
    type_id: str,
    definitions: Iterable[ExtractionTypeDefinition] | None = None,
) -> ExtractionTypeDefinition:
    for item in definitions or load_extraction_definitions():
        if item.type_id == type_id:
            return item
    raise KeyError(type_id)


def _norm(value: str, *, case_sensitive: bool) -> str:
    return value if case_sensitive else value.casefold()


def _suggested_name(path: Path, definition: ExtractionTypeDefinition) -> str:
    if definition.job_name == "stem" and path.name:
        return path.stem
    if definition.job_name == "parent_name" and path.parent.name:
        return path.parent.name
    return path.name or str(path)




def _source_root_hint(
    path: Path,
    definition: ExtractionTypeDefinition,
    *,
    search_root: Path | None = None,
) -> Path:
    """Return a data-driven source-root hint without changing the extraction path.

    The rule belongs to the extraction definition so the generic discovery engine
    does not hard-code Noark 5 or SIARD layouts.
    """
    rule = definition.source_root_rule or {}
    strategy = str(rule.get("strategy", "parent") or "parent").strip().lower()

    if strategy == "search_root" and search_root is not None:
        return search_root

    if strategy == "ancestor_before_sequence":
        sequence = [str(v) for v in rule.get("sequence", []) if str(v)]
        if sequence:
            parts = list(path.parts)
            hay = [v if definition.case_sensitive else v.casefold() for v in parts]
            needle = [v if definition.case_sensitive else v.casefold() for v in sequence]
            for i in range(0, len(hay) - len(needle) + 1):
                if hay[i:i + len(needle)] == needle:
                    prefix = parts[:i]
                    if prefix:
                        return Path(*prefix)
        fallback = str(rule.get("fallback", "parent") or "parent").lower()
        if fallback == "search_root" and search_root is not None:
            return search_root

    if definition.candidate_kind == "file":
        return path.parent
    return path.parent


def _directory_matches(
    filenames: Iterable[str],
    dirnames: Iterable[str],
    definition: ExtractionTypeDefinition,
) -> tuple[bool, tuple[str, ...]]:
    files = {_norm(v, case_sensitive=definition.case_sensitive) for v in filenames}
    dirs = {_norm(v, case_sensitive=definition.case_sensitive) for v in dirnames}
    required_files = [
        _norm(str(v), case_sensitive=definition.case_sensitive)
        for v in definition.match.get("required_files_all", [])
    ]
    required_dirs_any = [
        _norm(str(v), case_sensitive=definition.case_sensitive)
        for v in definition.match.get("required_directories_any", [])
    ]
    if any(value not in files for value in required_files):
        return False, ()
    if required_dirs_any and not any(value in dirs for value in required_dirs_any):
        return False, ()
    evidence = tuple(required_files + [v for v in required_dirs_any if v in dirs])
    return True, evidence


def _file_matches(path: Path, definition: ExtractionTypeDefinition) -> bool:
    extensions = [str(v) for v in definition.match.get("extensions", [])]
    if not extensions:
        return False
    suffix = path.suffix if definition.case_sensitive else path.suffix.casefold()
    allowed = {
        ext if definition.case_sensitive else ext.casefold()
        for ext in extensions
    }
    return suffix in allowed


def discover_in_folders(
    start_root: Path | str,
    definition: ExtractionTypeDefinition,
) -> ExtractionDiscoveryResult:
    start = Path(start_root).expanduser()
    if not start.is_dir():
        raise NotADirectoryError(str(start))

    candidates: list[ExtractionCandidate] = []
    errors: list[str] = []
    scanned = 0
    prune = {
        _norm(v, case_sensitive=definition.case_sensitive)
        for v in definition.prune_directories
    }

    def onerror(error: OSError) -> None:
        errors.append(f"{getattr(error, 'filename', None) or '?'}: {error}")

    for dirpath, dirnames, filenames in os.walk(start, topdown=True, onerror=onerror):
        scanned += 1
        root = Path(dirpath)
        if definition.candidate_kind == "directory":
            matches, evidence = _directory_matches(filenames, dirnames, definition)
            if matches:
                candidates.append(
                    ExtractionCandidate(
                        path=root,
                        type_id=definition.type_id,
                        label=definition.label,
                        profile_id=definition.profile_id,
                        suggested_name=_suggested_name(root, definition),
                        evidence=evidence,
                        origin=str(start),
                        source_root_hint=_source_root_hint(root, definition, search_root=start),
                    )
                )
        else:
            for filename in filenames:
                candidate_path = root / filename
                if _file_matches(candidate_path, definition):
                    candidates.append(
                        ExtractionCandidate(
                            path=candidate_path,
                            type_id=definition.type_id,
                            label=definition.label,
                            profile_id=definition.profile_id,
                            suggested_name=_suggested_name(candidate_path, definition),
                            evidence=(candidate_path.suffix,),
                            origin=str(start),
                            source_root_hint=_source_root_hint(candidate_path, definition, search_root=start),
                        )
                    )

        if prune:
            dirnames[:] = [
                value
                for value in dirnames
                if _norm(value, case_sensitive=definition.case_sensitive) not in prune
            ]

    candidates.sort(key=lambda item: os.path.normcase(str(item.path)))
    return ExtractionDiscoveryResult(
        definition=definition,
        source_kind="folders",
        source_label=str(start),
        candidates=tuple(candidates),
        scanned_directories=scanned,
        errors=tuple(errors),
    )


def _decode_text_file(path: Path) -> str:
    data = path.read_bytes()
    if data.startswith((b"\xff\xfe", b"\xfe\xff")):
        return data.decode("utf-16")
    for encoding in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            pass
    return data.decode("utf-8", errors="replace")


def _paths_from_lines(path: Path) -> list[Path]:
    found: list[Path] = []
    for line in _decode_text_file(path).splitlines():
        stripped = line.strip().strip('"')
        if not stripped:
            continue
        direct = Path(stripped)
        if direct.exists():
            found.append(direct)
            continue
        for match in _WINDOWS_ABSOLUTE_RE.findall(line):
            found.append(Path(match.rstrip(" \\t")))
    return found


def discover_from_lists(
    list_files: Iterable[Path | str],
    definition: ExtractionTypeDefinition,
) -> ExtractionDiscoveryResult:
    paths = tuple(Path(value) for value in list_files)
    if definition.list_reader == "robocopy_noark5":
        # Compatibility adapter. The generic discovery UI/contract does not
        # know Noark-specific log syntax; that syntax remains isolated in the
        # existing plugin adapter that already handles Robocopy /L correctly.
        from noark5_workflow.plugins.noark5.discovery import discover_from_robocopy_logs

        raw = discover_from_robocopy_logs(paths)
        candidates = tuple(
            ExtractionCandidate(
                path=Path(item.path),
                type_id=definition.type_id,
                label=definition.label,
                profile_id=definition.profile_id,
                suggested_name=str(item.suggested_name),
                evidence=tuple(item.evidence),
                origin=str(item.origin),
                source_root_hint=_source_root_hint(Path(item.path), definition),
            )
            for item in raw
        )
        return ExtractionDiscoveryResult(
            definition=definition,
            source_kind="lists",
            source_label=", ".join(path.name for path in paths),
            candidates=candidates,
        )

    if definition.list_reader != "path_lines":
        raise ExtractionDefinitionError(
            f"Ukjent list_reader for {definition.type_id}: {definition.list_reader}"
        )

    unique: dict[str, ExtractionCandidate] = {}
    for list_path in paths:
        for candidate_path in _paths_from_lines(list_path):
            if definition.candidate_kind == "file":
                if not _file_matches(candidate_path, definition):
                    continue
                accepted = candidate_path
            else:
                accepted = candidate_path
                if accepted.is_file():
                    accepted = accepted.parent
                if accepted.exists() and accepted.is_dir():
                    try:
                        names = list(accepted.iterdir())
                    except OSError:
                        continue
                    filenames = [p.name for p in names if p.is_file()]
                    dirnames = [p.name for p in names if p.is_dir()]
                    matches, _evidence = _directory_matches(filenames, dirnames, definition)
                    if not matches:
                        continue
            key = os.path.normcase(os.path.abspath(os.fspath(accepted)))
            unique[key] = ExtractionCandidate(
                path=accepted,
                type_id=definition.type_id,
                label=definition.label,
                profile_id=definition.profile_id,
                suggested_name=_suggested_name(accepted, definition),
                evidence=("path_lines",),
                origin=list_path.name,
                source_root_hint=_source_root_hint(accepted, definition),
            )

    return ExtractionDiscoveryResult(
        definition=definition,
        source_kind="lists",
        source_label=", ".join(path.name for path in paths),
        candidates=tuple(sorted(unique.values(), key=lambda item: str(item.path).casefold())),
    )
