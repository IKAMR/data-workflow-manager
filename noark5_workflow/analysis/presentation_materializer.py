from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any


def _visible_field(field: dict[str, Any], audience: str) -> bool:
    visible_for = field.get("visible_for")
    if visible_for is None:
        return True
    return audience in visible_for


def _filter_sections(sections: list[dict[str, Any]], audience: str) -> list[dict[str, Any]]:
    filtered = []
    for section in sections:
        new_section = copy.deepcopy(section)
        fields = [
            copy.deepcopy(field)
            for field in section.get("fields", [])
            if _visible_field(field, audience)
        ]
        if fields:
            new_section["fields"] = fields
            filtered.append(new_section)
    return filtered


def _filter_view(view: dict[str, Any], audience: str) -> dict[str, Any]:
    new_view = copy.deepcopy(view)

    if "sections" in new_view:
        new_view["sections"] = _filter_sections(new_view["sections"], audience)

    if "archive_parts" in new_view:
        rows = []
        for row in new_view["archive_parts"]:
            new_row = copy.deepcopy(row)
            new_row["sections"] = _filter_sections(
                new_row.get("sections", []),
                audience,
            )
            rows.append(new_row)
        new_view["archive_parts"] = rows

    return new_view


def materialize_presentation_profile(
    composed_views: list[dict[str, Any]],
    profile_id: str,
    presentation_definition: dict[str, Any],
) -> dict[str, Any]:
    profiles = presentation_definition.get("profiles") or {}
    if profile_id not in profiles:
        raise ValueError(f"Ukjent presentasjonsprofil: {profile_id}")

    profile = profiles[profile_id]
    audience = profile["include_audience"]
    include_views = set(profile.get("include_views") or [])

    selected = []
    for view in composed_views:
        if view.get("id") not in include_views:
            continue
        audiences = view.get("audiences") or []
        if audiences and audience not in audiences:
            continue
        selected.append(_filter_view(view, audience))

    selected.sort(key=lambda item: int(item.get("presentation_order") or 999))

    return {
        "presentation_materialization_format_version": 1,
        "profile_id": profile_id,
        "label": profile.get("label", profile_id),
        "audience": audience,
        "principle": "Presentation only: no recalculation.",
        "views": selected,
    }


def write_materialized_profiles(
    composed_view_files: dict[str, Path],
    presentation_definition: dict[str, Any],
    output_dir: str | Path,
) -> dict[str, Any]:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    composed_views = []
    for view_id, path in composed_view_files.items():
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        if payload.get("id") != view_id:
            payload["id"] = view_id
        composed_views.append(payload)

    files = {}
    for profile_id in presentation_definition.get("profiles", {}):
        payload = materialize_presentation_profile(
            composed_views,
            profile_id,
            presentation_definition,
        )
        filename = f"{profile_id}.json"
        (output_dir / filename).write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        files[profile_id] = filename

    index = {
        "presentation_materialization_format_version": 1,
        "profiles": files,
    }
    (output_dir / "index.json").write_text(
        json.dumps(index, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return index
