"""Report-facing projection of accepted external evidence; never mutates DWM reports.

Only a verified explicit decision may change an effective report value. All
other rows preserve the original DWM value (including unknown / None).
"""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
from typing import Any


def effective_projection(native_report: dict[str, Any], annex: dict[str, Any]) -> dict[str, Any]:
    from .evidence_report_bridge_a5 import read_dwm_values
    original, identities = read_dwm_values(native_report)
    rows = {}
    for row in annex.get('records') or []:
        if not isinstance(row, dict):
            continue
        scope = row.get('scope_key')
        if scope not in original or scope in rows:
            continue  # Unknown scopes / duplicates cannot influence a report.
        dwm = original[scope]
        accepted = (row.get('status') == 'external_evidence_selected' and
                    not row.get('scope_review') and
                    isinstance(row.get('evidence'), dict) and
                    type(row.get('effective_value')) is int and
                    row['effective_value'] >= 0 and
                    row.get('effective_source') == 'KDRS Query')
        value = row['effective_value'] if accepted else dwm
        evidence = row.get('evidence') if accepted else None
        rows[scope] = {'dwm_value':dwm, 'effective_value':value,
                       'effective_source':'KDRS Query' if accepted else 'DWM' if dwm is not None else None,
                       'status':'external_evidence_selected' if accepted else row.get('status') or 'original_or_unknown',
                       'evidence':evidence,
                       'dwm_comparison':row.get('dwm_comparison') or 'unknown'}
    for scope, dwm in original.items():
        rows.setdefault(scope, {'dwm_value':dwm, 'effective_value':dwm,
                      'effective_source':'DWM' if dwm is not None else None,
                      'status':'original_or_unknown', 'evidence':None,
                      'dwm_comparison':'unknown'})
    whole = {key.removeprefix('whole:'):value for key,value in rows.items() if key.startswith('whole:')}
    parts = {}
    for index, identity in identities.items():
        prefix = f'part:{index}:'
        parts[str(index)] = {'archive_part':identity,
                 'metrics':{key[len(prefix):]: value for key,value in rows.items() if key.startswith(prefix)}}
    return {'kind':'noark5_effective_evidence_projection', 'format_version':1,
            'native_report_unmodified':True,
            'policy':'Only explicitly selected, scope-verified external evidence; otherwise preserve DWM, including unknowns.',
            'whole':whole,'archive_parts':parts}


def write_effective_projection(report_path: str | Path, companion_path: str | Path) -> Path:
    report_path = Path(report_path)
    companion_path = Path(companion_path)
    raw = report_path.read_bytes()
    native = json.loads(raw.decode('utf-8-sig'))
    annex = json.loads(companion_path.read_text(encoding='utf-8'))
    projection = effective_projection(native, annex)
    projection['native_report_file'] = report_path.name
    projection['native_report_sha256'] = hashlib.sha256(raw).hexdigest()
    projection['evidence_companion_file'] = companion_path.name
    projection['evidence_companion_sha256'] = hashlib.sha256(companion_path.read_bytes()).hexdigest()
    target = report_path.with_name('depot-effective-evidence.json')
    tmp = target.with_suffix('.tmp')
    tmp.write_text(json.dumps(projection,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    tmp.replace(target)
    return target
