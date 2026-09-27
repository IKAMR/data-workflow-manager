from __future__ import annotations

from collections import Counter
from datetime import datetime
import os
from pathlib import Path
import platform
import re
import struct
import subprocess
import sys
import tempfile
import threading
import queue
import json
import time
from typing import Any, Iterable, Iterator

from lxml import etree


_SIMPLE_PREDICATE_RE = re.compile(r"^([^\[]+)(.*)$")
_STRING_LENGTH_RE = re.compile(r"^string-length\(([^)]+)\)>0$")
_ATTR_EQ_RE = re.compile(r'^@([^=]+)="([^"]*)"$')
_CHILD_EQ_RE = re.compile(r'^([^=]+)="([^"]*)"$')
_COUNT_ATTR_RE = re.compile(r"^count\(@\*\)(<1|=0)$")
_NOT_RE = re.compile(r"^not\((.+)\)$")
_COUNT_RE = re.compile(r"^count\((.+)\)$")

_INSTALLED = False
_TREE_CACHE: dict[str, tuple[tuple[int, int], etree._ElementTree]] = {}


def _extract_predicates(suffix: str) -> list[str]:
    out: list[str] = []
    depth = 0
    start: int | None = None
    for i, ch in enumerate(suffix):
        if ch == "[":
            if depth == 0:
                start = i + 1
            depth += 1
        elif ch == "]" and depth:
            depth -= 1
            if depth == 0 and start is not None:
                out.append(suffix[start:i])
                start = None
    return out


def _is_tree(node: Any) -> bool:
    return isinstance(node, etree._ElementTree)


def _root(node: Any) -> etree._Element:
    return node.getroot() if _is_tree(node) else node


def _children(node: etree._Element, tag: str | None = None) -> Iterator[etree._Element]:
    for child in node:
        if not isinstance(child.tag, str):
            continue
        if tag is None or tag == "*" or child.tag == tag:
            yield child


def _desc(node: Any, tag: str | None = None) -> Iterator[etree._Element]:
    root = _root(node)
    first = True
    for elem in root.iter():
        if first:
            first = False
            continue
        if not isinstance(elem.tag, str):
            continue
        if tag is None or tag == "*" or elem.tag == tag:
            yield elem


def _split_path(path: str) -> list[tuple[str, str]]:
    """Split the XPath subset used by the Noark catalogue into axis/step pairs."""
    path = path.strip()
    if not path:
        return []
    steps: list[tuple[str, str]] = []
    i = 0
    if path.startswith(".//"):
        axis = "desc"
        i = 3
    elif path.startswith("//"):
        # Leading // is evaluated from the document root. lxml's XPath
        # includes the root element itself when it matches (for example a
        # fixture whose document element is <arkiv> and select is //arkiv).
        # Preserve that behaviour without changing .// semantics.
        axis = "desc_or_self"
        i = 2
    elif path.startswith("./"):
        axis = "child"
        i = 2
    else:
        axis = "child"

    start = i
    bracket_depth = 0
    while i <= len(path):
        at_end = i == len(path)
        if not at_end:
            ch = path[i]
            if ch == "[":
                bracket_depth += 1
            elif ch == "]":
                bracket_depth = max(0, bracket_depth - 1)
        if at_end or (bracket_depth == 0 and path[i:i + 2] == "//") or (bracket_depth == 0 and path[i:i + 1] == "/"):
            step = path[start:i]
            if step:
                steps.append((axis, step))
            if at_end:
                break
            if path[i:i + 2] == "//":
                axis = "desc"
                i += 2
            else:
                axis = "child"
                i += 1
            start = i
            continue
        i += 1
    return steps


def _direct_child(node: etree._Element, name: str) -> etree._Element | None:
    for child in _children(node, name):
        return child
    return None


def _text(node: etree._Element) -> str:
    return "".join(node.itertext()).strip()


def _has_child(node: etree._Element, name: str) -> bool:
    return _direct_child(node, name) is not None


def _matches_predicate(node: etree._Element, predicate: str) -> bool:
    predicate = predicate.strip()

    m = _ATTR_EQ_RE.match(predicate)
    if m:
        return node.get(m.group(1), "") == m.group(2)

    m = _COUNT_ATTR_RE.match(predicate)
    if m:
        return len(node.attrib) == 0

    m = _STRING_LENGTH_RE.match(predicate)
    if m:
        child = _direct_child(node, m.group(1).strip())
        return child is not None and bool(_text(child))

    m = _NOT_RE.match(predicate)
    if m:
        inner = m.group(1).strip()
        if inner == "text()":
            return node.text is None
        if " or " in inner:
            terms = [term.strip() for term in inner.split(" or ")]
            return not any(_matches_predicate(node, term) for term in terms if term)
        return not _matches_predicate(node, inner)

    m = _CHILD_EQ_RE.match(predicate)
    if m:
        child = _direct_child(node, m.group(1).strip())
        return child is not None and _text(child) == m.group(2)

    # Simple child-existence predicate, including one nested form used by the
    # catalogue: journalpost[tilgangsrestriksjon].
    nested = _SIMPLE_PREDICATE_RE.match(predicate)
    if nested:
        child_name = nested.group(1).strip()
        suffix = nested.group(2)
        candidates = list(_children(node, child_name))
        if not suffix:
            return bool(candidates)
        nested_preds = _extract_predicates(suffix)
        return any(all(_matches_predicate(child, p) for p in nested_preds) for child in candidates)

    return False


