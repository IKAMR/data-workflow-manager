"""a15.4-a15.17: targeted, memory-bounded acceleration of existing XPath metrics.

The optimized paths are strictly equivalent to the corresponding lxml XPath
expressions for namespace-normalised Noark trees. All other metrics use the
original engine unchanged. No persistent mutable cache crosses test runs.
"""
from __future__ import annotations

from collections import Counter, OrderedDict
from bisect import bisect_left
import math
import re
from typing import Any
import json

from lxml import etree

from . import xpath_test_engine as engine
from .xpath_diagnostics import run_catalog_profiled as _run_catalog_profiled

_PARENT_CREATED = "string(ancestor::dokumentbeskrivelse[1]/opprettetDato)"

# Transient, metric-sized result cache. Only active during one run_test call;
# never retains an XML tree or any individual document/date observations.
_parent_date_summaries: dict[tuple[int, str], tuple[dict[str, int], dict[str, int]]] = {}


def _parent_created_summary(node: Any, select: str):
    """Create exact-date and year counters in ONE document-object traversal."""
    key = (id(node), select)
    cached = _parent_date_summaries.get(key)
    if cached is not None:
        return cached
    dates: Counter[str] = Counter()
    years: Counter[str] = Counter()
    for item in _simple_items(node, select):
        value = _parent_created(item).strip()
        if value:
            dates[value] += 1
        if len(value) >= 4 and value[:4].isdigit():
            years[value[:4]] += 1
    result = (
        dict(sorted(dates.items(), key=lambda x: x[0].casefold())),
        dict(sorted(years.items())),
    )
    _parent_date_summaries[key] = result
    return result


def _parent_created(item: etree._Element) -> str:
    """Equivalent to XPath string(ancestor::dokumentbeskrivelse[1]/opprettetDato)."""
    ancestor = item.getparent()
    while ancestor is not None:
        if ancestor.tag == "dokumentbeskrivelse":
            date = ancestor.find("opprettetDato")
            return "" if date is None else "".join(date.itertext())
        ancestor = ancestor.getparent()
    return ""


def _streamable_path(node: Any, select: Any) -> str | None:
    """Safely stream plain full-document and relative descendant paths.

    XPath //x starts from the document root; rewriting it to .//x is only
    equivalent for ElementTree (whole-extraction) context, never a part node.
    """
    if not isinstance(select, str):
        return None
    if _SIMPLE_RELATIVE_ELEMENTS.fullmatch(select):
        return select
    if (isinstance(node, etree._ElementTree)
            and select.startswith("//")
            and _SIMPLE_RELATIVE_ELEMENTS.fullmatch("." + select)):
        # .// excludes the document element while // includes it.
        if node.getroot().tag == select[2:].split("/", 1)[0]:
            return None
        return "." + select
    return None


def _simple_items(node: Any, select: str):
    """Use iterfind for provably equivalent paths; XPath for all others."""
    safe = _streamable_path(node, select)
    return node.iterfind(safe) if safe is not None else node.xpath(select)


def _fast_group(original, node: Any, spec: dict[str, Any]) -> dict[str, int]:
    kind = spec.get("type")
    select = spec.get("select", "")
    # Only optimize cases whose expression/semantics match the original.
    if kind == "group_attr" and spec.get("value", "@type") == "@type":
        counts = Counter()
        for item in _simple_items(node, select):
            if not isinstance(item, etree._Element):
                return original(node, spec)
            value = str(item.get("type") or "").strip()
            if value:
                counts[value] += 1
        return dict(sorted(counts.items(), key=lambda x: x[0].casefold()))
    if kind == "group_text" and _streamable_path(node, select) is not None:
        counts = Counter()
        for item in _simple_items(node, select):
            value = str(engine._scalar(item) or "").strip()
            if value:
                counts[value] += 1
        return dict(sorted(counts.items(), key=lambda x: x[0].casefold()))
    if (kind == "group_xpath" and select in {"//dokumentobjekt", ".//dokumentobjekt"}
            and spec.get("value") == _PARENT_CREATED):
        return _parent_created_summary(node, select)[0].copy()
    return original(node, spec)


