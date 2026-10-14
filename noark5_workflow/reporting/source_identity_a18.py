"""Conservative source-name identity hints, never authorization or rejection.

Only compare a strong extraction-subseries token on both ends. Historic IDs
can legitimately differ, so municipal/extraction numbers are not compared.
"""
from __future__ import annotations
import re


def _basename(value):
    return str(value or '').replace('\\','/').rstrip('/').rsplit('/',1)[-1]


def _target_token(job):
    for key in ('source_extraction','source','source_path','work_operations'):
        raw=str(getattr(job,key,None) or '').replace('\\','/')
        for component in reversed(raw.split('/')):
            # Strong, specifically identified archival system subgroup.
            m=re.search(r'(?:^|[_ -])ephorte[-_ ](?:hist[-_ ])?([a-z]{2,5})(?:[_ -]|$)', component, re.I)
            if m and m.group(1).lower() not in ('noark','hist'):
                return m.group(1).casefold()
    return None


def _source_token(filename):
    # Restrict hints to unambiguous legacy names with a 2TB partition marker.
    m=re.match(r'^\d{4}_\d{3}[_-]([a-z]{2,5})[_-]2tb(?:[_-]|\.)',_basename(filename),re.I)
    return m.group(1).casefold() if m else None


def source_identity_warnings(job, arkade_runs):
    target=_target_token(job)
    if not target:
        return []
    warnings=[]
    for run in arkade_runs:
        actual=_source_token(run.get('source_file'))
        if actual and actual != target:
            warnings.append({
                'source':'Arkade 5',
                'import_id':run.get('import_id'),
                'source_file':run.get('source_file'),
                'job_subseries':target,
                'file_subseries':actual,
                'status':'Mulig kildetilhørighetsavvik – må kontrolleres manuelt',
            })
    return warnings
