from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from lxml import etree


DEFAULT_DEFINITION = (
    Path(__file__).resolve().parents[2]
    / "config"
    / "noark5"
    / "arkivstruktur_fields.json"
)


class DefinedFieldExtractionError(ValueError):
    """XPath failure with enough context to diagnose the definition."""

    def __init__(
        self,
        message: str,
        *,
        entity_id: str | None = None,
        field_id: str | None = None,
        child_id: str | None = None,
        expression: str | None = None,
        phase: str | None = None,
    ) -> None:
        super().__init__(message)
        self.entity_id = entity_id
        self.field_id = field_id
        self.child_id = child_id
        self.expression = expression
        self.phase = phase

    def as_dict(self) -> dict[str, Any]:
        return {
            "error_type": type(self).__name__,
            "message": str(self),
            "entity_id": self.entity_id,
            "field_id": self.field_id,
            "child_id": self.child_id,
            "expression": self.expression,
            "phase": self.phase,
        }


def load_definition(path: str | Path = DEFAULT_DEFINITION) -> dict[str, Any]:
    with Path(path).open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _scalar(value: Any) -> Any:
    if isinstance(value, list):
        if not value:
            return None
        if len(value) == 1:
            return _scalar(value[0])
        return [_scalar(item) for item in value]
    if isinstance(value, etree._Element):
        return "".join(value.itertext()).strip()
    if isinstance(value, etree._ElementUnicodeResult):
        return str(value).strip()
    if isinstance(value, str):
        return value.strip()
    return value


def _evaluate_xpath(
    node,
    expression: str,
    *,
    entity_id: str,
    phase: str,
    field_id: str | None = None,
    child_id: str | None = None,
):
    try:
        return node.xpath(expression)
    except etree.XPathError as exc:
        location = entity_id
        if child_id:
            location += f".{child_id}"
        if field_id:
            location += f".{field_id}"
        raise DefinedFieldExtractionError(
            f"XPath-feil i {location}: {exc}",
            entity_id=entity_id,
            field_id=field_id,
            child_id=child_id,
            expression=expression,
            phase=phase,
        ) from exc


def _extract_fields(
    node: etree._Element,
    fields: dict[str, str],
    *,
    entity_id: str,
    child_id: str | None = None,
) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for field_id, expression in fields.items():
        out[field_id] = _scalar(
            _evaluate_xpath(
                node,
                expression,
                entity_id=entity_id,
                child_id=child_id,
                field_id=field_id,
                phase="field",
            )
        )
    return out


def extract_defined_fields(
    xml_path: str | Path,
    definition_path: str | Path = DEFAULT_DEFINITION,
) -> dict[str, Any]:
    xml_path = Path(xml_path)
    definition = load_definition(definition_path)

    parser = etree.XMLParser(
        resolve_entities=False,
        no_network=True,
        remove_blank_text=False,
        huge_tree=True,
    )
    tree = etree.parse(str(xml_path), parser)

    result: dict[str, Any] = {
        "definition_id": definition["definition_id"],
        "source": str(xml_path.resolve()),
    }

    for entity_id, entity in definition["entities"].items():
        selector = str(entity["select"])
        nodes = _evaluate_xpath(
            tree,
            selector,
            entity_id=entity_id,
            phase="entity_select",
        )
        extracted = []

        for index, node in enumerate(nodes, start=1):
            item = _extract_fields(
                node,
                entity.get("fields", {}),
                entity_id=entity_id,
            )
            item["index"] = index

            for child_id, child in entity.get("children", {}).items():
                child_selector = str(child["select"])
                child_nodes = _evaluate_xpath(
                    node,
                    child_selector,
                    entity_id=entity_id,
                    child_id=child_id,
                    phase="child_select",
                )
                item[child_id] = [
                    {
                        **_extract_fields(
                            child_node,
                            child.get("fields", {}),
                            entity_id=entity_id,
                            child_id=child_id,
                        ),
                        "index": child_index,
                    }
                    for child_index, child_node in enumerate(child_nodes, start=1)
                ]
            extracted.append(item)

        if entity.get("scope") == "single":
            result[entity_id] = extracted[0] if extracted else None
            result[f"{entity_id}_count"] = len(extracted)
        else:
            result[entity_id] = extracted
            result[f"{entity_id}_count"] = len(extracted)

    return result