def _parse_step(step: str) -> tuple[str, list[str], bool]:
    if step == "text()":
        return "text()", [], True
    m = _SIMPLE_PREDICATE_RE.match(step)
    if not m:
        return step, [], False
    name = m.group(1).strip()
    predicates = _extract_predicates(m.group(2))
    return name, predicates, False


def _iter_select(node: Any, path: str) -> Iterator[Any]:
    steps = _split_path(path)
    if not steps:
        return

    current: Iterable[Any] = [_root(node)]
    for axis, raw_step in steps:
        name, predicates, is_text = _parse_step(raw_step)
        if is_text:
            for item in current:
                if isinstance(item, etree._Element) and item.text is not None:
                    yield item.text
            return

        parent_items = current

        def next_items(
            source: Iterable[Any],
            axis_value: str,
            name_value: str,
            predicates_value: tuple[str, ...],
        ) -> Iterator[etree._Element]:
            for parent in source:
                if not isinstance(parent, etree._Element):
                    continue
                if axis_value == "desc_or_self":
                    root_candidate = _root(parent)
                    def candidates_iter():
                        if (
                            isinstance(root_candidate.tag, str)
                            and (name_value == "*" or root_candidate.tag == name_value)
                        ):
                            yield root_candidate
                        yield from _desc(parent, name_value)
                    candidates = candidates_iter()
                elif axis_value == "desc":
                    candidates = _desc(parent, name_value)
                else:
                    candidates = _children(parent, name_value)
                for candidate in candidates:
                    if all(_matches_predicate(candidate, p) for p in predicates_value):
                        yield candidate

        current = next_items(parent_items, axis, name, tuple(predicates))

    yield from current


def _count_path(node: Any, path: str) -> int:
    return sum(1 for _ in _iter_select(node, path))


def _count_expression(node: Any, expression: str) -> int | None:
    expression = expression.strip()
    # The catalogue uses subtraction only between count() expressions.
    depth = 0
    split_at = None
    for i, ch in enumerate(expression):
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        elif ch == "-" and depth == 0:
            split_at = i
            break
    if split_at is not None:
        left = _count_expression(node, expression[:split_at])
        right = _count_expression(node, expression[split_at + 1:])
        if left is not None and right is not None:
            return left - right
        return None

    m = _COUNT_RE.match(expression)
    if not m:
        return None
    path = m.group(1).strip()
    return _count_path(node, path)


def _safe_xpath(node: Any, expression: str, original_xpath) -> Any:
    value = _count_expression(node, expression)
    if value is not None:
        return value
    return original_xpath(node, expression)


def _safe_texts(node: Any, select: str) -> list[str]:
    # Keep the existing public return shape, but do not ask libxml2 to build a
    # large node-set first. Consumers that only aggregate are replaced below
    # with direct iterators and therefore avoid this list entirely.
    out: list[str] = []
    for value in _iter_select(node, select):
        if isinstance(value, etree._Element):
            text = _text(value)
        else:
            text = str(value).strip()
        if text:
            out.append(text)
    return out


def _safe_group(node: Any, spec: dict[str, Any]) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for item in _iter_select(node, spec["select"]):
        if not isinstance(item, etree._Element):
            value = str(item).strip()
        elif spec["type"] == "group_attr":
            attr = str(spec.get("value", "@type")).strip()
            attr = attr[1:] if attr.startswith("@") else attr
            value = item.get(attr, "")
        elif spec["type"] == "group_xpath":
            expr = str(spec.get("value", "string(.)"))
            value = str(item.xpath(expr) or "").strip()
        else:
            value = _text(item)
        value = str(value or "").strip()
        if value:
            counts[value] += 1
    return dict(sorted(counts.items(), key=lambda x: x[0].casefold()))


def _safe_year_counts(node: Any, select: str) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for item in _iter_select(node, select):
        text = _text(item) if isinstance(item, etree._Element) else str(item).strip()
        if len(text) >= 4:
            counts[text[:4]] += 1
    return dict(sorted(counts.items()))


def _safe_date_range(node: Any, select: str) -> dict[str, str | None]:
    first: str | None = None
    last: str | None = None
    for item in _iter_select(node, select):
        text = _text(item) if isinstance(item, etree._Element) else str(item).strip()
        if len(text) < 10:
            continue
        value = text[:10]
        if first is None or value < first:
            first = value
        if last is None or value > last:
            last = value
    return {"first": first, "last": last}


def _safe_numeric_values(node: Any, select: str) -> list[float]:
    values: list[float] = []
    for item in _iter_select(node, select):
        text = _text(item) if isinstance(item, etree._Element) else str(item).strip()
        try:
            values.append(float(text))
        except (TypeError, ValueError):
            pass
    return values


def _safe_rows(node: Any, spec: dict[str, Any], original_xpath) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in _iter_select(node, spec["select"]):
        if not isinstance(item, etree._Element):
            continue
        row: dict[str, Any] = {}
        for field_id, expression in spec.get("fields", {}).items():
            row[field_id] = original_xpath(item, expression)
        rows.append(row)
    return rows


def _safe_archive_parts(tree: Any) -> list[etree._Element]:
    return [item for item in _iter_select(tree, "//arkivdel") if isinstance(item, etree._Element)]


def _direct_child_text(node: etree._Element, name: str) -> str:
    child = _direct_child(node, name)
    return _text(child) if child is not None else ""


def _range_from_values(values: Iterable[str]) -> dict[str, str | None]:
    first: str | None = None
    last: str | None = None
    for raw in values:
        value = str(raw or "").strip()
        if len(value) < 10:
            continue
        value = value[:10]
        if first is None or value < first:
            first = value
        if last is None or value > last:
            last = value
    return {"first": first, "last": last}




