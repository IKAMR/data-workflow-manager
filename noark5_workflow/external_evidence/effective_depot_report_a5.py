"""Materialize a distinct Noark 5 report view from verified accepted evidence.

The native depot report remains immutable. This is a *derived* report, never an
unqualified replacement for the original DWM analysis.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path

from .evidence_report_bridge_a5 import METRIC_FIELDS, read_dwm_values


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def derive_effective_report(native: dict, projection: dict) -> dict:
    """Return a deep-copied report with explicitly selected, scoped counts only."""
    read_dwm_values(native)  # Verify native report shape before any application.
    result = deepcopy(native)
    applied = []

    def apply(fields: dict, rows: dict, scope: str) -> None:
        if not isinstance(rows, dict):
            raise ValueError('Ugyldig evidensstruktur')
        for metric, field in METRIC_FIELDS.items():
            row = rows.get(metric)
            if not isinstance(row, dict) or row.get('status') != 'external_evidence_selected':
                continue
            if row.get('effective_source') != 'KDRS Query' or not isinstance(row.get('evidence'), dict):
                continue
            value = row.get('effective_value')
            if type(value) is not int or value < 0:
                continue
            original = fields.get(field)
            if original != row.get('dwm_value'):
                raise ValueError(f'DWM-verdien er endret etter evidensvalg: {scope}:{metric}')
            fields[field] = value
            applied.append({'scope':scope, 'metric':metric, 'dwm_value':original,
                            'effective_value':value, 'source':'KDRS Query',
                            'evidence':deepcopy(row['evidence'])})

    apply(result['summary'], projection.get('whole') or {}, 'whole')
    parts = result.get('archive_parts') or []
    for index, part in enumerate(parts, 1):
        item = (projection.get('archive_parts') or {}).get(str(index), {})
        if not isinstance(item, dict):
            continue
        identity = (part.get('archive_part') or {}) if isinstance(part, dict) else {}
        actual = {'system_id':str(identity.get('system_id') or ''),
                  'title':str(identity.get('title') or '')}
        if item.get('archive_part') != actual:
            raise ValueError(f'Arkivdelidentitet er endret: {index}')
        apply(part, item.get('metrics') or {}, f'part:{index}')
    result['external_evidence_application'] = {
        'format_version':1, 'derived_report':True,
        'native_report_unmodified':True, 'applied':applied,
    }
    return result


def write_derived_depot_report(report_path: str | Path,
                               projection_path: str | Path) -> Path:
    report_path, projection_path = Path(report_path), Path(projection_path)
    projection = json.loads(projection_path.read_text(encoding='utf-8'))
    if projection.get('native_report_sha256') != _digest(report_path):
        raise ValueError('Depotrapporten er endret siden evidensgrunnlaget ble generert')
    companion_name = projection.get('evidence_companion_file')
    if not isinstance(companion_name, str) or Path(companion_name).name != companion_name:
        raise ValueError('Ugyldig evidensvedlegg')
    companion = projection_path.parent / companion_name
    if projection.get('evidence_companion_sha256') != _digest(companion):
        raise ValueError('Evidensvedlegget er endret siden evidensgrunnlaget ble generert')
    native = json.loads(report_path.read_text(encoding='utf-8-sig'))
    result = derive_effective_report(native, projection)
    result['external_evidence_application']['native_report_sha256'] = _digest(report_path)
    result['external_evidence_application']['projection_sha256'] = _digest(projection_path)
    destination = report_path.with_name('depot-derived-evidence-report.json')
    temp = destination.with_suffix('.tmp')
    temp.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    temp.replace(destination)
    return destination
