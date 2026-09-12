from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _get_path(value: Any, dotted: str) -> Any:
    current = value
    for part in dotted.split("."):
        if not isinstance(current, dict) or part not in current:
            raise KeyError(dotted)
        current = current[part]
    return current


def _result_file(results_dir: Path, test_id: str) -> Path:
    return results_dir / (test_id.replace(".", "_") + ".json")


def _load_results(result_set_dir: Path) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    index = _read_json(result_set_dir / "index.json")
    results_dir = result_set_dir / "results"
    results = {}
    for row in index.get("tests", []):
        test_id = row.get("test_id")
        if not test_id:
            continue
        path = _result_file(results_dir, test_id)
        if path.is_file():
            results[test_id] = _read_json(path)
    # Also load result files not listed in index, useful for compact fixtures/tests.
    if results_dir.is_dir():
        for path in results_dir.glob("*.json"):
            stem = path.stem.replace("_", ".", 1)
            try:
                payload = _read_json(path)
            except Exception:
                continue
            # Prefer an explicit test id if present, else infer common kdrs_* filename.
            test_id = payload.get("test_id") or stem
            if path.stem.startswith("kdrs_"):
                test_id = "kdrs." + path.stem[len("kdrs_"):]
            results.setdefault(test_id, payload)
    return index, results


def _archive_part_map(result: dict[str, Any]) -> dict[str, dict[str, Any]]:
    rows = result.get("values", {}).get("_archive_parts") or []
    by_id = {}
    for row in rows:
        identity = row.get("archive_part") or {}
        system_id = identity.get("system_id")
        if system_id:
            by_id[system_id] = row.get("values") or {}
    return by_id


def _materialize_views(definition: dict[str, Any]) -> list[dict[str, Any]]:
    """Expand reusable a25 sections into the stable a25 view contract."""
    if definition.get("compositions"):
        library = definition.get("section_library") or {}
        views = []
        for comp in definition["compositions"]:
            if comp["id"] == "validation_evidence":
                views.append({
                    "id": comp["id"],
                    "label": comp["label"],
                    "scope": "result_set",
                    "mode": "validation_evidence",
                    "audiences": comp.get("audiences", []),
                    "presentation_order": comp.get("presentation_order"),
                })
                continue

            sections = []
            for section_id in comp.get("sections", []):
                sec = library[section_id]
                # validation_summary belongs to result-set evidence, not a normal value view.
                if any("source_special" in f for f in sec.get("fields", [])):
                    continue
                fields = []
                for f in sec.get("fields", []):
                    fields.append({
                        "id": f["id"],
                        "label": f.get("label", f["id"]),
                        "value_type": f.get("value_type"),
                        "presentation_order": f.get("presentation_order"),
                        "visible_for": f.get("visible_for", []),
                        "source": {
                            "test_id": f["source_test"],
                            "path": f["source_path"],
                        },
                    })
                sections.append({
                    "id": section_id,
                    "label": sec.get("label", section_id),
                    "presentation_group": sec.get("presentation_group"),
                    "fields": sorted(
                        fields,
                        key=lambda item: int(item.get("presentation_order") or 999),
                    ),
                })

            view = {
                "id": comp["id"],
                "label": comp["label"],
                "scope": comp["scope"],
                "audiences": comp.get("audiences", []),
                "presentation_order": comp.get("presentation_order"),
                "sections": sections,
            }
            if comp["scope"] == "archive_part":
                view["identity_source"] = {
                    "test_id": "kdrs.c02",
                    "path": "archive_part_records",
                    "identity_key": "system_id",
                }
            views.append(view)
        return views

    return definition.get("views", [])


def _whole_field(results: dict[str, dict[str, Any]], source: dict[str, Any]) -> dict[str, Any]:
    test_id = source["test_id"]
    path = source["path"]
    result = results.get(test_id)
    if result is None:
        return {"status": "source_missing", "source_test_id": test_id}
    try:
        value = _get_path(result.get("values", {}), path)
    except KeyError:
        return {"status": "value_missing", "source_test_id": test_id, "source_path": path}
    return {"status": "ok", "source_test_id": test_id, "source_path": path, "value": value}


def _compose_whole(view: dict[str, Any], results: dict[str, dict[str, Any]]) -> dict[str, Any]:
    sections = []
    for section in view.get("sections", []):
        fields = []
        for field in section.get("fields", []):
            item = {
                "id": field["id"],
                "label": field.get("label", field["id"]),
                "value_type": field.get("value_type"),
            }
            item.update(_whole_field(results, field["source"]))
            fields.append(item)
        sections.append({
            "id": section["id"],
            "label": section.get("label", section["id"]),
            "presentation_group": section.get("presentation_group"),
            "fields": fields,
        })
    return {
        "id": view["id"],
        "label": view.get("label", view["id"]),
        "scope": "whole_extraction",
        "audiences": view.get("audiences", []),
        "presentation_order": view.get("presentation_order"),
        "sections": sections,
    }


