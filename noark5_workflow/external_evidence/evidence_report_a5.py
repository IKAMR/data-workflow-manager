"""Export an auditable evidence annex. Never mutates the native depot report."""
from __future__ import annotations
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from .evidence_decisions_a5 import exact_candidates, load_decisions, report_evidence


def evidence_annex(pool: dict[str, Any], decisions: dict[str, Any], *,
                   dwm_values: dict[str, int | None] | None = None) -> dict[str, Any]:
    """Compare all exact mapped observations, grouped strictly by metric and scope.

    DWM values are optional and keyed by `whole:metric` / `part:N:metric`.
    In their absence we report external disagreements but do not claim DWM parity.
    """
    dwm_values = dwm_values or {}
    if not isinstance(dwm_values, dict):
        raise TypeError('dwm_values må være en ordbok')
    scopes: set[tuple[str, int | None]] = set()
    for resource in pool.get('resources') or []:
        for line in resource.get('semantic_lines') or []:
            for fact in line.get('facts') or []:
                if fact.get('mapping_status') == 'exact' and fact.get('value_kind') == 'count':
                    metric, part = fact.get('metric_id'), fact.get('archive_part_index')
                    if isinstance(metric, str) and metric and (part is None or (type(part) is int and part > 0)):
                        scopes.add((metric, part))
    for key in set(decisions) | set(dwm_values):
        if not isinstance(key, str) or ':' not in key: continue
        scope, metric = key.rsplit(':', 1)
        if not metric: continue
        if scope == 'whole': scopes.add((metric, None))
        elif scope.startswith('part:') and scope[5:].isdigit() and int(scope[5:]) > 0:
            scopes.add((metric, int(scope[5:])))
    records = []
    for metric, part in sorted(scopes, key=lambda x: (x[1] is not None, x[1] or 0, x[0])):
        key = f"{'whole' if part is None else 'part:'+str(part)}:{metric}"
        dwm = dwm_values.get(key)
        if type(dwm) is not int or dwm < 0: dwm = None
        row = report_evidence(pool, decisions, metric=metric, part_index=part, dwm_value=dwm)
        values = sorted({entry['value'] for entry in row['external_candidates']})
        row['scope_key'] = key
        row['external_unique_values'] = values
        row['external_comparison'] = ('missing' if not values else
                                     'agreement' if len(values) == 1 else 'conflict')
        row['dwm_comparison'] = ('unknown' if dwm is None or not values else
                                 'agreement' if values == [dwm] else
                                 'conflict' if dwm not in values else 'mixed')
        records.append(row)
    return {'format_version': 1, 'kind': 'external_evidence_annex',
            'policy': 'No automatic promotion, summation or mutation of DWM results',
            'summary': dict(Counter(row['external_comparison'] for row in records)),
            'records': records}


def write_evidence_annex(work_operations: str | Path, *,
                         dwm_values: dict[str, int | None] | None = None) -> Path:
    from .kdrs_query_mapping import build_mapped_pool
    work = Path(work_operations)
    annex = evidence_annex(build_mapped_pool(work), load_decisions(work), dwm_values=dwm_values)
    annex['generated_at'] = datetime.now(timezone.utc).isoformat()
    path = work / 'external_evidence' / 'kdrs_query_views' / 'evidence-annex.json'
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix('.tmp')
    tmp.write_text(json.dumps(annex, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    tmp.replace(path)
    return path
