from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable


MASTER_MODEL_PATH = (
    Path(__file__).resolve().parents[2]
    / "config"
    / "noark5"
    / "master_result_model.json"
)
MASTER_FILENAME = "master-results.json"


class MasterResultError(ValueError):
    pass


def _read_json_object(path: Path, *, label: str) -> dict[str, Any]:
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise MasterResultError(f"Kunne ikke lese {label}: {exc}") from exc
    if not isinstance(value, dict):
        raise MasterResultError(f"{label} ma vaere et JSON-objekt: {path}")
    return value


def load_master_result_model(path: Path = MASTER_MODEL_PATH) -> dict[str, Any]:
    model = _read_json_object(Path(path), label="masterresultatmodellen")
    if int(model.get("format_version") or 0) != 1:
        raise MasterResultError(
            f"Ustottet masterresultatmodell: {model.get('format_version')}"
        )
    if not str(model.get("model_id") or "").strip():
        raise MasterResultError("Masterresultatmodellen mangler model_id")
    return model


def _entities_for_definition(
    definition: dict[str, Any], model: dict[str, Any]
) -> list[str]:
    mapping = model.get("tag_to_entity") or {}
    ignored = set(model.get("non_entity_tags") or [])
    tags = definition.get("tags") or []
    if isinstance(tags, str):
        tags = [tags]
    entities: list[str] = []
    for raw_tag in tags if isinstance(tags, list) else []:
        tag = str(raw_tag).strip()
        if not tag or tag in ignored:
            continue
        entity = str(mapping.get(tag) or "").strip()
        if entity and entity not in entities:
            entities.append(entity)
    return entities or ["cross_cutting"]


def _result_file(run_dir: Path, relative_path: str) -> Path:
    candidate = (run_dir / relative_path).resolve()
    root = run_dir.resolve()
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise MasterResultError(
            f"Resultatfil peker utenfor testkjoringen: {relative_path}"
        ) from exc
    return candidate


def build_master_result_set(
    run_dir: str | Path,
    *,
    model_path: Path = MASTER_MODEL_PATH,
    output_path: str | Path | None = None,
) -> Path:
    """Materialize the master index for one normal Noark 5 test run.

    Individual test JSON files remain the master values. This function only
    builds a stable index over those files; it never recalculates test values.
    Historical U1/U2/regression runs and external evidence are comparison
    sources and cannot be promoted through this function.
    """

    run_dir = Path(run_dir)
    index_path = run_dir / "index.json"
    index = _read_json_object(index_path, label="testindeksen")
    model = load_master_result_model(model_path)

    execution_profile = str(index.get("execution_profile") or "").strip()
    accepted = {str(value) for value in model.get("accepted_execution_profiles") or []}
    if execution_profile not in accepted:
        raise MasterResultError(
            "Bare ordinaer individuell testkjoring kan materialiseres som master; "
            f"execution_profile={execution_profile or '<mangler>'}"
        )

    raw_tests = index.get("tests")
    if not isinstance(raw_tests, list):
        raise MasterResultError("Testindeksen mangler tests-listen")

    entries: list[dict[str, Any]] = []
    entity_members: dict[str, list[str]] = {
        str(entity): [] for entity in model.get("entity_order") or []
    }

    available = 0
    unavailable = 0
    for row in raw_tests:
        if not isinstance(row, dict):
            continue
        test_id = str(row.get("test_id") or "").strip()
        relative_file = str(row.get("file") or "").strip()
        if not test_id or not relative_file:
            raise MasterResultError("Testindeksen inneholder rad uten test_id/file")

        result_path = _result_file(run_dir, relative_file)
        result = _read_json_object(result_path, label=f"testresultatet {test_id}")
        if str(result.get("test_id") or "") != test_id:
            raise MasterResultError(
                f"test_id stemmer ikke mellom indeks og resultatfil: {test_id}"
            )

        definition = result.get("definition")
        if not isinstance(definition, dict):
            definition = {}
        entities = _entities_for_definition(definition, model)
        status = str(result.get("status") or row.get("status") or "unknown")
        has_values = status == "ok" and isinstance(result.get("values"), dict)
        availability = "available" if has_values else "unavailable"
        if has_values:
            available += 1
        else:
            unavailable += 1

        entry = {
            "test_id": test_id,
            "role": "master" if has_values else "master_test_unavailable",
            "availability": availability,
            "status": status,
            "entities": entities,
            "tags": list(definition.get("tags") or []),
            "name": definition.get("name"),
            "source_xml": result.get("source_xml") or definition.get("source_xml"),
            "test_point": row.get("test_point"),
            "normalized_test_point": row.get("normalized_test_point"),
            "result_file": relative_file,
        }
        entries.append(entry)
        for entity in entities:
            entity_members.setdefault(entity, []).append(test_id)

    ordered_entities = []
    known_order = [str(value) for value in model.get("entity_order") or []]
    extras = sorted(set(entity_members).difference(known_order))
    for entity in known_order + extras:
        ids = entity_members.get(entity) or []
        if ids:
            ordered_entities.append({"entity": entity, "test_ids": ids})

    document = {
        "format_version": 1,
        "model_id": model["model_id"],
        "role": model.get("master_role"),
        "source": {
            "catalog_id": index.get("catalog_id"),
            "execution_profile": execution_profile,
            "index_file": "index.json",
        },
        "principles": model.get("principles", {}),
        "tests": entries,
        "entities": ordered_entities,
        "summary": {
            "tests": len(entries),
            "available_master_results": available,
            "unavailable_master_results": unavailable,
            "entities": len(ordered_entities),
        },
        "reference_sources": model.get("reference_sources", []),
    }

    target = Path(output_path) if output_path is not None else run_dir / MASTER_FILENAME
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return target


def load_master_result_set(path: str | Path) -> dict[str, Any]:
    document = _read_json_object(Path(path), label="masterresultatsettet")
    if int(document.get("format_version") or 0) != 1:
        raise MasterResultError(
            f"Ustottet masterresultatformat: {document.get('format_version')}"
        )
    return document


def iter_master_entries(
    master_path: str | Path,
    *,
    entity: str | None = None,
    available_only: bool = True,
) -> Iterable[dict[str, Any]]:
    document = load_master_result_set(master_path)
    for entry in document.get("tests") or []:
        if not isinstance(entry, dict):
            continue
        if available_only and entry.get("availability") != "available":
            continue
        if entity is not None and entity not in (entry.get("entities") or []):
            continue
        yield entry


def load_master_values(master_path: str | Path, test_id: str) -> dict[str, Any]:
    """Load values from the individual JSON result referenced by the master index."""
    master_path = Path(master_path)
    wanted = str(test_id)
    for entry in iter_master_entries(master_path, available_only=True):
        if str(entry.get("test_id")) != wanted:
            continue
        relative = str(entry.get("result_file") or "")
        result_path = _result_file(master_path.parent, relative)
        result = _read_json_object(result_path, label=f"mastertestresultatet {wanted}")
        values = result.get("values")
        if not isinstance(values, dict):
            raise MasterResultError(f"Mastertestresultatet {wanted} mangler values")
        return values
    raise MasterResultError(f"Tilgjengelig mastertestresultat finnes ikke: {wanted}")