def _local_name(tag: Any) -> str:
    if not isinstance(tag, str):
        return ""
    if tag.startswith("{"):
        try:
            return etree.QName(tag).localname
        except Exception:
            return tag
    return tag


def _c02_values_iterparse_file(source: Path, execution: dict[str, Any], engine) -> dict[str, Any]:
    """Materialise C02 directly from disk with iterparse.

    This is intentionally independent of the normalized in-memory tree.  It
    never evaluates ``//arkivdel//...`` through libxml2 XPath and therefore
    avoids the node-set materialisation limit seen on very large Noark 5
    ``arkivstruktur.xml`` files.  Only the small aggregate/result contract is
    retained in memory.
    """
    rows: list[dict[str, Any]] = []
    whole_medium: Counter[str] = Counter()
    whole_status: Counter[str] = Counter()
    created_dates: list[str] = []
    closed_dates: list[str] = []
    archive_part_records: list[dict[str, Any]] = []

    total_folders = 0
    total_registrations = 0
    total_descriptions = 0
    part_index = 0
    current: dict[str, Any] | None = None

    direct_fields = {
        "systemID", "tittel", "beskrivelse", "arkivdelstatus",
        "dokumentmedium", "arkivperiodeStartDato",
        "arkivperiodeSluttDato", "opprettetDato", "avsluttetDato",
    }

    context = etree.iterparse(
        str(source),
        events=("start", "end"),
        resolve_entities=False,
        no_network=True,
        huge_tree=True,
    )

    for event, elem in context:
        tag = _local_name(elem.tag)

        if event == "start":
            if tag == "arkivdel":
                part_index += 1
                current = {
                    "index": part_index,
                    "fields": {},
                    "folder_count": 0,
                    "registration_count": 0,
                    "document_description_count": 0,
                    "document_medium_counts": Counter(),
                }
            continue

        parent = elem.getparent()
        parent_tag = _local_name(parent.tag) if parent is not None else ""

        if current is not None:
            if tag == "mappe":
                current["folder_count"] += 1
            elif tag == "registrering":
                current["registration_count"] += 1
            elif tag == "dokumentbeskrivelse":
                current["document_description_count"] += 1
            elif tag == "dokumentmedium" and parent_tag == "dokumentbeskrivelse":
                value = _text(elem)
                if value:
                    current["document_medium_counts"][value] += 1

            if parent_tag == "arkivdel" and tag in direct_fields:
                current["fields"][tag] = _text(elem)

            if tag == "arkivdel":
                fields = current["fields"]
                folder_count = int(current["folder_count"])
                registration_count = int(current["registration_count"])
                description_count = int(current["document_description_count"])
                medium_counts = current["document_medium_counts"]

                status = str(fields.get("arkivdelstatus", "") or "").strip()
                created = str(fields.get("opprettetDato", "") or "").strip()
                closed = str(fields.get("avsluttetDato", "") or "").strip()
                if status:
                    whole_status[status] += 1
                if created:
                    created_dates.append(created)
                if closed:
                    closed_dates.append(closed)

                total_folders += folder_count
                total_registrations += registration_count
                total_descriptions += description_count
                whole_medium.update(medium_counts)

                rows.append({
                    "archive_part": {
                        "index": current["index"],
                        "system_id": str(fields.get("systemID", "") or ""),
                        "title": str(fields.get("tittel", "") or ""),
                        "status": status,
                    },
                    "values": {
                        "folder_count": folder_count,
                        "registration_count": registration_count,
                        "document_description_count": description_count,
                        "document_medium_counts": dict(sorted(medium_counts.items(), key=lambda item: item[0].casefold())),
                        "archive_part_created_date_range": _range_from_values([created]),
                        "archive_part_closed_date_range": _range_from_values([closed]),
                    },
                })
                archive_part_records.append({
                    "system_id": str(fields.get("systemID", "") or ""),
                    "title": str(fields.get("tittel", "") or ""),
                    "description": str(fields.get("beskrivelse", "") or ""),
                    "status": status,
                    "document_medium": str(fields.get("dokumentmedium", "") or ""),
                    "archive_period_start_date": str(fields.get("arkivperiodeStartDato", "") or ""),
                    "archive_period_end_date": str(fields.get("arkivperiodeSluttDato", "") or ""),
                    "created_date": created,
                    "closed_date": closed,
                })
                current = None

        # Release processed XML aggressively.  This is the important
        # difference from the a13.7 in-memory walk: memory use scales with the
        # active parser window rather than the full source document.
        elem.clear()
        parent = elem.getparent()
        if parent is not None:
            while elem.getprevious() is not None:
                del parent[0]

    values: dict[str, Any] = {
        "archive_part_count": len(rows),
        "folder_count": total_folders,
        "registration_count": total_registrations,
        "document_description_count": total_descriptions,
        "document_medium_counts": dict(sorted(whole_medium.items(), key=lambda item: item[0].casefold())),
        "archive_part_created_date_range": _range_from_values(created_dates),
        "archive_part_closed_date_range": _range_from_values(closed_dates),
        "archive_part_records": archive_part_records,
        "archive_part_status_counts": dict(sorted(whole_status.items(), key=lambda item: item[0].casefold())),
        "_archive_parts": rows,
    }

    specs = execution.get("reconciliation") or []
    if specs:
        values["_reconciliation"] = engine._reconcile(values, rows, specs)
        statuses = [entry.get("status") for entry in values["_reconciliation"].values()]
        values["_reconciliation_summary"] = {
            "checks": len(statuses),
            "matches": sum(1 for status in statuses if status == "match"),
            "mismatches": sum(1 for status in statuses if status == "mismatch"),
            "not_comparable": sum(1 for status in statuses if status == "not_comparable"),
            "status": (
                "match" if statuses and all(status == "match" for status in statuses)
                else "not_comparable" if statuses and all(status == "not_comparable" for status in statuses)
                else "review"
            ),
        }
    return values