def _fast_year_counts(original, node: Any, spec: dict[str, Any]) -> dict[str, int]:
    if spec.get("select") not in {"//dokumentobjekt", ".//dokumentobjekt"} or spec.get("value") != _PARENT_CREATED:
        return original(node, spec)
    return _parent_created_summary(node, spec["select"])[1].copy()


def _exclusive_bucket_index(buckets: list[dict[str, Any]]):
    """Index ordered inclusive intervals only when they cannot overlap.

    A nonoverlapping set permits O(log buckets) lookup per value instead of
    testing each interval. Unsuitable definitions retain their existing path.
    """
    highs = []
    previous_high = None
    for index, bucket in enumerate(buckets):
        low, high = bucket.get("min"), bucket.get("max")
        if not isinstance(bucket.get("id"), str):
            return None
        if low is not None and (not isinstance(low, (int, float)) or math.isnan(low)):
            return None
        if high is not None and (not isinstance(high, (int, float)) or math.isnan(high)):
            return None
        if low is not None and high is not None and low > high:
            return None
        if index and (previous_high is None or low is None or low <= previous_high):
            return None
        if high is None and index < len(buckets) - 1:
            return None
        highs.append(float("inf") if high is None else high)
        previous_high = high
    return highs


def _fast_numeric_buckets(original, node: Any, spec: dict[str, Any]) -> dict[str, int]:
    """Stream numeric values where possible; preserve inclusive, overlapping buckets."""
    buckets = spec.get("buckets")
    if not isinstance(buckets, list):
        return original(node, spec)
    select = spec.get("select", "")
    if _streamable_path(node, select) is None:
        return original(node, spec)
    results = {bucket["id"]: 0 for bucket in buckets}
    # Ordered disjoint intervals use a binary search. Other definitions,
    # including overlapping buckets, preserve legacy multiple-match semantics.
    highs = _exclusive_bucket_index(buckets)
    for item in _simple_items(node, select):
        # Must match _numeric_values: text conversion, whitespace, invalid numbers.
        text = str(engine._scalar(item)).strip()
        if not text:
            continue
        try:
            value = float(text)
        except (TypeError, ValueError):
            continue
        if highs is not None:
            if math.isnan(value):
                continue
            index = bisect_left(highs, value)
            if index < len(buckets):
                bucket = buckets[index]
                low, high = bucket.get("min"), bucket.get("max")
                if (low is None or value >= low) and (high is None or value <= high):
                    results[bucket["id"]] += 1
        else:
            for bucket in buckets:
                low, high = bucket.get("min"), bucket.get("max")
                if (low is None or value >= low) and (high is None or value <= high):
                    results[bucket["id"]] += 1
    return results


def _fast_date_range(original, node: Any, select: str) -> dict[str, str | None]:
    """Find lexicographic first/last dates without a second list and sort.

    This intentionally retains the old semantics: stripped, nonempty text
    values of at least ten characters are compared by their first ten chars.
    No date parsing or normalization is introduced.
    """
    # XPath predicates can change node-selection semantics; keep the
    # original evaluator for complex selections. Ordinary relative
    # .//element paths (also per archive part) remain accelerated.
    if "[" in select or "]" in select:
        return original(node, select)
    first = last = None
    # iterfind avoids a potentially very large temporary XPath result list.
    # Complex XPath retains the original evaluator above.
    iterator = _simple_items(node, select)
    for item in iterator:
        scalar = engine._scalar(item)
        values = scalar if isinstance(scalar, list) else [scalar]
        for value in values:
            if value is None:
                continue
            text = str(value).strip()
            if len(text) < 10:
                continue
            date = text[:10]
            if first is None or date < first:
                first = date
            if last is None or date > last:
                last = date
    return {"first": first, "last": last}