def _compose_archive_parts(view: dict[str, Any], results: dict[str, dict[str, Any]]) -> dict[str, Any]:
    identity_source = view["identity_source"]
    identity_result = results.get(identity_source["test_id"], {})
    try:
        identities = _get_path(identity_result.get("values", {}), identity_source["path"])
    except KeyError:
        # Fallback to canonical _archive_parts identities if archive_part_records is absent.
        identities = [
            row.get("archive_part") or {}
            for row in identity_result.get("values", {}).get("_archive_parts", [])
        ]
    identity_key = identity_source.get("identity_key", "system_id")

    source_maps = {}
    for section in view.get("sections", []):
        for field in section.get("fields", []):
            test_id = field["source"]["test_id"]
            if test_id not in source_maps:
                source_maps[test_id] = _archive_part_map(results.get(test_id, {}))

    rows = []
    for identity in identities:
        system_id = identity.get(identity_key)
        sections = []
        for section in view.get("sections", []):
            fields = []
            for field in section.get("fields", []):
                source = field["source"]
                item = {
                    "id": field["id"],
                    "label": field.get("label", field["id"]),
                    "value_type": field.get("value_type"),
                    "source_test_id": source["test_id"],
                    "source_path": source["path"],
                }
                values = source_maps.get(source["test_id"], {}).get(system_id)
                if values is None:
                    item["status"] = "archive_part_missing"
                else:
                    try:
                        item["value"] = _get_path(values, source["path"])
                        item["status"] = "ok"
                    except KeyError:
                        item["status"] = "value_missing"
                fields.append(item)
            sections.append({
                "id": section["id"],
                "label": section.get("label", section["id"]),
                "presentation_group": section.get("presentation_group"),
                "fields": fields,
            })
        rows.append({"archive_part": identity, "sections": sections})

    return {
        "id": view["id"],
        "label": view.get("label", view["id"]),
        "scope": "archive_part",
        "audiences": view.get("audiences", []),
        "presentation_order": view.get("presentation_order"),
        "archive_parts": rows,
    }


def _compose_validation(
    view: dict[str, Any],
    index: dict[str, Any],
    results: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    rows = []
    for idxrow in index.get("tests", []):
        test_id = idxrow.get("test_id")
        result = results.get(test_id, {})
        values = result.get("values", {})
        rows.append({
            "test_id": test_id,
            "legacy_job_id": idxrow.get("legacy_job_id"),
            "test_point": idxrow.get("test_point"),
            "status": idxrow.get("status"),
            "reconciliation_summary": values.get("_reconciliation_summary"),
            "standard_value_checks": values.get("_standard_values") or {},
        })
    return {
        "id": view["id"],
        "label": view.get("label", view["id"]),
        "scope": "result_set",
        "audiences": view.get("audiences", []),
        "presentation_order": view.get("presentation_order"),
        "execution_profile": index.get("execution_profile"),
        "result_summary": index.get("summary", {}),
        "tests": rows,
    }


def compose_views(result_set_dir: str | Path, definition: dict[str, Any]) -> dict[str, Any]:
    result_set_dir = Path(result_set_dir)
    index, results = _load_results(result_set_dir)

    required_profile = definition.get("input", {}).get("required_execution_profile", "normal")
    actual_profile = index.get("execution_profile")
    if required_profile and actual_profile != required_profile:
        raise ValueError(
            f"Views require execution_profile={required_profile}, got {actual_profile}"
        )

    composed_views = []
    for view in _materialize_views(definition):
        if view.get("mode") == "validation_evidence":
            composed_views.append(_compose_validation(view, index, results))
        elif view.get("scope") == "whole_extraction":
            composed_views.append(_compose_whole(view, results))
        elif view.get("scope") == "archive_part":
            composed_views.append(_compose_archive_parts(view, results))
        else:
            raise ValueError(f"Unknown view mode/scope: {view.get('id')}")

    return {
        "composition_format_version": 2,
        "definition_id": definition.get("definition_id"),
        "source_result_set": str(result_set_dir),
        "source_execution_profile": actual_profile,
        "principle": "Composition only: no XML/XPath recalculation.",
        "audiences": definition.get("audiences", {}),
        "presentation_groups": definition.get("presentation_groups", {}),
        "views": sorted(
            composed_views,
            key=lambda item: int(item.get("presentation_order") or 999),
        ),
    }


def write_composed_views(
    result_set_dir: str | Path,
    definition_path: str | Path,
    output_dir: str | Path,
) -> dict[str, Any]:
    """Stable a25 API: compose and write one JSON file per view plus index.json."""
    definition_path = Path(definition_path)
    definition = _read_json(definition_path)
    composed = compose_views(result_set_dir, definition)

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    files = []
    for view in composed["views"]:
        filename = view["id"] + ".json"
        (output_dir / filename).write_text(
            json.dumps(view, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        files.append(filename)

    index = {
        "composition_format_version": composed["composition_format_version"],
        "definition_id": composed["definition_id"],
        "source_result_set": composed["source_result_set"],
        "source_execution_profile": composed["source_execution_profile"],
        "views": [
            {"id": v["id"], "label": v["label"], "file": v["id"] + ".json"}
            for v in composed["views"]
        ],
    }
    (output_dir / "index.json").write_text(
        json.dumps(index, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return index