def _c02_values_streaming(tree: etree._ElementTree, execution: dict[str, Any], engine) -> dict[str, Any]:
    """Materialise C02 without asking libxml2 for any large XPath node-set.

    C02 is almost entirely counters and groupings below the 18 arkivdel nodes.
    On ~1 GB arkivstruktur.xml files libxml2 can emit ``growing nodeset hit
    limit`` even though the surrounding catalogue run continues.  This path
    walks each arkivdel subtree with Python iterators and reconstructs the same
    total/per-arkivdel result contract.
    """
    parts = _safe_archive_parts(tree)
    rows: list[dict[str, Any]] = []
    whole_medium: Counter[str] = Counter()
    whole_status: Counter[str] = Counter()
    created_dates: list[str] = []
    closed_dates: list[str] = []
    archive_part_records: list[dict[str, Any]] = []

    total_folders = 0
    total_registrations = 0
    total_descriptions = 0

    for index, part in enumerate(parts, 1):
        folder_count = 0
        registration_count = 0
        description_count = 0
        medium_counts: Counter[str] = Counter()

        for elem in part.iterdescendants():
            if not isinstance(elem.tag, str):
                continue
            tag = elem.tag
            if tag == "mappe":
                folder_count += 1
            elif tag == "registrering":
                registration_count += 1
            elif tag == "dokumentbeskrivelse":
                description_count += 1
                medium = _direct_child_text(elem, "dokumentmedium")
                if medium:
                    medium_counts[medium] += 1

        system_id = _direct_child_text(part, "systemID")
        title = _direct_child_text(part, "tittel")
        status = _direct_child_text(part, "arkivdelstatus")
        created = _direct_child_text(part, "opprettetDato")
        closed = _direct_child_text(part, "avsluttetDato")

        if status:
            whole_status[status] += 1
        if created:
            created_dates.append(created)
        if closed:
            closed_dates.append(closed)

        total_folders += folder_count
        total_registrations += registration_count
        total_descriptions += description_count
        whole_medium.update(medium_counts)

        part_values = {
            "folder_count": folder_count,
            "registration_count": registration_count,
            "document_description_count": description_count,
            "document_medium_counts": dict(sorted(medium_counts.items(), key=lambda item: item[0].casefold())),
            "archive_part_created_date_range": _range_from_values([created]),
            "archive_part_closed_date_range": _range_from_values([closed]),
        }
        rows.append({
            "archive_part": {
                "index": index,
                "system_id": system_id,
                "title": title,
                "status": status,
            },
            "values": part_values,
        })
        archive_part_records.append({
            "system_id": system_id,
            "title": title,
            "description": _direct_child_text(part, "beskrivelse"),
            "status": status,
            "document_medium": _direct_child_text(part, "dokumentmedium"),
            "archive_period_start_date": _direct_child_text(part, "arkivperiodeStartDato"),
            "archive_period_end_date": _direct_child_text(part, "arkivperiodeSluttDato"),
            "created_date": created,
            "closed_date": closed,
        })

    values: dict[str, Any] = {
        "archive_part_count": len(parts),
        "folder_count": total_folders,
        "registration_count": total_registrations,
        "document_description_count": total_descriptions,
        "document_medium_counts": dict(sorted(whole_medium.items(), key=lambda item: item[0].casefold())),
        "archive_part_created_date_range": _range_from_values(created_dates),
        "archive_part_closed_date_range": _range_from_values(closed_dates),
        "archive_part_records": archive_part_records,
        "archive_part_status_counts": dict(sorted(whole_status.items(), key=lambda item: item[0].casefold())),
        "_archive_parts": rows,
    }

    specs = execution.get("reconciliation") or []
    if specs:
        values["_reconciliation"] = engine._reconcile(values, rows, specs)
        statuses = [entry.get("status") for entry in values["_reconciliation"].values()]
        values["_reconciliation_summary"] = {
            "checks": len(statuses),
            "matches": sum(1 for status in statuses if status == "match"),
            "mismatches": sum(1 for status in statuses if status == "mismatch"),
            "not_comparable": sum(1 for status in statuses if status == "not_comparable"),
            "status": (
                "match"
                if statuses and all(status == "match" for status in statuses)
                else "not_comparable"
                if statuses and all(status == "not_comparable" for status in statuses)
                else "review"
            ),
        }
    return values



