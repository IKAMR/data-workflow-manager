"""Read-only inputs to a non-approved, verifiable AIP *candidate* staged under Work.

This is explicitly not a standards-compliant AIP or permission to preserve. The
source extraction is NEVER included, moved, deleted or traversed by this module.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
import hashlib
import json
import os
import shutil
import tempfile
from typing import Any

from noark5_workflow.analysis.canonical_results import _validate_work
from noark5_workflow.analysis.canonical_matrix_v0115_a11 import load_external_status
from version import APP_NAME, VERSION

OUT = 'preservation_staging/dwm-aip-candidate-v1'
INDEX = 'manifest-sha256.json'
CORE = (
    'job.json',
    'noark5_evidence/canonical-results.json',
    'noark5_evidence/canonical-context.json',
    'noark5_evidence/canonical-external-analysis.json',
    'noark5_reports/QUALITY_ASSURANCE_DRAFT.html',
    'noark5_reports/COMPLETION_DECISION_DRAFT.html',
)
MAX_FILES = 128
MAX_TOTAL_BYTES = 1_000_000_000

class PackageCandidateError(ValueError):
    pass

def digest(path: Path) -> str:
    h=hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda:stream.read(1024*1024),b''):
            h.update(block)
    return h.hexdigest()

def _safe_file(root: Path, rel: str) -> Path:
    if not isinstance(rel,str) or not rel or '\\' in rel:
        raise PackageCandidateError('Ugyldig relativ filreferanse')
    p=PurePosixPath(rel)
    if p.is_absolute() or any(x in ('','.', '..') for x in p.parts) or ':' in rel or rel.startswith('/'):
        raise PackageCandidateError('Utrygg sti i evidensreferanse')
    candidate=root.joinpath(*p.parts)
    # No symlinks in any component (not just the terminal file).
    current=root
    for part in p.parts:
        current=current/part
        if current.is_symlink():
            raise PackageCandidateError('Symbolsk lenke i evidensreferanse')
    if not candidate.is_file() or not candidate.resolve().is_relative_to(root.resolve()):
        raise PackageCandidateError('Evidensfil mangler eller ligger utenfor Work')
    return candidate

def _sources(root: Path) -> tuple[list[str],list[str],str]:
    selected=[]; missing=[]
    for name in CORE:
        try: _safe_file(root,name)
        except PackageCandidateError: missing.append(name)
        else: selected.append(name)
    ext=load_external_status(root)
    # Only include explicitly analyzed evidence whose current hash still matches.
    if ext.get('state')=='linked':
        for name,status in sorted(ext.get('sources',{}).items()):
            if status != 'analyzed':
                missing.append('Ekstern evidens ikke verifisert: '+name)
                continue
            if not (name.startswith('external_evidence/') and name.endswith('.json')):
                raise PackageCandidateError('Uventet ekstern kilde utenfor evidensmappe')
            _safe_file(root,name)
            selected.append(name)
    else:
        missing.append('Ekstern analyse: ikke gyldig/tilgjengelig')
    # No double counting and no directory-wide scans.
    return sorted(set(selected)),missing,ext.get('state','not_analyzed')

def prepare_candidate(work: str | Path, *, write: bool=True, generated_at: str | None=None) -> dict[str,Any]:
    root,identity = _validate_work(Path(work))
    root=root.resolve()
    selected,missing,external_status=_sources(root)
    if not selected or 'job.json' not in selected:
        raise PackageCandidateError('Mangler autoritativ Work-identitet')
    if len(selected)>MAX_FILES:
        raise PackageCandidateError('For mange filer til konservativ pakkekandidat')
    sizes={name:_safe_file(root,name).stat().st_size for name in selected}
    if sum(sizes.values())>MAX_TOTAL_BYTES:
        raise PackageCandidateError('Pakkekandidaten overskrider sikker størrelsegrense')
    # File identities and digests reflect what will actually be copied.
    entries=[{'path':name,'bytes':sizes[name],'sha256':digest(_safe_file(root,name))}
             for name in selected]
    blockers=[
        'Kontrollprofilen er ikke godkjent',
        'Arkivskapers aksept er ikke dokumentert i DWM',
        'Depotets ferdigstillingsvedtak er ikke dokumentert',
        'Journalføringsreferanse er ikke dokumentert',
        'Teknisk kontroll og faglig behandling av avvik er ikke ferdigstilt',
        'Source/uttrekksinnhold er ikke pakket i denne kandidaten',
    ]
    blockers += ['Mangler evidens: '+x for x in missing]
    manifest={
      'model_id':'dwm.preservation-staging.candidate.v1',
      'app_name':APP_NAME,'app_version':VERSION,
      'work_job_uid':identity['job_uid'],
      'created_utc':generated_at or datetime.now(timezone.utc).isoformat(timespec='seconds'),
      'status':'candidate_not_approved_not_aip',
      'external_analysis_state':external_status,
      'included_files':entries,
      'missing_sources':missing,
      'open_requirements':blockers,
      'source_included':False,'approval_registered':False,
    }
    if not write:
        return {'output':OUT,'manifest':manifest,'files':len(entries),'missing':len(missing),'status':manifest['status']}
    stage_root=root/'preservation_staging'
    target=root/OUT
    if stage_root.is_symlink() or target.is_symlink():
        raise PackageCandidateError('Utrygt pakkemål')
    stage_root.mkdir(exist_ok=True)
    # Build in a new temporary directory; existing candidate is untouched on error.
    temp=Path(tempfile.mkdtemp(prefix='.aip-candidate-',dir=stage_root))
    try:
        for entry in entries:
            src=_safe_file(root,entry['path'])
            dst=temp/'payload'/entry['path']
            dst.parent.mkdir(parents=True,exist_ok=True)
            # Copy without following symlinks and verify both input and output.
            with src.open('rb') as reader,dst.open('xb') as writer:
                shutil.copyfileobj(reader,writer,1024*1024)
            if digest(src)!=entry['sha256'] or digest(dst)!=entry['sha256']:
                raise PackageCandidateError('Kilde eller kopiert evidens endret under bygging')
        (temp/INDEX).write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
        # No destructive overwrite of an existing candidate; user must explicitly
        # remove/rename old candidate if they need to stage again.
        if target.exists() or target.is_symlink():
            raise PackageCandidateError('Pakkekandidat finnes allerede; beholdt uendret. Gi den et annet navn før ny bygging.')
        temp.rename(target)
    finally:
        if temp.exists():shutil.rmtree(temp)
    return {'output':OUT,'manifest':manifest,'files':len(entries),'missing':len(missing),'status':manifest['status']}

def verify_candidate(work: str | Path) -> dict[str,Any]:
    root,_=_validate_work(Path(work))
    target=root/OUT
    if target.is_symlink() or not target.is_dir():
        raise PackageCandidateError('Pakkekandidat mangler')
    manifest_path=_safe_file(target,INDEX)
    manifest=json.loads(manifest_path.read_text(encoding='utf8'))
    if manifest.get('model_id')!='dwm.preservation-staging.candidate.v1':
        raise PackageCandidateError('Ukjent manifestformat')
    failed=[]
    for entry in manifest.get('included_files',[]):
        try:
            p=_safe_file(target/'payload',entry['path'])
            if p.stat().st_size!=entry['bytes'] or digest(p)!=entry['sha256']:
                failed.append(entry['path'])
        except (PackageCandidateError,OSError,KeyError,TypeError):
            failed.append(entry.get('path','ukjent'))
    return {'verified':not failed,'files':len(manifest['included_files']),
            'failed_files':failed,'status':manifest['status']}
