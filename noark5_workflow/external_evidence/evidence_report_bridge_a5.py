"""Read-only reconciliation of a native Noark 5 depot report with KDRS evidence.

Never alters the native report. Unknown or missing DWM counts remain unknown.
Part indices match depot report archive_parts order (1 based); identity included
so users can check imported U2 scope against the destination archive part.
"""
from __future__ import annotations
import json
from pathlib import Path
from typing import Any
from .evidence_report_a5 import evidence_annex

# Supported metrics are exact fields in the native depot report format v2.
METRIC_FIELDS = {
    'archive_count':'archive_count',
    'archive_creator_count':'archive_creator_count',
    'archive_part_count':'archive_part_count',
    'classification_system_count':'classification_system_count',
    'class_count':'class_count',
    'folder_count':'folder_count',
    'registration_count':'registration_count',
    'journalpost_count':'journalpost_count',
    'document_description_count':'document_description_count',
    'document_object_count':'document_object_count',
}


def read_dwm_values(report: dict[str, Any]) -> tuple[dict[str, int | None], dict[int, dict[str, str]]]:
    if report.get('report_type') != 'noark5_depot_validation':
        raise ValueError('Forventet en Noark 5 depotvalideringsrapport')
    values: dict[str, int | None] = {}
    summary = report.get('summary') or {}
    if not isinstance(summary, dict):
        raise ValueError('Ugyldig summary i depotrapport')
    for metric, field in METRIC_FIELDS.items():
        value = summary.get(field)
        values[f'whole:{metric}'] = value if type(value) is int and value >= 0 else None
    parts = report.get('archive_parts') or []
    if not isinstance(parts, list):
        raise ValueError('Ugyldige arkivdeler i depotrapport')
    identities: dict[int, dict[str, str]] = {}
    for index, part in enumerate(parts, 1):
        if not isinstance(part, dict):
            continue
        identity = part.get('archive_part') or {}
        if not isinstance(identity, dict): identity = {}
        identities[index] = {'system_id':str(identity.get('system_id') or ''),
                             'title':str(identity.get('title') or '')}
        for metric in ('folder_count','registration_count','journalpost_count',
                       'document_description_count','document_object_count'):
            value = part.get(METRIC_FIELDS[metric])
            values[f'part:{index}:{metric}'] = value if type(value) is int and value >= 0 else None
    return values, identities


def reconcile_depot_report(report: dict[str, Any], mapped_pool: dict[str, Any],
                           decisions: dict[str, Any]) -> dict[str, Any]:
    values, identities = read_dwm_values(report)
    annex = evidence_annex(mapped_pool,decisions,dwm_values=values)
    for record in annex['records']:
        index = record.get('archive_part_index')
        if type(index) is int:
            record['dwm_archive_part'] = identities.get(index)
            if index not in identities:
                record['scope_review'] = 'archive_part_index_out_of_range'
                record['effective_value'] = None
                record['effective_source'] = None
                record['status'] = 'scope_review_required'
                continue
            # Source title is not sufficient to prove identical scope, so flag
            # a mismatch for review rather than automatically promoting evidence.
            evidence = record.get('evidence')
            title = (evidence or {}).get('archive_part_title') if isinstance(evidence,dict) else None
            expected = identities.get(index,{}).get('title')
            if title and expected and title.strip().casefold() != expected.strip().casefold():
                record['scope_review'] = 'archive_part_title_mismatch'
                record['effective_value'] = record.get('dwm_value')
                record['effective_source'] = 'DWM' if record.get('dwm_value') is not None else None
                record['status'] = 'scope_review_required'
    annex['native_report_type'] = report['report_type']
    annex['native_report_model_format_version'] = report.get('depot_report_model_format_version')
    annex['native_report_unmodified'] = True
    return annex


def write_depot_evidence_companion(report_path: str | Path, work_operations: str | Path) -> Path:
    from .kdrs_query_mapping import build_mapped_pool
    from .evidence_decisions_a5 import load_decisions
    rp = Path(report_path)
    report = json.loads(rp.read_text(encoding='utf-8'))
    result = reconcile_depot_report(report, build_mapped_pool(work_operations),load_decisions(work_operations))
    result['native_report_file'] = rp.name
    # Separate from the native report and beside it, to bind evidence to
    # exactly the same run, with no destructive update to the source file.
    target = rp.with_name('depot-external-evidence.json')
    tmp = target.with_suffix('.tmp')
    tmp.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    tmp.replace(target)
    return target