# Simple relative element paths support streaming iterfind without a list of
# every matching XML element. Predicates, functions, attributes, absolute paths,
# namespaces and other XPath constructs retain the original evaluator.
_SIMPLE_RELATIVE_ELEMENTS = re.compile(r"^\.//[A-Za-z_][A-Za-z0-9_.-]*(?:/[A-Za-z_][A-Za-z0-9_.-]*)*$")


def _fast_year_counts_text(original, node: Any, select: str) -> dict[str, int]:
    """Stream year counts for simple descendant paths; preserve original rules.

    The old implementation first materializes XPath nodes, then a second
    list of stripped values. iterfind avoids both for relative element paths.
    Anything more complex is evaluated by the unmodified original handler.
    """
    if _streamable_path(node, select) is None:
        return original(node, select)
    counts = Counter()
    for item in _simple_items(node, select):
        # _scalar is the exact conversion used by the existing _texts helper.
        scalar = engine._scalar(item)
        values = scalar if isinstance(scalar, list) else (scalar,)
        for value in values:
            if value is None:
                continue
            text = str(value).strip()
            if len(text) >= 4:
                counts[text[:4]] += 1
    return dict(sorted(counts.items()))


def _fast_numeric_stats(original, node: Any, select: str) -> dict[str, Any]:
    """Calculate statistics in one pass without retaining every file size.

    Preserve the original float conversion and arithmetic order, including
    errors on non-finite aggregate values and the exact empty result.
    """
    if _streamable_path(node, select) is None:
        return original(node, select)
    count = 0
    total = 0.0
    smallest = largest = None
    for item in _simple_items(node, select):
        text = str(engine._scalar(item)).strip()
        if not text:
            continue
        try:
            value = float(text)
        except (TypeError, ValueError):
            continue
        count += 1
        total += value
        if smallest is None or value < smallest:
            smallest = value
        if largest is None or value > largest:
            largest = value
    if not count:
        return {"count": 0, "sum": 0, "average": None, "min": None, "max": None}
    # Match _numeric_stats: min/max on NaN use Python's input-order semantics.
    return {
        "count": count,
        "sum": int(total) if total.is_integer() else total,
        "average": total / count,
        "min": int(smallest) if smallest.is_integer() else smallest,
        "max": int(largest) if largest.is_integer() else largest,
    }


# Reuse identical whole-extraction metric calculations across individual tests.
# Only scalar counts and bounded distribution dictionaries are retained. Archive
# part metrics deliberately remain uncached: archive-part identity is not
# reliably encoded in XPath expressions alone.
_SHARED_METRIC_LIMIT = 128


def _shared_key(spec: dict[str, Any]):
    kind = spec.get("type", "xpath")
    if kind == "xpath":
        expr = spec.get("expression")
        if not isinstance(expr, str) or not re.fullmatch(r"count\([^()]+\)", expr):
            return None
    elif kind in {"date_range", "year_counts", "numeric_stats"}:
        # A path with predicates or dynamic context is deliberately excluded.
        # These are finite summaries, not row-level results.
        select = spec.get("select")
        if not isinstance(select, str) or not re.fullmatch(
            r"(?:\.//|//)[A-Za-z_][A-Za-z0-9_.-]*(?:/[A-Za-z_][A-Za-z0-9_.-]*)*",
            select,
        ):
            return None
    elif kind not in {"group_text", "group_attr"}:
        return None
    return json.dumps({k: v for k, v in spec.items() if k != "id"}, sort_keys=True, ensure_ascii=False)