def _c01_values_iterparse_file(source: Path) -> dict[str, Any]:
    """Materialise C01 directly from disk without building a full XML tree.

    C01 has a tiny result contract (archives, archive creators and archive
    status counts), so a full ``etree.parse``/normalisation pass is unnecessary
    and risky on very large ``arkivstruktur.xml`` files.  This streaming path
    keeps only the currently active archive/archive-creator fields in memory.
    """
    archives: list[dict[str, Any]] = []
    creators: list[dict[str, Any]] = []
    status_counts: Counter[str] = Counter()

    archive_fields = {
        "systemID", "tittel", "beskrivelse", "arkivstatus",
        "dokumentmedium", "opprettetDato", "avsluttetDato",
        "opprettetAv", "avsluttetAv",
    }
    creator_fields = {"arkivskaperNavn", "arkivskaperID", "beskrivelse"}

    archive_stack: list[dict[str, str]] = []
    creator_stack: list[dict[str, str]] = []

    context = etree.iterparse(
        str(source),
        events=("start", "end"),
        resolve_entities=False,
        no_network=True,
        huge_tree=True,
    )

    for event, elem in context:
        tag = _local_name(elem.tag)

        if event == "start":
            if tag == "arkiv":
                archive_stack.append({})
            elif tag == "arkivskaper":
                creator_stack.append({})
            continue

        parent = elem.getparent()
        parent_tag = _local_name(parent.tag) if parent is not None else ""

        if creator_stack and parent_tag == "arkivskaper" and tag in creator_fields:
            creator_stack[-1][tag] = _text(elem)

        if archive_stack and parent_tag == "arkiv" and tag in archive_fields:
            archive_stack[-1][tag] = _text(elem)

        if tag == "arkivskaper" and creator_stack:
            fields = creator_stack.pop()
            creators.append({
                "name": str(fields.get("arkivskaperNavn", "") or ""),
                "id": str(fields.get("arkivskaperID", "") or ""),
                "description": str(fields.get("beskrivelse", "") or ""),
            })

        elif tag == "arkiv" and archive_stack:
            fields = archive_stack.pop()
            status = str(fields.get("arkivstatus", "") or "").strip()
            if status:
                status_counts[status] += 1
            archives.append({
                "system_id": str(fields.get("systemID", "") or ""),
                "title": str(fields.get("tittel", "") or ""),
                "description": str(fields.get("beskrivelse", "") or ""),
                "status": status,
                "document_medium": str(fields.get("dokumentmedium", "") or ""),
                "created_date": str(fields.get("opprettetDato", "") or ""),
                "closed_date": str(fields.get("avsluttetDato", "") or ""),
                "created_by": str(fields.get("opprettetAv", "") or ""),
                "closed_by": str(fields.get("avsluttetAv", "") or ""),
            })

        # Do not retain processed siblings.  Memory use follows the active
        # parser window instead of the size of arkivstruktur.xml.
        elem.clear()
        parent = elem.getparent()
        if parent is not None:
            while elem.getprevious() is not None:
                del parent[0]

    return {
        "archive_count": len(archives),
        "archive_creator_count": len(creators),
        "archive_records": archives,
        "archive_creator_records": creators,
        "archive_status_counts": dict(
            sorted(status_counts.items(), key=lambda item: item[0].casefold())
        ),
    }


def _c01_values_streaming(tree: etree._ElementTree) -> dict[str, Any]:
    """Materialise C01 without libxml2 XPath node-set construction.

    The archive/creator test is structurally small in its result, but on very
    large arkivstruktur.xml documents a leading // XPath can still make
    libxml2 build a huge intermediate node-set.  Walk the tree once instead.
    """
    archives: list[dict[str, Any]] = []
    creators: list[dict[str, Any]] = []
    status_counts: Counter[str] = Counter()

    for elem in _root(tree).iter():
        if not isinstance(elem.tag, str):
            continue
        if elem.tag == "arkiv":
            status = _direct_child_text(elem, "arkivstatus")
            if status:
                status_counts[status] += 1
            archives.append({
                "system_id": _direct_child_text(elem, "systemID"),
                "title": _direct_child_text(elem, "tittel"),
                "description": _direct_child_text(elem, "beskrivelse"),
                "status": status,
                "document_medium": _direct_child_text(elem, "dokumentmedium"),
                "created_date": _direct_child_text(elem, "opprettetDato"),
                "closed_date": _direct_child_text(elem, "avsluttetDato"),
                "created_by": _direct_child_text(elem, "opprettetAv"),
                "closed_by": _direct_child_text(elem, "avsluttetAv"),
            })
        elif elem.tag == "arkivskaper":
            creators.append({
                "name": _direct_child_text(elem, "arkivskaperNavn"),
                "id": _direct_child_text(elem, "arkivskaperID"),
                "description": _direct_child_text(elem, "beskrivelse"),
            })

    return {
        "archive_count": len(archives),
        "archive_creator_count": len(creators),
        "archive_records": archives,
        "archive_creator_records": creators,
        "archive_status_counts": dict(
            sorted(status_counts.items(), key=lambda item: item[0].casefold())
        ),
    }


