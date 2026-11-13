"""Noark metadata references drawn only from shipped, versioned DWM sources.

This is a documented value-set lookup, not a conversion of the full Noark PDF,
Word specification or XSD into JSON. No source document is modified.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
import json
import re

ROOT = Path(__file__).resolve().parents[1]
CATALOG = Path('config/noark5/tests/xpath_catalog_2026_05_26.json')
REGISTRY = Path('config/noark5/standards/noark5_standard_values.json')
MAX_BYTES = 6_000_000


def _load(relative: Path) -> dict:
    file = ROOT / relative
    if not file.is_file() or file.stat().st_size > MAX_BYTES:
        return {}
    data = json.loads(file.read_text(encoding='utf-8-sig'))
    return data if isinstance(data, dict) else {}


@lru_cache(maxsize=1)
def _data():
    catalog = _load(CATALOG)
    registry = _load(REGISTRY)
    tests = {str(t.get('test_id', '')).casefold(): t for t in catalog.get('tests', ())
             if isinstance(t, dict) and t.get('test_id')}
    return tests, registry


def _check(test_id: str, field: str) -> tuple[dict, dict] | None:
    tests, _ = _data()
    test = tests.get(str(test_id).casefold())
    if test is None:
        return None
    for check in test.get('standard_value_checks', ()):
        if isinstance(check, dict) and check.get('id') == field:
            return test, check
    return None


def reference_versions(test_id: str, field: str) -> tuple[str, ...]:
    pair = _check(test_id, field)
    if pair is None:
        return ()
    _, registry = _data()
    _, check = pair
    return tuple(str(v) for v in check.get('versions', ())
                 if registry.get('versions', {}).get(str(v), {}).get('value_sets', {}).get(check.get('value_set_id')))


def reference_for_finding(test_id: str, field: str, version: str) -> dict | None:
    pair = _check(test_id, field)
    if pair is None:
        return None
    test, check = pair
    _, registry = _data()
    value_set_id = str(check.get('value_set_id') or '')
    value_set = (registry.get('versions', {}).get(str(version), {})
                 .get('value_sets', {}).get(value_set_id))
    if not isinstance(value_set, dict):
        return None
    metadata_id = str(value_set.get('metadata_id') or '')
    # Names use catalog registry keys, rather than guessed PDF paragraphs.
    name = value_set_id.split('_', 1)[1] if '_' in value_set_id else field
    # Read the exact metric selector in the catalog when it is available.
    metric_id = check.get('metric_id')
    xpath = ''
    for metric in test.get('execution', {}).get('metrics', ()):
        if isinstance(metric, dict) and metric.get('id') == metric_id:
            xpath = str(metric.get('select') or metric.get('expression') or '')
            break
    if not re.fullmatch(r'M\d{3}', metadata_id):
        return None
    return {
        'test_id': str(test.get('test_id')), 'test_point': str(test.get('legacy', {}).get('test_point') or ''),
        'field': field, 'metadata_id': metadata_id, 'name': name,
        'value_set_id': value_set_id, 'version': str(version),
        'values': tuple(str(v) for v in value_set.get('values', ()) if isinstance(v, str)),
        'value_set_role': str(value_set.get('value_set_role') or ''),
        'source_xml': str(test.get('source_xml') or 'Ikke dokumentert'),
        'xpath': xpath,
        'registry_file': REGISTRY.as_posix(), 'catalog_file': CATALOG.as_posix(),
        'xsd_note': 'Kobling til konkret XSD-element/type er ikke verifisert av dette registeret.',
    }
