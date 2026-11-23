from __future__ import annotations

import json
from pathlib import Path
import re
from typing import Any, Iterator

from lxml import etree


class AnalysisDefinitionError(ValueError):
    pass


def load_analysis_definition(path: str | Path) -> dict[str, Any]:
    path = Path(path)
    with path.open("r", encoding="utf-8") as handle:
        definition = json.load(handle)
    if not isinstance(definition, dict):
        raise AnalysisDefinitionError("Analysedefinisjonen må være et JSON-objekt.")
    if not definition.get("definition_id"):
        raise AnalysisDefinitionError("Analysedefinisjonen mangler definition_id.")
    if not isinstance(definition.get("entities"), list):
        raise AnalysisDefinitionError("Analysedefinisjonen mangler entities-liste.")
    return definition


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
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return value


# v0.2.5-a1: A170 has its own definition engine. Unlike A130's optimized
# catalogue, it previously used a full libxml2 node-set for all archive and
# archive-part selectors and each count(.//*[local-name()='...']) metric.
# libxml2 can hit "growing nodeset hit limit" on large arkivstruktur.xml.
# Recognize only the exact, side-effect-free XPath subset in the checked-in
# U1/U2 A170 definition. Unknown expressions still use the original evaluator:
# no silent metric loss, no changed XPath semantics for other definitions.
_LOCAL_NAME_SELECT = re.compile(
    r'''(?P<axis>//|\.//)\*\[local-name\(\)=(?P<quote>['"])(?P<name>[^'"\[\]]+)(?P=quote)\]'''
)
_LOCAL_NAME_COUNT = re.compile(
    r'''count\(\.//\*\[local-name\(\)=(?P<quote>['"])(?P<name>[^'"\[\]]+)(?P=quote)\]\)'''
)


def _iter_local_name(
    context: etree._Element | etree._ElementTree,
    local_name: str,
    *,
    include_self: bool,
) -> Iterator[etree._Element]:
    root = context.getroot() if isinstance(context, etree._ElementTree) else context
    if root is None:
        return
    iterator = root.iter()
    if not include_self:
        # XPath './/' skips the context element. XPath '//' includes a
        # matching document element, e.g. when arkiv is the XML root.
        next(iterator, None)
    for item in iterator:
        tag = item.tag
        if isinstance(tag, str) and tag.rsplit('}', 1)[-1] == local_name:
            yield item


def _fallback_xpath(node: etree._Element | etree._ElementTree, expression: str) -> Any:
    return node.xpath(expression)


def _select_nodes(
    node: etree._Element | etree._ElementTree, selector: str,
) -> Iterator[etree._Element] | Any:
    match = _LOCAL_NAME_SELECT.fullmatch(selector.strip())
    if match is not None:
        return _iter_local_name(
            node, match.group('name'), include_self=match.group('axis') == '//',
        )
    return _fallback_xpath(node, selector)


def _evaluate(node: etree._Element, expression: str) -> Any:
    match = _LOCAL_NAME_COUNT.fullmatch(expression.strip())
    if match is not None:
        # One element at a time, no potentially huge intermediate node-set.
        return sum(1 for _ in _iter_local_name(node, match.group('name'), include_self=False))
    return _scalar(_fallback_xpath(node, expression))


def _coerce_metric(value: Any, metric_type: str | None) -> Any:
    if metric_type == "integer":
        if value in (None, ""):
            return 0
        return int(float(value))
    if metric_type == "float":
        if value in (None, ""):
            return 0.0
        return float(value)
    return value


def _extract_fields(node: etree._Element, fields: dict[str, str]) -> dict[str, Any]:
    return {field_id: _evaluate(node, expression) for field_id, expression in fields.items()}


def run_definition_analysis(
    xml_path: str | Path,
    definition_path: str | Path,
) -> dict[str, Any]:
    """Run an externally defined XPath analysis and return a canonical model.

    The engine knows how to execute selectors/fields/metrics, but it contains no
    Noark-specific XPath expressions. Those belong in the external definition.
    """
    xml_path = Path(xml_path)
    definition_path = Path(definition_path)
    definition = load_analysis_definition(definition_path)

    parser = etree.XMLParser(
        resolve_entities=False,
        no_network=True,
        remove_blank_text=False,
        huge_tree=True,
    )
    tree = etree.parse(str(xml_path), parser)

    entities_result: dict[str, list[dict[str, Any]]] = {}
    entity_counts: dict[str, int] = {}

    for entity in definition["entities"]:
        entity_id = str(entity["id"])
        selector = str(entity["select"])
        items: list[dict[str, Any]] = []

        try:
            for index, node in enumerate(_select_nodes(tree, selector), start=1):
                if not isinstance(node, etree._Element):
                    raise AnalysisDefinitionError(
                        f"Entity selector for {entity_id!r} må returnere XML-elementer."
                    )

                item: dict[str, Any] = {
                    "index": index,
                    "fields": _extract_fields(node, entity.get("fields", {})),
                    "metrics": {},
                    "children": {},
                }

                for metric in entity.get("metrics", []):
                    metric_id = str(metric["id"])
                    raw = _evaluate(node, str(metric["expression"]))
                    item["metrics"][metric_id] = _coerce_metric(raw, metric.get("type"))

                for child in entity.get("children", []):
                    child_id = str(child["id"])
                    child_items = []
                    for child_index, child_node in enumerate(
                        _select_nodes(node, str(child["select"])), start=1
                    ):
                        if not isinstance(child_node, etree._Element):
                            continue
                        child_items.append(
                            {
                                "index": child_index,
                                "fields": _extract_fields(child_node, child.get("fields", {})),
                            }
                        )
                    item["children"][child_id] = child_items

                items.append(item)
        except etree.XPathError as exc:
            # A170 must be reported as failed rather than produce an incomplete
            # but apparently successful analysis when an unsupported XPath
            # expression fails in the existing libxml2 evaluator.
            raise AnalysisDefinitionError(
                f"A170 feilet i entity {entity_id!r} (selector {selector!r}): {exc}"
            ) from exc

        entities_result[entity_id] = items
        entity_counts[entity_id] = len(items)

    return {
        "model_format_version": 1,
        "definition_id": definition["definition_id"],
        "definition_path": str(definition_path.resolve()),
        "source": str(xml_path.resolve()),
        "basis": definition.get("basis", {}),
        "summary": {
            "entity_counts": entity_counts,
        },
        "entities": entities_result,
    }


def write_analysis_result(result: dict[str, Any], path: str | Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return path