def _install_c01_c02_streaming_run_test(engine) -> None:
    if getattr(engine, "_a13_c01_c02_streaming_installed", False):
        return
    original_run_test = engine.run_test

    def run_test(test, extraction_root, standard_registry=None):
        test_id = str(test.get("test_id") or "")
        if test_id not in {"kdrs.c01", "kdrs.c02"}:
            return original_run_test(test, extraction_root, standard_registry=standard_registry)

        extraction_root = Path(extraction_root)
        if test.get("legacy", {}).get("job_enabled") == 0:
            return original_run_test(test, extraction_root, standard_registry=standard_registry)
        source = extraction_root / test["source_xml"]
        if not source.is_file():
            return original_run_test(test, extraction_root, standard_registry=standard_registry)

        started = datetime.now().astimezone()
        timer = time.perf_counter()
        strategy = "a13-c01-file-iterparse" if test_id == "kdrs.c01" else "a13-c02-file-iterparse"
        result = {
            "result_format_version": 2,
            "test_id": test["test_id"],
            "definition": test,
            "status": "not_run",
            "source_xml": test["source_xml"],
        }
        try:
            if test_id == "kdrs.c01":
                # C01 must bypass _normalise_tree as well.  The previous a13.8
                # path still parsed/normalised the complete ~1 GB XML before
                # using Python iteration, which could trigger libxml2's
                # "growing nodeset hit limit" before the C01 evaluator ran.
                values = _c01_values_iterparse_file(source)
            else:
                # C02 must not construct the normalized full tree first.
                # Stream directly from the source file so no broad // XPath
                # or full-document node-set is ever materialised.
                values = _c02_values_iterparse_file(source, test["execution"], engine)
            checks = test.get("standard_value_checks") or []
            if checks:
                values["_standard_values"] = engine._standard_value_checks(
                    values, checks, standard_registry
                )
            result.update({
                "status": "ok",
                "source_path": str(source),
                "values": values,
                "execution_strategy": strategy,
            })
        except Exception as exc:
            result.update({
                "status": "error",
                "source_path": str(source),
                "error": f"{type(exc).__name__}: {exc}",
                "execution_strategy": strategy,
            })
        finally:
            finished = datetime.now().astimezone()
            result["timing"] = {
                "started_at": started.isoformat(timespec="milliseconds"),
                "finished_at": finished.isoformat(timespec="milliseconds"),
                "duration_seconds": round(time.perf_counter() - timer, 6),
            }
        return result

    engine.run_test = run_test
    engine._a13_c01_c02_streaming_installed = True

def _install_c02_streaming_run_test(engine) -> None:
    if getattr(engine, "_a13_c02_streaming_installed", False):
        return
    original_run_test = engine.run_test

    def run_test(test, extraction_root, standard_registry=None):
        if str(test.get("test_id") or "") != "kdrs.c02":
            return original_run_test(test, extraction_root, standard_registry=standard_registry)

        extraction_root = Path(extraction_root)
        # Preserve established missing/disabled semantics through the original
        # implementation; the streaming path only replaces real C02 execution.
        if test.get("legacy", {}).get("job_enabled") == 0:
            return original_run_test(test, extraction_root, standard_registry=standard_registry)
        source = extraction_root / test["source_xml"]
        if not source.is_file():
            return original_run_test(test, extraction_root, standard_registry=standard_registry)

        started = datetime.now().astimezone()
        timer = time.perf_counter()
        result = {
            "result_format_version": 2,
            "test_id": test["test_id"],
            "definition": test,
            "status": "not_run",
            "source_xml": test["source_xml"],
        }
        try:
            tree = engine._normalise_tree(source)
            values = _c02_values_streaming(tree, test["execution"], engine)
            checks = test.get("standard_value_checks") or []
            if checks:
                values["_standard_values"] = engine._standard_value_checks(
                    values,
                    checks,
                    standard_registry,
                )
            result.update({
                "status": "ok",
                "source_path": str(source),
                "values": values,
                "execution_strategy": "a13-c02-python-streaming",
            })
        except Exception as exc:
            result.update({
                "status": "error",
                "source_path": str(source),
                "error": f"{type(exc).__name__}: {exc}",
                "execution_strategy": "a13-c02-python-streaming",
            })
        finally:
            finished = datetime.now().astimezone()
            result["timing"] = {
                "started_at": started.isoformat(timespec="milliseconds"),
                "finished_at": finished.isoformat(timespec="milliseconds"),
                "duration_seconds": round(time.perf_counter() - timer, 6),
            }
        return result

    engine.run_test = run_test
    engine._a13_c02_streaming_installed = True


def _available_memory_bytes() -> int | None:
    if os.name == "nt":
        try:
            import ctypes

            class MEMORYSTATUSEX(ctypes.Structure):
                _fields_ = [
                    ("dwLength", ctypes.c_ulong),
                    ("dwMemoryLoad", ctypes.c_ulong),
                    ("ullTotalPhys", ctypes.c_ulonglong),
                    ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong),
                    ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong),
                    ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
                ]

            state = MEMORYSTATUSEX()
            state.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
            if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(state)):
                return int(state.ullAvailPhys)
        except Exception:
            return None
    try:
        pages = os.sysconf("SC_AVPHYS_PAGES")
        page_size = os.sysconf("SC_PAGE_SIZE")
        return int(pages) * int(page_size)
    except (AttributeError, OSError, ValueError):
        return None


def _cache_budget_allows(path: Path) -> bool:
    try:
        size = path.stat().st_size
    except OSError:
        return False
    available = _available_memory_bytes()
    if available is None:
        return size <= 256 * 1024 * 1024
    # A normalized libxml2 tree can require several times the source size.
    # Keep a conservative 8x estimate and never reserve more than 40% of
    # currently available physical memory for the reusable tree.
    estimate = max(size * 8, 256 * 1024 * 1024)
    return estimate <= int(available * 0.40)


