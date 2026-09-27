from __future__ import annotations

import json
from pathlib import Path
from typing import Any
import xml.etree.ElementTree as ET

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


def _local_name(tag: str) -> str:
    if tag.startswith("{") and "}" in tag:
        return tag.split("}", 1)[1]
    return tag


def _element_text(elem: ET.Element) -> str:
    return "".join(elem.itertext()).strip()


def _local_name_from_xpath(expression: str) -> str | None:
    """Return the local-name literal from the small XPath subset we can stream."""
    import re

    match = re.search(r"local-name\(\)\s*=\s*(['\"])([^'\"]+)\1", expression)
    return match.group(2) if match else None


def _xpath_syntax_valid(expression: str) -> bool:
    """Validate XPath syntax without evaluating it against the XML tree."""
    try:
        etree.XPath(expression)
    except etree.XPathError:
        return False
    return True


def _stream_plan(definition: dict[str, Any]) -> dict[str, Any] | None:
    """Compile external field definitions to an iterparse plan.

    The engine deliberately does not know Noark element names.  Streaming is
    enabled only when selectors use the simple local-name() subset represented
    by the external JSON definition.  Anything else falls back to the existing
    XPath implementation so validation/error semantics are preserved.
    """
    entities = definition.get("entities")
    if not isinstance(entities, dict) or not entities:
        return None

    plan: dict[str, Any] = {}
    for entity_id, entity in entities.items():
        if not isinstance(entity, dict):
            return None
        entity_selector = str(entity.get("select", ""))
        if not _xpath_syntax_valid(entity_selector):
            return None
        entity_tag = _local_name_from_xpath(entity_selector)
        if not entity_tag:
            return None

        field_tags: dict[str, str] = {}
        fields = entity.get("fields", {})
        if not isinstance(fields, dict):
            return None
        for field_id, expression in fields.items():
            expression = str(expression)
            if not _xpath_syntax_valid(expression):
                return None
            tag = _local_name_from_xpath(expression)
            if not tag:
                return None
            field_tags[tag] = str(field_id)

        child_plan: dict[str, Any] = {}
        children = entity.get("children", {})
        if not isinstance(children, dict):
            return None
        for child_id, child in children.items():
            if not isinstance(child, dict):
                return None
            child_selector = str(child.get("select", ""))
            if not _xpath_syntax_valid(child_selector):
                return None
            child_tag = _local_name_from_xpath(child_selector)
            if not child_tag:
                return None
            child_field_tags: dict[str, str] = {}
            child_fields = child.get("fields", {})
            if not isinstance(child_fields, dict):
                return None
            for field_id, expression in child_fields.items():
                expression = str(expression)
                if not _xpath_syntax_valid(expression):
                    return None
                tag = _local_name_from_xpath(expression)
                if not tag:
                    return None
                child_field_tags[tag] = str(field_id)
            child_plan[str(child_id)] = {
                "tag": child_tag,
                "field_tags": child_field_tags,
            }

        plan[str(entity_id)] = {
            "tag": entity_tag,
            "scope": entity.get("scope"),
            "field_tags": field_tags,
            "children": child_plan,
        }
    return plan


def _can_stream_definition(definition: dict[str, Any]) -> bool:
    return _stream_plan(definition) is not None