def _shared_eval_metrics(original, cache: OrderedDict, source_name: str, node, metrics, part_index=None):
    """Cache only identical calculations in a single source and stable scope.

    Per-part indices come exclusively from the existing _per_parts traversal;
    never infer archive-part identity from titles or XML IDs (which may repeat).
    """
    if not source_name:
        return original(node, metrics)
    if isinstance(node, etree._ElementTree):
        scope = ("whole",)
    elif isinstance(node, etree._Element) and isinstance(part_index, int) and part_index > 0:
        scope = ("part", part_index)
    else:
        return original(node, metrics)
    result = {}
    for spec in metrics:
        key = _shared_key(spec)
        cache_key = (source_name, scope, key) if key is not None else None
        if cache_key is not None and cache_key in cache:
            value = cache[cache_key]
            cache.move_to_end(cache_key)
            result[spec["id"]] = value.copy() if isinstance(value, dict) else value
            continue
        partial = original(node, [spec])
        result.update(partial)
        value = partial[spec["id"]]
        if cache_key is not None and (
            isinstance(value, (int, float)) and not isinstance(value, bool)
            or isinstance(value, dict) and len(value) <= 128
        ):
            cache[cache_key] = value.copy() if isinstance(value, dict) else value
            if len(cache) > _SHARED_METRIC_LIMIT:
                cache.popitem(last=False)
    return result


# a15.15: paired numeric statistics and bucket counts for the same selection.
# The definition is inspected per test; no XML nodes or raw values are cached.
_numeric_bucket_specs: dict[str, dict[str, Any]] = {}
_numeric_pair_results: dict[tuple[int, str], dict[str, int]] = {}


def _numeric_pair_specs(test: Any) -> None:
    _numeric_bucket_specs.clear()
    if not isinstance(test, dict):
        return
    execution = test.get("execution") or {}
    if execution.get("kind") != "metrics":
        return
    for metric_set in (execution.get("metrics") or [], execution.get("archive_part_metrics") or []):
        stats = {s.get("select") for s in metric_set if isinstance(s, dict)
                 and s.get("type") == "numeric_stats"}
        for spec in metric_set:
            if not isinstance(spec, dict) or spec.get("type") != "numeric_buckets":
                continue
            select = spec.get("select")
            buckets = spec.get("buckets")
            if (select in stats and isinstance(select, str)
                    and (bool(_SIMPLE_RELATIVE_ELEMENTS.fullmatch(select))
                         or bool(_SIMPLE_RELATIVE_ELEMENTS.fullmatch("." + select)))
                    and isinstance(buckets, list)
                    and all(isinstance(b, dict) and isinstance(b.get("id"), str)
                            for b in buckets)):
                # Both full and archive-part scopes use the same bucket spec.
                # Do not optimize ambiguous duplicate specifications.
                if select not in _numeric_bucket_specs:
                    _numeric_bucket_specs[select] = spec
                elif _numeric_bucket_specs[select] != spec:
                    _numeric_bucket_specs.pop(select, None)


def _fast_numeric_stats_paired(original, node: Any, select: str) -> dict[str, Any]:
    spec = _numeric_bucket_specs.get(select)
    if spec is None:
        return _fast_numeric_stats(original, node, select)
    buckets = spec["buckets"]
    highs = _exclusive_bucket_index(buckets)
    results = {bucket["id"]: 0 for bucket in buckets}
    count, total = 0, 0.0
    smallest = largest = None
    for item in _simple_items(node, select):
        text = str(engine._scalar(item)).strip()
        if not text:
            continue
        try:
            value = float(text)
        except (TypeError, ValueError):
            continue
        count += 1
        total += value
        if smallest is None or value < smallest:
            smallest = value
        if largest is None or value > largest:
            largest = value
        if highs is not None:
            if not math.isnan(value):
                index = bisect_left(highs, value)
                if index < len(buckets):
                    bucket = buckets[index]
                    low, high = bucket.get("min"), bucket.get("max")
                    if (low is None or value >= low) and (high is None or value <= high):
                        results[bucket["id"]] += 1
        else:
            for bucket in buckets:
                low, high = bucket.get("min"), bucket.get("max")
                if (low is None or value >= low) and (high is None or value <= high):
                    results[bucket["id"]] += 1
    if not count:
        stats = {"count": 0, "sum": 0, "average": None, "min": None, "max": None}
    else:
        # Preserve original float accumulation and conversion semantics.
        stats = {"count": count, "sum": int(total) if total.is_integer() else total,
                 "average": total / count,
                 "min": int(smallest) if smallest.is_integer() else smallest,
                 "max": int(largest) if largest.is_integer() else largest}
    _numeric_pair_results[(id(node), select)] = results
    return stats