def _normalise_tree_scalable(path: Path) -> etree._ElementTree:
    path = Path(path)
    key = str(path.resolve()).casefold()
    try:
        stat = path.stat()
        signature = (int(stat.st_size), int(stat.st_mtime_ns))
    except OSError:
        signature = (-1, -1)

    cached = _TREE_CACHE.get(key)
    if cached is not None and cached[0] == signature:
        return cached[1]

    parser = etree.XMLParser(resolve_entities=False, no_network=True, huge_tree=True)
    tree = etree.parse(str(path), parser)
    root = tree.getroot()
    for node in root.iter():
        if not isinstance(node.tag, str):
            continue
        node.tag = etree.QName(node).localname
        if node.attrib:
            attrs = {}
            for attr_key, value in node.attrib.items():
                local = etree.QName(attr_key).localname if attr_key.startswith("{") else attr_key
                attrs["type" if local == "type" else local] = value
            node.attrib.clear()
            node.attrib.update(attrs)
    etree.cleanup_namespaces(root)

    # The large Noark structure is repeatedly queried by many catalogue tests.
    # Reusing it is both faster and less memory-intensive than parse+deepcopy for
    # every test. Keep only this dominant source and only when Auto deems it safe.
    if path.name.casefold() == "arkivstruktur.xml" and _cache_budget_allows(path):
        _TREE_CACHE.clear()
        _TREE_CACHE[key] = (signature, tree)
    return tree


def _clear_tree_cache() -> None:
    _TREE_CACHE.clear()



def _run_catalog_profiled_isolated(
    catalog_path,
    extraction_root,
    output_dir,
    *,
    include_disabled=True,
    execution_profile="normal",
    progress_callback=None,
):
    """Run the heavy lxml/XPath catalogue in a separate Python process.

    The desktop workflow already executes operations on a background thread,
    but long libxml2 calls can still starve Tk repaint/message handling.  a13
    therefore isolates the XPath engine at the process boundary.  The parent
    receives progress events and can terminate the worker when cancellation is
    requested by the caller in future server/worker integrations.
    """
    if os.environ.get("DWM_A13_XPATH_WORKER") == "1":
        # Child process: never recurse. The caller patches this function only
        # in the parent runtime, but keep the guard explicit for safety.
        from . import xpath_diagnostics as diagnostics
        return diagnostics._a13_original_run_catalog_profiled(
            catalog_path,
            extraction_root,
            output_dir,
            include_disabled=include_disabled,
            execution_profile=execution_profile,
            progress_callback=progress_callback,
        )

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    stderr_path = output_dir / "xpath-worker-stderr.log"

    with tempfile.TemporaryDirectory(prefix="dwm-a13-xpath-") as td:
        td_path = Path(td)
        request_path = td_path / "request.json"
        result_path = td_path / "result.json"
        # Remove a stale native-stderr log before starting a new worker.
        try:
            stderr_path.unlink()
        except FileNotFoundError:
            pass

        request_path.write_text(
            json.dumps({
                "catalog_path": str(catalog_path),
                "extraction_root": str(extraction_root),
                "output_dir": str(output_dir),
                "stderr_path": str(stderr_path),
                "include_disabled": bool(include_disabled),
                "execution_profile": str(execution_profile),
            }, ensure_ascii=False),
            encoding="utf-8",
        )

        creationflags = 0
        if os.name == "nt":
            creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)

        proc = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "noark5_workflow.a13_xpath_worker",
                str(request_path),
                str(result_path),
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
            creationflags=creationflags,
        )

        messages: queue.Queue[tuple[str, str]] = queue.Queue()

        def reader(stream, kind: str) -> None:
            try:
                for line in iter(stream.readline, ""):
                    messages.put((kind, line.rstrip("\r\n")))
            finally:
                try:
                    stream.close()
                except Exception:
                    pass

        out_thread = threading.Thread(target=reader, args=(proc.stdout, "stdout"), daemon=True)
        err_thread = threading.Thread(target=reader, args=(proc.stderr, "stderr"), daemon=True)
        out_thread.start()
        err_thread.start()
        stderr_lines: list[str] = []

        while proc.poll() is None or not messages.empty():
            try:
                kind, line = messages.get(timeout=0.10)
            except queue.Empty:
                continue
            if kind == "stderr":
                if line:
                    stderr_lines.append(line)
                continue
            if not line.startswith("DWM_A13_EVENT\t"):
                continue
            try:
                event = json.loads(line.split("\t", 1)[1])
            except Exception:
                continue
            if event.get("kind") == "test_progress" and progress_callback is not None:
                progress_callback(
                    event.get("phase"),
                    int(event.get("current") or 0),
                    int(event.get("total") or 0),
                    event.get("test") or {},
                    event.get("status"),
                    event.get("duration"),
                )

        out_thread.join(timeout=2.0)
        err_thread.join(timeout=2.0)
        while not messages.empty():
            kind, line = messages.get_nowait()
            if kind == "stderr" and line:
                stderr_lines.append(line)

        if stderr_lines:
            # Python-level stderr emitted before/around native redirection is
            # appended to the same per-run diagnostic file. Native libxml2
            # output is written there directly by the child process.
            with stderr_path.open("a", encoding="utf-8") as handle:
                handle.write("\n".join(stderr_lines) + "\n")

        payload = {}
        if result_path.is_file():
            try:
                payload = json.loads(result_path.read_text(encoding="utf-8"))
            except Exception:
                payload = {}

        if proc.returncode != 0 or not payload.get("ok"):
            detail = str(payload.get("error") or "XPath-worker avsluttet uten resultat")
            if stderr_lines:
                detail += f". Worker-stderr: {stderr_path}"
            raise RuntimeError(detail)

        return payload.get("index") or {}


