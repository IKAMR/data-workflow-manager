from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFINITION_PATH = ROOT / "config" / "storage_layouts.json"


@dataclass(frozen=True)
class StorageLayout:
    layout_id: str
    label: str
    description: str
    match: dict[str, Any]
    roles: dict[str, str]


def load_storage_layouts(path: Path = DEFINITION_PATH) -> list[StorageLayout]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    return [
        StorageLayout(
            layout_id=str(item["id"]),
            label=str(item["label"]),
            description=str(item.get("description", "")),
            match=dict(item.get("match", {})),
            roles=dict(item.get("roles", {})),
        )
        for item in payload.get("profiles", [])
    ]


def storage_layout_by_id(layout_id: str | None) -> StorageLayout:
    layouts = load_storage_layouts()
    wanted = str(layout_id or "none")
    for layout in layouts:
        if layout.layout_id == wanted:
            return layout
    return next(layout for layout in layouts if layout.layout_id == "none")


def storage_layout_labels() -> dict[str, str]:
    return {layout.layout_id: layout.label for layout in load_storage_layouts()}


def _extraction_prefix(layout: StorageLayout) -> list[str]:
    return [
        str(part)
        for part in layout.match.get("extraction_relative_prefix", [])
    ]


def infer_package_root(extraction_root: Path, layout: StorageLayout) -> Path | None:
    prefix = [part.casefold() for part in _extraction_prefix(layout)]
    if not prefix:
        return None

    extraction = Path(extraction_root)
    matches: list[Path] = []
    for ancestor in extraction.parents:
        try:
            relative = extraction.relative_to(ancestor)
        except ValueError:
            continue
        parts = [part.casefold() for part in relative.parts]
        if len(parts) >= len(prefix) and parts[:len(prefix)] == prefix:
            matches.append(ancestor)
    return matches[-1] if matches else None


def _roles_from_roots(
    package_root: Path,
    extraction_root: Path,
    layout: StorageLayout,
) -> dict[str, Path]:
    values = {
        "package_root": str(package_root),
        "extraction_root": str(extraction_root),
    }
    return {
        role: Path(str(template).format(**values))
        for role, template in layout.roles.items()
    }


def materialize_storage_roles(
    extraction_root: Path,
    *,
    layout_id: str | None,
) -> dict[str, Path]:
    """Materialize roles from a known extraction root.

    Existing discovery uses this direction. It remains conservative: if the
    extraction path cannot be matched to the configured layout, no package
    root is invented.
    """
    extraction = Path(extraction_root)
    layout = storage_layout_by_id(layout_id)

    if layout.layout_id == "none":
        return {"source_extraction": extraction}

    package_root = infer_package_root(extraction, layout)
    if package_root is None:
        return {"source_extraction": extraction}

    return _roles_from_roots(package_root, extraction, layout)


def materialize_storage_roles_from_root(
    source_root: Path,
    *,
    layout_id: str | None,
) -> dict[str, Path]:
    """Materialize role suggestions from a known package/source root.

    This is the inverse convenience direction used by the Mapper dialog.
    It is suggestion-only at the UI boundary; callers decide whether values
    may replace existing role assignments.
    """
    root = Path(source_root)
    layout = storage_layout_by_id(layout_id)

    if layout.layout_id == "none":
        return {"source_root": root}

    prefix = _extraction_prefix(layout)
    if not prefix:
        return {"source_root": root}

    extraction = root.joinpath(*prefix)
    return _roles_from_roots(root, extraction, layout)


def suggest_storage_roles(
    *,
    source_root: Path | None = None,
    extraction_root: Path | None = None,
    layout_id: str | None,
) -> dict[str, Path]:
    """Suggest roles from whichever trustworthy anchor is available.

    A recognized extraction path has priority because it can preserve real
    variants such as an extra trailing ``content`` directory. If that cannot
    produce a package root, an explicitly selected Source root is used.
    """
    if extraction_root is not None:
        from_extraction = materialize_storage_roles(
            Path(extraction_root),
            layout_id=layout_id,
        )
        if "source_root" in from_extraction:
            return from_extraction

    if source_root is not None:
        return materialize_storage_roles_from_root(
            Path(source_root),
            layout_id=layout_id,
        )

    if extraction_root is not None:
        return {"source_extraction": Path(extraction_root)}

    return {}


def suggested_job_name(extraction_root: Path, *, layout_id: str | None) -> str:
    extraction = Path(extraction_root)
    layout = storage_layout_by_id(layout_id)
    package_root = infer_package_root(extraction, layout)
    if package_root is not None and package_root.name:
        return package_root.name
    return extraction.name or str(extraction)
