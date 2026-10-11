"""Read-only Arkade 5 quantity-choice candidates for the multi-report GUI.

Only known DWM depot report directories are inspected. Source documents are not read.
"""
from __future__ import annotations

from pathlib import Path


def candidates_for_jobs(jobs, *, joblist=None, source=None):
    """Return documented, unambiguous whole-extraction Arkade totals.

    jobs: selected (job_id, name, extraction_path) tuples.
    Never use JOB-ID alone as the identity of an extraction.
    """
    from tools.noark5_batch_overview_a6 import locate_reports, extract, choose_latest_per_job
    from gui.noark5_overview_evidence_a10 import extraction_root
    wanted = {(str(job), Path(extraction_root(location) or location).name.casefold()) for job, _name, location in jobs}
    reports = set()
    if joblist:
        import json
        data = json.loads(Path(joblist).read_text(encoding='utf-8-sig'))
        for item in data.get('jobs', []):
            if not isinstance(item, dict):
                continue
            root = item.get('source_root') or item.get('source_extraction') or item.get('source_unzipped')
            resolved = extraction_root(root) if root else None
            if not resolved or (str(item.get('job_id')), resolved.name.casefold()) not in wanted:
                continue
            for candidate in [item.get('work_operations'), root]:
                if candidate and Path(candidate).is_dir():
                    reports.update(locate_reports(Path(candidate)))
    elif source and Path(source).is_dir():
        reports.update(locate_reports(Path(source)))
    matches = choose_latest_per_job([extract(p) for p in sorted(reports)])
    choices = []
    for item in matches:
        extraction = Path(item['extraction']).name
        if (str(item['job']), extraction.casefold()) not in wanted:
            continue
        for row in item.get('quantity_comparison', []):
            count = row.get('arkade_count')
            if type(count) is not int or count < 0:
                continue
            choices.append({
                'job': item['job'], 'extraction': extraction,
                'metric': row['metric'], 'source': 'Arkade 5', 'count': count,
                'label': row.get('label') or row['metric'],
                'dwm_count': row.get('dwm_count'),
            })
    return sorted(choices, key=lambda c: (c['extraction'], c['job'], c['metric']))


def selection_key(choice):
    return (choice['job'], choice['extraction'].casefold(), choice['metric'])


def selected_payload(candidates, selected_keys):
    """Revalidate selections against current documented candidates."""
    return {'choices': [
        {key: choice[key] for key in ('job', 'extraction', 'metric', 'source', 'count')}
        for choice in candidates if selection_key(choice) in selected_keys
    ]}