def _install_storage_guard() -> None:
    """Give mid-run storage loss an explicit result instead of a generic stop."""
    try:
        from noark5_workflow.executors.local import LocalExecutor
        from noark5_workflow.core.result import OperationResult
    except Exception:
        return
    if getattr(LocalExecutor, "_a13_storage_guard_installed", False):
        return
    original_execute = LocalExecutor.execute

    def guarded_execute(self, operation, ctx):
        checks = (("Source", getattr(ctx, "extraction_root", None)),
                  ("Work", getattr(ctx, "work_operations", None)))
        for label, raw in checks:
            if raw is None:
                continue
            path = Path(raw)
            try:
                available = path.exists()
            except OSError:
                available = False
            if not available:
                return OperationResult(
                    False,
                    f"LAGRING UTILGJENGELIG: {label} kan ikke nås: {path}. "
                    "Kontroller ekstern disk, BitLocker eller nettverkslagring og prøv igjen.",
                )
        try:
            return original_execute(self, operation, ctx)
        except OSError as exc:
            return OperationResult(
                False,
                f"LAGRING UTILGJENGELIG / I/O-feil under {operation.definition.name}: "
                f"{type(exc).__name__}: {exc}",
            )

    LocalExecutor.execute = guarded_execute
    LocalExecutor._a13_storage_guard_installed = True

def _environment() -> dict[str, Any]:
    return {
        "captured_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "platform": platform.platform(),
        "machine": platform.machine(),
        "python": platform.python_version(),
        "python_bits": struct.calcsize("P") * 8,
        "lxml_version": ".".join(str(v) for v in etree.LXML_VERSION),
        "libxml2_version": ".".join(str(v) for v in etree.LIBXML_VERSION),
        "available_memory_bytes": _available_memory_bytes(),
        "large_xml_mode": "auto-iterator-cache",
        "xpath_execution_mode": "subprocess",
        "tree_cache_entries": len(_TREE_CACHE),
    }


def install() -> None:
    """Install a13's large-XML evaluator once for the Noark XPath engine.

    The patch deliberately preserves the catalogue and result model. It changes
    only how high-volume XPath subsets are evaluated: counts, grouping, ranges,
    rows and archive-part iteration use Python element iteration instead of
    libxml2 node-set materialisation. Unsupported expressions fall back to the
    established lxml XPath evaluator.
    """
    global _INSTALLED
    if _INSTALLED:
        return
    _INSTALLED = True

    from . import xpath_test_engine as engine

    original_xpath = engine._xpath
    original_run_catalog = engine.run_catalog
    original_special = engine._special

    engine._normalise_tree = _normalise_tree_scalable
    engine._xpath = lambda node, expression: _safe_xpath(node, expression, original_xpath)
    engine._texts = _safe_texts
    engine._group = _safe_group
    engine._year_counts = _safe_year_counts
    engine._date_range = _safe_date_range
    engine._numeric_values = _safe_numeric_values
    engine._rows = lambda node, spec: _safe_rows(node, spec, original_xpath)
    engine._archive_parts = _safe_archive_parts
    _install_c01_c02_streaming_run_test(engine)

    def safe_special(tree, test, source_path, extraction_root):
        kind = test.get("execution", {}).get("kind")
        if kind == "class_folder_list":
            rows = []
            for cls in _iter_select(tree, "//klasse[mappe]"):
                rows.append({
                    "class_id": original_xpath(cls, "string(klasseID)"),
                    "title": original_xpath(cls, "string(tittel)"),
                    "folder_count": _count_path(cls, "mappe"),
                })
            return {"classes": rows}
        if kind == "empty_class_list":
            return {
                "classes": [
                    {
                        "class_id": original_xpath(cls, "string(klasseID)"),
                        "title": original_xpath(cls, "string(tittel)"),
                    }
                    for cls in _iter_select(tree, "//klasse[not(klasse or mappe)]")
                ]
            }
        if kind == "class_registration_conflict_list":
            return {
                "registrations": [
                    {
                        "class_id": original_xpath(reg, "string(../../klasseID)"),
                        "system_id": original_xpath(reg, "string(systemID)"),
                    }
                    for reg in _iter_select(tree, "//klasse[klasse]/registrering")
                ]
            }
        if kind == "class_registration_list":
            rows = []
            for cls in _iter_select(tree, "//klasse[registrering]"):
                rows.append({
                    "class_id": original_xpath(cls, "string(klasseID)"),
                    "title": original_xpath(cls, "string(tittel)"),
                    "registration_count": _count_path(cls, "registrering"),
                })
            return {"classes": rows}
        return original_special(tree, test, source_path, extraction_root)

    engine._special = safe_special

    def run_catalog_with_environment(*args, **kwargs):
        _clear_tree_cache()
        try:
            index = original_run_catalog(*args, **kwargs)
            index["runtime_environment"] = _environment()
            try:
                output_dir = Path(args[2] if len(args) > 2 else kwargs["output_dir"])
                (output_dir / "index.json").write_text(
                    __import__("json").dumps(index, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8",
                )
            except Exception:
                pass
            return index
        finally:
            _clear_tree_cache()

    engine.run_catalog = run_catalog_with_environment

    # Keep heavy libxml2 work out of the desktop process.  The child sets
    # DWM_A13_XPATH_WORKER=1 before importing analysis, so it receives the
    # iterator/cache patch above but not another process wrapper.
    try:
        from . import xpath_diagnostics as diagnostics
        if not hasattr(diagnostics, "_a13_original_run_catalog_profiled"):
            diagnostics._a13_original_run_catalog_profiled = diagnostics.run_catalog_profiled
        if os.environ.get("DWM_A13_XPATH_WORKER") != "1":
            diagnostics.run_catalog_profiled = _run_catalog_profiled_isolated
    except Exception:
        pass

    _install_storage_guard()