def _extract_defined_fields_streaming(
    xml_path: Path,
    definition: dict[str, Any],
) -> dict[str, Any]:
    """Extract externally defined metadata with iterparse only.

    Element names and output field names come exclusively from the external
    definition.  This avoids materialising global libxml2 XPath node-sets while
    keeping the original definition-driven architecture intact.
    """
    plan = _stream_plan(definition)
    if plan is None:
        raise DefinedFieldExtractionError(
            "Definisjonen kan ikke kjoeres med stroemmet feltuttrekk.",
            phase="stream_plan",
        )

    entity_stacks: dict[str, list[dict[str, Any]]] = {
        entity_id: [] for entity_id in plan
    }
    child_stacks: dict[tuple[str, str], list[dict[str, Any]]] = {
        (entity_id, child_id): []
        for entity_id, entity_plan in plan.items()
        for child_id in entity_plan["children"]
    }
    extracted: dict[str, list[dict[str, Any]]] = {
        entity_id: [] for entity_id in plan
    }
    tag_stack: list[str] = []

    try:
        for event, elem in ET.iterparse(xml_path, events=("start", "end")):
            tag = _local_name(elem.tag)

            if event == "start":
                tag_stack.append(tag)

                for entity_id, entity_plan in plan.items():
                    if tag == entity_plan["tag"]:
                        entity_stacks[entity_id].append({
                            "values": {},
                            "children": {
                                child_id: []
                                for child_id in entity_plan["children"]
                            },
                        })

                for entity_id, entity_plan in plan.items():
                    if not entity_stacks[entity_id]:
                        continue
                    for child_id, child_plan in entity_plan["children"].items():
                        if tag == child_plan["tag"]:
                            child_stacks[(entity_id, child_id)].append({
                                "values": {},
                                "owner": entity_stacks[entity_id][-1],
                            })
                continue

            parent_tag = tag_stack[-2] if len(tag_stack) >= 2 else ""

            for entity_id, entity_plan in plan.items():
                if entity_stacks[entity_id] and parent_tag == entity_plan["tag"]:
                    field_id = entity_plan["field_tags"].get(tag)
                    if field_id is not None:
                        entity_stacks[entity_id][-1]["values"][field_id] = _element_text(elem)

                for child_id, child_plan in entity_plan["children"].items():
                    stack = child_stacks[(entity_id, child_id)]
                    if stack and parent_tag == child_plan["tag"]:
                        field_id = child_plan["field_tags"].get(tag)
                        if field_id is not None:
                            stack[-1]["values"][field_id] = _element_text(elem)

            for entity_id, entity_plan in plan.items():
                for child_id, child_plan in entity_plan["children"].items():
                    stack = child_stacks[(entity_id, child_id)]
                    if tag == child_plan["tag"] and stack:
                        child_state = stack.pop()
                        values = child_state["values"]
                        for field_id in child_plan["field_tags"].values():
                            values.setdefault(field_id, "")
                        owner_items = child_state["owner"]["children"][child_id]
                        values["index"] = len(owner_items) + 1
                        owner_items.append(values)

                if tag == entity_plan["tag"] and entity_stacks[entity_id]:
                    state = entity_stacks[entity_id].pop()
                    values = state["values"]
                    for field_id in entity_plan["field_tags"].values():
                        values.setdefault(field_id, "")
                    values["index"] = len(extracted[entity_id]) + 1
                    for child_id, items in state["children"].items():
                        values[child_id] = items
                    extracted[entity_id].append(values)

            elem.clear()
            if tag_stack:
                tag_stack.pop()

    except ET.ParseError as exc:
        raise DefinedFieldExtractionError(
            f"XML-feil under stroemmet feltuttrekk: {exc}",
            phase="stream_parse",
        ) from exc

    result: dict[str, Any] = {
        "definition_id": definition["definition_id"],
        "source": str(xml_path.resolve()),
    }
    for entity_id, entity_plan in plan.items():
        rows = extracted[entity_id]
        if entity_plan["scope"] == "single":
            result[entity_id] = rows[0] if rows else None
            result[f"{entity_id}_count"] = len(rows)
        else:
            result[entity_id] = rows
            result[f"{entity_id}_count"] = len(rows)
    return result


def _extract_defined_fields_xpath(
    xml_path: Path,
    definition: dict[str, Any],
) -> dict[str, Any]:
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


def extract_defined_fields(
    xml_path: str | Path,
    definition_path: str | Path = DEFAULT_DEFINITION,
) -> dict[str, Any]:
    xml_path = Path(xml_path)
    definition = load_definition(definition_path)

    if _can_stream_definition(definition):
        return _extract_defined_fields_streaming(xml_path, definition)

    return _extract_defined_fields_xpath(xml_path, definition)