def _fast_numeric_buckets_paired(original, node: Any, spec: dict[str, Any]) -> dict[str, int]:
    select = spec.get("select")
    if _numeric_bucket_specs.get(select) == spec:
        cached = _numeric_pair_results.pop((id(node), select), None)
        if cached is not None:
            return cached.copy()
    return _fast_numeric_buckets(original, node, spec)


def run_catalog_profiled(*args, **kwargs):
    """Preserve existing diagnostics and event contract; patch only during run."""
    original_group = engine._group
    original_year = engine._year_counts_by_node
    original_buckets = engine._numeric_buckets
    original_date_range = engine._date_range
    original_year_counts_text = engine._year_counts
    original_numeric_stats = engine._numeric_stats
    original_run_test = engine.run_test
    original_eval_metrics = engine._eval_metrics
    original_per_parts = engine._per_parts
    shared_metrics = OrderedDict()
    active_source = [""]
    active_part = [None]
    active_node = [None]

    def shared_eval(node, metrics):
        index = active_part[0] if node is active_node[0] else None
        return _shared_eval_metrics(original_eval_metrics, shared_metrics,
                                    active_source[0], node, metrics, part_index=index)

    def scoped_per_parts(tree, metrics):
        # Preserve original enumeration, output shape, and part identity.
        rows = []
        for index, part in enumerate(engine._archive_parts(tree), 1):
            active_part[0] = index
            active_node[0] = part
            try:
                values = engine._eval_metrics(part, metrics)
            finally:
                active_part[0] = None
                active_node[0] = None
            rows.append({"archive_part": engine._part_identity(part, index), "values": values})
        return rows

    engine._per_parts = scoped_per_parts

    engine._eval_metrics = shared_eval

    def scoped_run_test(*args, **kwargs):
        _parent_date_summaries.clear()
        _numeric_pair_results.clear()
        active_part[0] = None
        active_node[0] = None
        test = args[0] if args else kwargs.get("test", {})
        _numeric_pair_specs(test)
        active_source[0] = str(test.get("source_xml", "")) if isinstance(test, dict) else ""
        try:
            return original_run_test(*args, **kwargs)
        finally:
            active_source[0] = ""
            active_part[0] = None
            active_node[0] = None
            _parent_date_summaries.clear()
            _numeric_pair_results.clear()
            _numeric_bucket_specs.clear()

    engine.run_test = scoped_run_test
    engine._group = lambda node, spec: _fast_group(original_group, node, spec)
    engine._year_counts_by_node = lambda node, spec: _fast_year_counts(original_year, node, spec)
    engine._numeric_buckets = lambda node, spec: _fast_numeric_buckets_paired(original_buckets, node, spec)
    engine._date_range = lambda node, select: _fast_date_range(original_date_range, node, select)
    engine._year_counts = lambda node, select: _fast_year_counts_text(original_year_counts_text, node, select)
    engine._numeric_stats = lambda node, select: _fast_numeric_stats_paired(original_numeric_stats, node, select)
    try:
        return _run_catalog_profiled(*args, **kwargs)
    finally:
        _parent_date_summaries.clear()
        _numeric_pair_results.clear()
        _numeric_bucket_specs.clear()
        engine.run_test = original_run_test
        engine._eval_metrics = original_eval_metrics
        engine._per_parts = original_per_parts
        shared_metrics.clear()
        engine._group = original_group
        engine._year_counts_by_node = original_year
        engine._numeric_buckets = original_buckets
        engine._date_range = original_date_range
        engine._year_counts = original_year_counts_text
        engine._numeric_stats = original_numeric_stats
