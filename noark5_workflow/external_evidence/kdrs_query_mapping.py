"""Traceable, lossless KDRS Query Standard/U1/U2 mapping into DWM result pool.

Coverage is a *candidate relation*, not proof of semantic equivalence.
No source line is discarded, including unparsable and unassigned text.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def _coverage_path() -> Path:
    return Path(__file__).resolve().parents[2] / 'config/noark5/analysis/u1_u2_coverage_2026_05_26.json'


def _catalog_path() -> Path:
    return Path(__file__).resolve().parents[2] / 'config/noark5/tests/xpath_catalog_2026_05_26.json'


def load_mapping_definitions() -> tuple[dict[str, Any], dict[str, Any]]:
    coverage = json.loads(_coverage_path().read_text(encoding='utf-8'))
    catalog = json.loads(_catalog_path().read_text(encoding='utf-8'))
    return coverage, catalog


def _coverage_candidates(coverage: dict[str, Any], report_type: str) -> list[dict[str, Any]]:
    legacy_id = {'u01': 'U01', 'u02': 'U02'}.get(report_type)
    if not legacy_id:
        return []
    return [
        {'area': item.get('id'), 'tests': list(item.get('tests') or []),
         'scope': list(item.get('scope') or []), 'coverage_status': item.get('status')}
        for item in coverage.get('items') or []
        if legacy_id in (item.get('legacy') or [])
    ]


def map_resources(bank: dict[str, Any], *, coverage: dict[str, Any] | None = None,
                  catalog: dict[str, Any] | None = None) -> dict[str, Any]:
    """Map every external line and parsed value with stable source lineage.

    Standard test IDs are catalog matches. U1/U2 have multi-test coverage
    candidates only: values must not be assigned to specific metrics by guessing.
    """
    if coverage is None or catalog is None:
        default_cov, default_cat = load_mapping_definitions()
        coverage = coverage if coverage is not None else default_cov
        catalog = catalog if catalog is not None else default_cat
    known = {str(t.get('test_id')): t for t in catalog.get('tests') or []}
    records = []
    summary = {'resources': 0, 'lines': 0, 'numeric_observations': 0,
               'year_observations': 0, 'unresolved': 0, 'catalog_mapped': 0,
               'coverage_candidates': 0}
    for resource in bank.get('resources') or []:
        if resource.get('source_system') != 'KDRS Query':
            continue
        summary['resources'] += 1
        report_type = str(resource.get('report_type') or '')
        test_id = str(resource.get('test_id') or '')
        matched = test_id in known and report_type == 'standard'
        candidates = ([test_id] if matched else sorted({test for area in _coverage_candidates(coverage, report_type)
                                                         for test in area['tests']}))
        confidence = 'catalog_test' if matched else ('coverage_candidates_only' if candidates else 'unmapped')
        areas = _coverage_candidates(coverage, report_type)
        if matched:
            summary['catalog_mapped'] += 1
        elif candidates:
            summary['coverage_candidates'] += 1
        else:
            summary['unresolved'] += 1
        lines = []
        for line_no, line in enumerate(resource.get('results') or [], start=1):
            line = line if isinstance(line, dict) else {'text': str(line)}
            base = f"{resource.get('resource_id')}:{line_no}"
            observations = []
            for j, value in enumerate(line.get('values') or [], start=1):
                observations.append({'observation_id': f'{base}:numeric:{j}', 'kind': 'parsed_value',
                                     'label': value.get('label'), 'value': value.get('value'),
                                     'metric_id': None, 'mapping_status': 'metric_review_required'})
                summary['numeric_observations'] += 1
            for year, amount in sorted((line.get('year_counts') or {}).items()):
                observations.append({'observation_id': f'{base}:year:{year}', 'kind': 'year_count',
                                     'year': year, 'value': amount, 'metric_id': None,
                                     'mapping_status': 'metric_review_required'})
                summary['year_observations'] += 1
            lines.append({'line_id': base, 'line_number': line_no, 'raw_text': line.get('text') or '',
                          'observations': observations})
            summary['lines'] += 1
        records.append({'resource_id': resource.get('resource_id'), 'source_system': 'KDRS Query',
                        'import_id': resource.get('source_import_id'), 'source_file': resource.get('source_file'),
                        'source_sha256': resource.get('source_sha256'), 'report_type': report_type,
                        'archive_part_index': resource.get('archive_part_index'),
                        'archive_part_title': resource.get('archive_part_title'),
                        'legacy_test_id': resource.get('legacy_job_id'), 'test_id': test_id,
                        'dwm_test_candidates': candidates, 'mapping_status': confidence,
                        'coverage_areas': areas, 'lines': lines,
                        'raw_text': resource.get('raw_text')})
    from .kdrs_query_semantics import attach_semantic_facts
    return attach_semantic_facts({'format_version': 1, 'kind': 'kdrs_query_mapped_result_pool',
            'mapping_policy': 'No implicit metric equivalence or overwriting DWM results',
            'summary': summary, 'resources': records})


def build_mapped_pool(work_operations: str | Path) -> dict[str, Any]:
    from .result_bank import build_external_result_bank
    return map_resources(build_external_result_bank(work_operations))


def write_mapped_pool(work_operations: str | Path) -> Path:
    work = Path(work_operations)
    result = build_mapped_pool(work)
    path = work / 'external_evidence' / 'kdrs-query-mapped-results.json'
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix('.tmp')
    tmp.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    tmp.replace(path)
    return path
