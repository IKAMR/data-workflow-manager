"""Explicit, auditable report-value choices from imported KDRS Query evidence."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .result_bank import build_external_result_bank

FILENAME = 'kdrs-query-report-selections.json'
METRICS = {
    'folder_count': 'Mapper',
    'case_count': 'Saker',
    'registration_count': 'Registreringer',
    'journalpost_count': 'Journalposter',
    'document_description_count': 'Dokumentbeskrivelser',
    'document_object_count': 'Dokumentobjekter',
}


def choice_path(work_operations: str | Path) -> Path:
    return Path(work_operations) / 'external_evidence' / FILENAME


def candidates(work_operations: str | Path, metric: str | None = None) -> list[dict[str, Any]]:
    """Only semantically verified whole-extraction candidates are selectable.

    Old unconstrained number selections are deliberately not offered again.
    """
    from .kdrs_query_mapping import build_mapped_pool
    supported = {'case_count': 'case_folder_count'}
    wanted = supported.get(metric, metric)
    rows = []
    for resource in build_mapped_pool(work_operations).get('resources', []):
        for semantic in resource.get('semantic_lines') or []:
            if semantic.get('archive_part_index') is not None:
                continue
            for fact in semantic.get('facts') or []:
                if fact.get('mapping_status') != 'exact' or fact.get('value_kind') != 'count':
                    continue
                if wanted and fact.get('metric_id') != wanted:
                    continue
                value = fact.get('value')
                if not isinstance(value, int) or value < 0:
                    continue
                rid = resource.get('resource_id') or ''
                line = semantic.get('line_number')
                rows.append({
                    'observation_id': f'{rid}:exact:{line}:{fact["metric_id"]}',
                    'metric_id': fact['metric_id'], 'value': value,
                    'label': fact.get('label') or fact['metric_id'],
                    'line': semantic.get('raw_text') or '',
                    'source_file': resource.get('source_file'),
                    'source_sha256': resource.get('source_sha256'),
                    'report_type': resource.get('report_type'),
                    'archive_part_title': None,
                    'test_id': resource.get('test_id'),
                })
    return rows


def load_choices(work_operations: str | Path) -> dict[str, dict]:
    path = choice_path(work_operations)
    if not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding='utf-8'))
        choices = payload.get('choices') or {}
        return choices if isinstance(choices, dict) else {}
    except (OSError, ValueError, TypeError):
        return {}


def set_choice(work_operations: str | Path, metric: str, observation_id: str) -> Path:
    if metric not in METRICS:
        raise ValueError('Ukjent måltall')
    found = next((item for item in candidates(work_operations, metric)
                  if item['observation_id'] == observation_id), None)
    if found is None:
        raise ValueError('Valgt observasjon finnes ikke i importert evidens')
    if found.get('archive_part_title'):
        raise ValueError('Arkivdelresultat kan ikke brukes som verdi for hele uttrekket')
    if found['value'] < 0 or int(found['value']) != found['value']:
        raise ValueError('Antall må være et ikke-negativt heltall')
    path = choice_path(work_operations)
    path.parent.mkdir(parents=True, exist_ok=True)
    choices = load_choices(work_operations)
    choices[metric] = {'source': 'KDRS Query', **found}
    tmp = path.with_suffix('.tmp')
    tmp.write_text(json.dumps({'format_version': 1, 'choices': choices}, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    tmp.replace(path)
    return path


def selected_count(work_operations: str | Path, metric: str):
    choice = load_choices(work_operations).get(metric)
    if not isinstance(choice, dict):
        return None
    # An old selection cannot silently survive replacement/removal of its evidence.
    match = next((item for item in candidates(work_operations, metric)
                  if item['observation_id'] == choice.get('observation_id')
                  and item['source_sha256'] == choice.get('source_sha256')),
                 None)
    return int(match['value']) if match is not None else None
