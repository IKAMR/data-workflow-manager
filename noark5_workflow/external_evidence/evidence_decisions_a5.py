"""Auditable external evidence decisions, separate from immutable DWM results.

No external result is silently promoted. A whole-extraction value cannot be
substituted for an archive-part value, nor may U2 values be silently summed.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DECISIONS_FILE = 'external-evidence-decisions.json'
SUPPORTED_REASONS = {'missing_dwm_test', 'invalid_dwm_result', 'verified_external_source'}


def _decisions_path(work_operations: str | Path) -> Path:
    return Path(work_operations) / 'external_evidence' / DECISIONS_FILE


def _scope(part_index: int | None) -> str:
    if part_index is None:
        return 'whole'
    if isinstance(part_index, bool) or not isinstance(part_index, int) or part_index < 1:
        raise ValueError('Ugyldig arkivdelindeks')
    return f'part:{part_index}'


def _evidence_key(metric: str, part_index: int | None) -> str:
    if not metric or not isinstance(metric, str):
        raise ValueError('Måltall mangler')
    return f'{_scope(part_index)}:{metric}'


def exact_candidates(mapped_pool: dict[str, Any], metric: str, *,
                     part_index: int | None = None) -> list[dict[str, Any]]:
    """Return only proven numeric facts for one strict extraction/part scope."""
    _scope(part_index)
    found = []
    for resource in mapped_pool.get('resources') or []:
        for line in resource.get('semantic_lines') or []:
            for fact in line.get('facts') or []:
                if (fact.get('mapping_status') != 'exact' or
                    fact.get('metric_id') != metric or
                    fact.get('value_kind') != 'count' or
                    fact.get('archive_part_index') != part_index):
                    continue
                value = fact.get('value')
                if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                    continue
                digest = fact.get('source_sha256') or resource.get('source_sha256')
                resource_id = fact.get('source_resource_id') or resource.get('resource_id')
                line_number = fact.get('source_line_number')
                if not digest or not resource_id or line_number is None:
                    continue
                found.append({
                    'id': f'{resource_id}:exact:{line_number}:{metric}',
                    'metric_id': metric,
                    'archive_part_index': part_index,
                    'archive_part_title': fact.get('archive_part_title'),
                    'value': value,
                    'source': resource.get('source_system') or 'KDRS Query',
                    'source_import_id': resource.get('import_id'),
                    'source_file': fact.get('source_file') or resource.get('source_file'),
                    'source_sha256': digest,
                    'resource_id': resource_id,
                    'source_line_number': line_number,
                    'report_type': resource.get('report_type'),
                })
    return found


def load_decisions(work_operations: str | Path) -> dict[str, Any]:
    p = _decisions_path(work_operations)
    if not p.is_file():
        return {}
    doc = json.loads(p.read_text(encoding='utf-8'))
    if doc.get('format_version') != 1 or not isinstance(doc.get('decisions'), dict):
        raise ValueError('Ukjent format for evidensbeslutninger')
    return doc['decisions']


def select_evidence(work_operations: str | Path, mapped_pool: dict[str, Any],
                    *, metric: str, evidence_id: str, reason: str,
                    part_index: int | None = None, note: str = '') -> Path:
    """Record an explicit choice; reject unmapped/stale/ambiguous observations."""
    if reason not in SUPPORTED_REASONS:
        raise ValueError('Valg av ekstern evidens krever en gyldig begrunnelse')
    candidates = [r for r in exact_candidates(mapped_pool, metric, part_index=part_index)
                  if r['id'] == evidence_id]
    if len(candidates) != 1:
        raise ValueError('Observasjonen er ikke entydig, eksakt mappet eller tilgjengelig')
    item = candidates[0]
    decisions = load_decisions(work_operations)
    key = _evidence_key(metric, part_index)
    decisions[key] = {**item, 'reason': reason, 'note': str(note).strip(),
                      'selected_at': datetime.now(timezone.utc).isoformat()}
    p = _decisions_path(work_operations)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix('.tmp')
    tmp.write_text(json.dumps({'format_version': 1, 'decisions': decisions},
                              ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    tmp.replace(p)
    return p


def report_evidence(mapped_pool: dict[str, Any], decisions: dict[str, Any],
                    *, metric: str, part_index: int | None = None,
                    dwm_value: int | None = None) -> dict[str, Any]:
    """Resolve displayed evidence without ever changing DWM's own value.

    No selection means DWM wins, even if external sources agree on another
    value. If the selected source file changes, selection becomes stale.
    """
    key = _evidence_key(metric, part_index)
    source = decisions.get(key)
    result = {'metric_id': metric, 'archive_part_index': part_index,
              'dwm_value': dwm_value, 'effective_value': dwm_value,
              'effective_source': 'DWM' if dwm_value is not None else None,
              'status': 'dwm' if dwm_value is not None else 'missing',
              'external_candidates': exact_candidates(mapped_pool, metric, part_index=part_index)}
    if not isinstance(source, dict):
        return result
    verified = next((item for item in result['external_candidates']
                     if item['id'] == source.get('id') and
                     item['source_sha256'] == source.get('source_sha256') and
                     item['value'] == source.get('value') and
                     item['source_import_id'] == source.get('source_import_id')), None)
    if verified is None:
        result['status'] = 'stale_evidence_selection'
        return result
    if source.get('reason') not in SUPPORTED_REASONS:
        result['status'] = 'invalid_evidence_reason'
        return result
    result.update({'effective_value': verified['value'], 'effective_source': verified['source'],
                   'status': 'external_evidence_selected', 'evidence': {**verified,
                     'reason': source['reason'], 'note': source.get('note', ''),
                     'selected_at': source.get('selected_at')}})
    return result
