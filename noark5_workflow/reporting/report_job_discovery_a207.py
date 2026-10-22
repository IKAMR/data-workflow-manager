"""a20.7: reconstruct a REPORT-ONLY job list from a Noark 5 collection.

No XML/DOKUMENT traversal, imported evidence conversion, workflow replay or source
writes.  A missing depot report never hides an otherwise recognizable extraction.
The original report reader still owns the interpretation of numeric evidence.
"""
from __future__ import annotations

import json
import hashlib
import re
import shutil
import tempfile
import zipfile
from uuid import uuid4
from dataclasses import dataclass
from pathlib import Path
from threading import Event
from typing import Callable

from .report_job_recovery_a204 import (
    RecoveryError, RecoveryCancelled, discover_report_jobs,
    _candidate_dwm_roots, _extraction_ancestor, _check_cancel,
)

_JOB_ID = re.compile(r'^JOB-\d{3,}$', re.I)
_EXTRACTION = re.compile(r'^\d{4}_\d{3}(?!\d)')
_PATH_ID = re.compile(r'(?<!\d)(\d{4}_\d{3})(?!\d)')
_MAX_LEGACY_BYTES = 8 * 1024 * 1024
_EVIDENCE_NAMES = ('noark5_reports', 'noark5_tests', 'noark5_views', 'external_evidence', 'wf')


@dataclass(frozen=True)
class ReportCandidate:
    job_id: str                    # unique within the NEW job list
    name: str                      # archive extraction folder, not a guessed LABEL
    work_operations: Path | None   # actual DWM work root if present
    extraction_folder: Path | None
    evidence: tuple[str, ...]
    report_file: Path | None
    source_job_id: str | None      # original list-local JOB-NNN, if verified
    manifest_verified: bool
    original_runs: int = 0
    legacy_job_list: Path | None = None
    archived_zips: tuple[Path, ...] = ()
    archive_report_zip: Path | None = None
    archive_report_member: str = ""
    archive_report_crc: int | None = None
    archive_report_length: int | None = None
    report_needs_cache: bool = False

    @property
    def has_report(self) -> bool:
        return self.report_file is not None or self.archive_report_zip is not None


@dataclass(frozen=True)
class ReportDiscoveryPlan:
    scanned_root: Path
    jobs: tuple[ReportCandidate, ...]
    warnings: tuple[str, ...]
    report_roots: tuple[Path, ...]
    extraction_folders: tuple[Path, ...]
    existing_job_lists: tuple[Path, ...]
    archived_dwm_zips: tuple[Path, ...]
    missing_report_extractions: tuple[Path, ...]


def _legacy_jobs(files: tuple[Path, ...], extractions: tuple[Path, ...], warnings: list[str]):
    """Only map an old job if a path names exactly one known extraction.

    Never import its workflow, stale disk letters, run state, or automatic
    approval status. An old root joblist may also describe unrelated extracts.
    """
    known = {_PATH_ID.search(ex.name).group(1): ex for ex in extractions
             if _PATH_ID.search(ex.name)}
    by_extraction = {}
    for path in files:
        try:
            if path.stat().st_size > _MAX_LEGACY_BYTES:
                warnings.append(f'For stor eldre jobbliste, ikke tolket: {path}')
                continue
            document = json.loads(path.read_text(encoding='utf-8-sig'))
        except (OSError, UnicodeError, ValueError) as exc:
            warnings.append(f'Eldre jobbliste kunne ikke tolkes: {path}: {exc}')
            continue
        rows = document.get('jobs') if isinstance(document, dict) else None
        if not isinstance(rows, list):
            warnings.append(f'Eldre jobbliste uten lesbar jobs-liste: {path}')
            continue
        for entry in rows:
            if not isinstance(entry, dict):
                continue
            values = [str(entry.get(key) or '') for key in
                      ('source_extraction', 'source_root', 'source_unzipped', 'work_operations',
                       'work_root', 'name')]
            ids = {m.group(1) for value in values for m in _PATH_ID.finditer(value)}
            matched = {known[key] for key in ids if key in known}
            if len(matched) != 1:
                continue
            extraction = next(iter(matched))
            jid = str(entry.get('job_id') or '').upper()
            if not _JOB_ID.fullmatch(jid):
                continue
            by_extraction.setdefault(extraction, []).append((path, jid))
    return by_extraction


def _existing_work_areas(extraction: Path):
    """Inspect only fixed directories; do not descend into content/SIP/archives."""
    base = extraction / 'repository_operations'
    if not base.is_dir():
        return ()
    result = []
    try:
        roots = (base / 'dwm',)
        for root in roots:
            if not root.is_dir() or root.is_symlink():
                continue
            result.append(root)
            for child in root.iterdir():
                if child.is_dir() and not child.is_symlink() and not getattr(child, 'is_junction', lambda:False)():
                    # b01/b02/b03 are DWM's job-list output variants.
                    if re.fullmatch(r'[a-z]\d{2,3}', child.name, re.I):
                        result.append(child)
    except OSError as exc:
        raise RecoveryError(f'Kan ikke lese DWM-arbeidsområder for {extraction}: {exc}') from exc
    return tuple(result)


def _work_evidence(root: Path) -> tuple[str, ...]:
    names = set()
    for dirname in _EVIDENCE_NAMES:
        try:
            if (root / dirname).is_dir():
                names.add(dirname)
        except OSError as exc:
            raise RecoveryError(f'Lagringsmediet er utilgjengelig: {root}: {exc}') from exc
    return tuple(sorted(names))


def _choose_work_root(extraction: Path, report_job) -> tuple[Path | None, tuple[str, ...]]:
    areas = _existing_work_areas(extraction)
    if report_job is not None:
        root = report_job.work_operations
        return root, _work_evidence(root)
    ranked = []
    for area in areas:
        evidence = _work_evidence(area)
        # Prefer the actual materialized DWM root with stored XPath results.
        score = 10 * ('noark5_tests' in evidence) + 7 * ('noark5_views' in evidence) + \
                4 * ('external_evidence' in evidence) + 2 * ('noark5_reports' in evidence) + \
                ('wf' in evidence)
        ranked.append((score, len(evidence), area, evidence))
    if ranked:
        _score, _length, path, evidence = max(ranked, key=lambda t:(t[0],t[1],str(t[2])))
        return path, evidence
    # Do not assign a nonexistent DWM directory: opening the list must not
    # create DWM output on an otherwise archival/source-only extraction.
    return None, ()


def _legacy_evidence(extraction: Path):
    base = extraction / 'repository_operations'
    indicators = []
    for subpath, label, glob in (
        ('analyse', 'KDRS Query (eldre kildefiler)', '*noark5-xpath-report*.txt'),
        ('arkade5_v2.12.3/folder', 'Arkade 5 (eldre resultat)', '*testrapport*.json'),
        ('arkade5_v2.13.1/folder', 'Arkade 5 (eldre resultat)', 'arkade-testrapporter_*'),
    ):
        folder = base.joinpath(*subpath.split('/'))
        if folder.is_dir():
            try:
                if next(folder.glob(glob), None) is not None and label not in indicators:
                    indicators.append(label)
            except OSError as exc:
                raise RecoveryError(f'Kan ikke kontrollere {folder}: {exc}') from exc
    return tuple(indicators)


def _shared_zip_inventory(root: Path, extractions: tuple[Path, ...]):
    """Inspect the historical flat _noark5 ZIP directory, never its subtrees.

    Only exact FFKK_nnn matches are linked. Generic 1539_nnn is ambiguous
    until a user reviews it, even if there is only one known extraction.
    """
    folder=root/'_noark5'
    if not folder.is_dir() or folder.is_symlink() or getattr(folder,'is_junction',lambda:False)():
        return ()
    found=[]
    for index,item in enumerate(folder.iterdir()):
        if index >= 3000:
            raise RecoveryError('For mange filer i felles _noark5-mappe; velg et smalere søk.')
        if item.is_file() and item.suffix.lower()=='.zip' and 'dwm' in item.name.casefold():
            if re.match(r'^\d{4}_\d{3}(?!\d)',item.name):
                found.append(item)
    return tuple(sorted(found,key=str))


def _zip_hints(extraction: Path, all_zips: tuple[Path, ...]) -> tuple[Path, ...]:
    root = extraction/'repository_operations'
    match = _PATH_ID.search(extraction.name)
    identifier = match.group(1).lower() if match else ''
    return tuple(path for path in all_zips
                 if path.parent == root or
                 (path.parent.name.lower() == '_noark5' and identifier and
                  path.name.lower().startswith(identifier) and
                  (len(path.name)==len(identifier) or not path.name[len(identifier)].isdigit())))


def _zip_report_hint(archives: tuple[Path, ...], warnings: list[str], *, extraction: Path):
    """Inspect only the ZIP directory and one bounded saved depot JSON.

    This is NOT a generic ZIP extractor. Older DWM packages with just XPath
    snapshots are inventoried, not called finished depot validations.
    """
    possible = []
    match=_PATH_ID.search(extraction.name)
    expected_id=match.group(1) if match else ''
    for archive in archives[:16]:
        try:
            with zipfile.ZipFile(archive) as handle:
                entries = handle.infolist()
                if len(entries) > 40000:
                    warnings.append(f'ZIP har for mange oppføringer, hoppet over: {archive.name}')
                    continue
                named={part.filename.replace('\\','/'):part for part in entries}
                for item in entries:
                    path = item.filename.replace('\\', '/')
                    segments = path.strip('/').split('/')
                    if (len(segments) < 4 or segments[-1] != 'depot_validation_report.json'
                            or segments[-3] != 'depot_validation'
                            or segments[-4] != 'noark5_reports'):
                        continue
                    run_name = segments[-2]
                    m = re.match(r'^(JOB-\d{3,})__', run_name, re.I)
                    if not m or item.file_size > 32 * 1024 * 1024 or item.file_size < 8:
                        continue
                    manifest_name=path.rsplit('/',1)[0]+'/artifact_manifest.json'
                    meta=named.get(manifest_name)
                    if meta is not None and meta.file_size <= 256*1024:
                        source_meta=json.loads(handle.read(meta).decode('utf-8-sig'))
                        if not isinstance(source_meta,dict):
                            continue
                        provenance_id=str(source_meta.get('job_id') or '').upper()
                        if provenance_id and provenance_id != m.group(1).upper():
                            warnings.append('ZIP-manifest har motstridende JOB-ID: '+archive.name)
                            continue
                        source=str(source_meta.get('source_extraction') or '')
                        actual={x.group(1) for x in _PATH_ID.finditer(source)}
                        if expected_id and actual and expected_id not in actual:
                            warnings.append('ZIP-manifest peker til annet uttrekk enn '+extraction.name+': '+archive.name)
                            continue
                    if item.compress_size == 0 or item.file_size > 500 * item.compress_size:
                        continue
                    data = handle.read(item)
                    value = json.loads(data.decode('utf-8-sig'))
                    if not isinstance(value, dict) or (not isinstance(value.get('summary'), dict)
                            and not isinstance(value.get('archive_parts'), list)):
                        continue
                    possible.append((archive.stat().st_mtime_ns, archive, item.filename,
                                     m.group(1).upper(), item.CRC, item.file_size))
        except (OSError, RuntimeError, zipfile.BadZipFile, UnicodeError, ValueError) as exc:
            warnings.append(f'Kunne ikke lese eldre DWM ZIP {archive.name}: {exc}')
    if not possible:
        return None
    if len({row[3] for row in possible}) > 1:
        warnings.append('DWM ZIP inneholder flere forskjellige JOB-ID-er; kan ikke velge '
                        'riktig uttrekk automatisk. ZIP registrert uten rapportimport.')
        return None
    if len(possible) > 1:
        warnings.append(f'Flere arkiverte DWM-depotrapporter funnet; nyeste ZIP-tid valgt. '
                        'Kildeversjon bør kontrolleres ved rapportering.')
    _time, archive, member, original, crc, length = max(possible,
                            key=lambda r:(r[0],r[1].name,r[2]))
    return archive, member, original, crc, length


def _materialize_report(candidate: ReportCandidate, target: Path) -> None:
    """Copy one bounded, confirmed JSON report to a NEW local provenance cache."""
    if candidate.archive_report_zip:
        with zipfile.ZipFile(candidate.archive_report_zip) as handle:
            entry=handle.getinfo(candidate.archive_report_member)
            if (entry.file_size > 32 * 1024 * 1024 or
                    entry.file_size != candidate.archive_report_length or
                    entry.CRC != candidate.archive_report_crc):
                raise RecoveryError('Arkivert depotrapport er endret siden funnet. Start nytt søk.')
            content=handle.read(entry)
        provenance={'kind':'DWM ZIP', 'source':str(candidate.archive_report_zip),
                    'zip_member':candidate.archive_report_member,
                    'original_job_id':candidate.source_job_id}
    elif candidate.report_file:
        if candidate.report_file.stat().st_size > 32 * 1024 * 1024:
            raise RecoveryError('Lagret DWM-depotrapport overskrider tillatt størrelse')
        content=candidate.report_file.read_bytes()
        provenance={'kind':'DWM depotrapport', 'source':str(candidate.report_file),
                    'original_job_id':candidate.source_job_id}
    else:
        raise RecoveryError('Ingen rapport å gjenopprette i lokal cache')
    value=json.loads(content.decode('utf-8-sig'))
    if not isinstance(value, dict) or not (
            isinstance(value.get('summary'),dict) or isinstance(value.get('archive_parts'),list)):
        raise RecoveryError('Ugyldig arkivert depotrapport; ingen data lagret.')
    provenance['sha256_report_json']=hashlib.sha256(content).hexdigest()
    original = candidate.source_job_id or candidate.job_id
    suffix = uuid4().hex[:12]
    run = target/'noark5_reports'/'depot_validation'/(
        candidate.job_id + '__RECOVERED-' + suffix)
    run.mkdir(parents=True, exist_ok=False)
    (run/'depot_validation_report.json').write_bytes(content)
    (run/'recovery_source.json').write_text(json.dumps({
        'schema':'ikamr.dwm.report_recovery.source.a20.7',
        'joblist_job_id':candidate.job_id,
        'original_job_id':original,
        'copied_for_read_only_report':True,
        'provenance':provenance,
    },indent=2,ensure_ascii=False)+'\n',encoding='utf-8')


def discover_available_report_jobs(directory: str | Path, *, cancelled: Event | None = None,
                                   on_progress: Callable[[str], None] | None = None) -> ReportDiscoveryPlan:
    """Discover one report-only job PER extraction, even without depot JSON.

    Uses the existing a20.5 bounded work-tree scanner, then inspects each
    extraction independently. Distinct source folders always remain distinct;
    JOB-nnn in old data is NEVER treated as globally unique.
    """
    root = Path(directory).expanduser()
    if not root.is_dir():
        raise RecoveryError(f'Mappen finnes ikke eller er frakoblet: {root}')
    initial_device = root.stat().st_dev
    _check_cancel(cancelled)
    roots, extractions, joblists, zipfiles = _candidate_dwm_roots(
        root, cancelled=cancelled, on_progress=on_progress)
    _check_cancel(cancelled)
    shared_zips = _shared_zip_inventory(root, extractions) if extractions else ()
    zipfiles = tuple(sorted(set(zipfiles) | set(shared_zips), key=str))
    warnings = []
    old_ids = _legacy_jobs(joblists, extractions, warnings)
    rows = []
    if not extractions:
        # A dwm/b03 directory selected directly still needs to work.
        strict = discover_report_jobs(root, cancelled=cancelled)
        for found in strict.jobs:
            rows.append(dict(extraction=_extraction_ancestor(found.work_operations),
                name=found.name, report=found, work=found.work_operations,
                dwm=_work_evidence(found.work_operations), evidence=('DWM depotrapport',),
                zips=(), legacy=None, archive_report=None))
    else:
        for index, extraction in enumerate(extractions, 1):
            _check_cancel(cancelled)
            strict_job = None
            try:
                strict_plan = discover_report_jobs(extraction, cancelled=cancelled)
                if len(strict_plan.jobs) == 1:
                    strict_job = strict_plan.jobs[0]
                elif strict_plan.jobs:
                    warnings.append(f'Flere forskjellige historiske jobber i {extraction}; '
                                    'velg denne mappen separat for gjennomgang.')
            except RecoveryCancelled:
                raise
            except RecoveryError as exc:
                # No DWM report is normal here; a real filesystem exception
                # from work enumeration is NOT silently downgraded.
                if 'Ingen lagrede depotrapporter' not in str(exc) and 'Ingen lesbare' not in str(exc):
                    warnings.append(str(exc))
            work, dwm = _choose_work_root(extraction, strict_job)
            sources = []
            if strict_job is not None:
                sources.append('DWM depotrapport')
            elif dwm:
                sources.append('DWM-arbeidsresultater (uten depotrapport)')
            sources.extend(_legacy_evidence(extraction))
            archives = _zip_hints(extraction, zipfiles)
            archive_report = None
            if archives:
                # Reading ZIP metadata is bounded and never extracts source payloads.
                if strict_job is None:
                    archive_report = _zip_report_hint(archives, warnings, extraction=extraction)
                if archive_report:
                    sources.append('Depotrapport i eldre DWM-ZIP (lokal kopi ved lagring)')
                else:
                    sources.append(f'{len(archives)} DWM-ZIP (uten bekreftet depotrapport)')
            legacy_matches = old_ids.get(extraction, [])
            if legacy_matches:
                sources.append('Tidligere .n5jobs (identitetshjelp)')
            if not sources:
                sources.append('Kun uttrekksmappe (ingen normal DWM-rapport)')
            rows.append(dict(extraction=extraction, name=extraction.name, report=strict_job,
                            work=work, dwm=dwm, evidence=tuple(sources), zips=archives,
                            legacy=legacy_matches[0] if len(set(legacy_matches)) == 1 else None,
                            archive_report=archive_report))
            if on_progress and (index % 3 == 0 or index == len(extractions)):
                on_progress(f'Kontrollerer uttrekk {index}/{len(extractions)}; '
                            f'{sum(bool(x["report"]) for x in rows)} med depotrapport ...')

    # Preserve original JOB-nnn for each original report where possible. This
    # is needed because a19's report reader addresses original JOB-nnn__RUN.
    reserved = set()
    # A live DWM report wins its original JOB-nnn over an older ZIP copy.
    # This keeps native evidence/assessment links intact whenever possible.
    for source_kind in ('report', 'archive_report'):
        for row in rows:
            if 'assigned_id' in row:
                continue
            source = row[source_kind]
            native = (source.job_id if source_kind == 'report' and source else
                      source[2] if source_kind == 'archive_report' and source else None)
            if not native:
                continue
            if native not in reserved:
                row['assigned_id'] = native
                reserved.add(native)
            else:
                # Reused JOB-001 is correctly re-numbered and its original
                # JSON is copied to a provenance-labelled local cache on save.
                row['needs_cache'] = True
    next_number = 1
    for row in rows:
        if 'assigned_id' in row:
            continue
        while f'JOB-{next_number:03d}' in reserved:
            next_number += 1
        row['assigned_id'] = f'JOB-{next_number:03d}'
        reserved.add(row['assigned_id'])
        next_number += 1

    results = []
    for row in rows:
        report = row['report']
        legacy = row['legacy']
        archive = row['archive_report']
        native = (report.job_id if report is not None else archive[2] if archive
                  else legacy[1] if legacy else None)
        results.append(ReportCandidate(
            job_id=row['assigned_id'], name=row['name'], work_operations=row['work'],
            extraction_folder=row['extraction'], evidence=tuple(row['evidence']),
            report_file=report.report_file if report is not None else None,
            source_job_id=native, manifest_verified=bool(report and report.manifest_verified),
            original_runs=report.original_runs if report is not None else 0,
            legacy_job_list=legacy[0] if legacy else None,
            archived_zips=tuple(row['zips']),
            archive_report_zip=archive[0] if archive else None,
            archive_report_member=archive[1] if archive else '',
            archive_report_crc=archive[3] if archive else None,
            archive_report_length=archive[4] if archive else None,
            report_needs_cache=bool(row.get('needs_cache')) or bool(archive),
        ))
    try:
        if root.stat().st_dev != initial_device:
            raise RecoveryError('Lagringsmediet ble byttet under søket.')
    except OSError as exc:
        raise RecoveryError(f'Disken ble utilgjengelig under gjenfinning: {exc}') from exc
    missing = tuple(ex for ex in extractions
                    if not any(j.extraction_folder == ex and j.has_report for j in results))
    if on_progress:
        on_progress(f'Ferdig: {len(results)} rapportjobber fra {len(extractions)} uttrekksmapper; '
                    f'{sum(j.has_report for j in results)} med full DWM-depotrapport.')
    return ReportDiscoveryPlan(root, tuple(results), tuple(warnings), roots,
        extractions, joblists, zipfiles, missing)


def save_available_report_jobs(plan: ReportDiscoveryPlan, filename: str | Path) -> Path:
    """Write a new native .n5jobs and optional local copies of saved report JSON.

    Neither report source nor historical joblist is overwritten. On failure a
    partial .n5jobs is not published as success; the temporary cache is removed.
    """
    if not plan.jobs:
        raise RecoveryError('Ingen uttrekk eller rapportjobber ble funnet.')
    dest = Path(filename).expanduser()
    if dest.suffix.lower() != '.n5jobs':
        dest = dest.with_suffix('.n5jobs')
    if dest.exists():
        raise FileExistsError(f'Filen finnes allerede: {dest}')
    try:
        dest.resolve().relative_to(plan.scanned_root.resolve())
    except ValueError:
        pass
    else:
        raise RecoveryError('Lagre .n5jobs utenfor skannet arkivområde, helst på C:.')
    from noark5_workflow.core.job import Job, JobBatch, JobStatus
    from noark5_workflow.core.job_store import save_job_list
    from version import VERSION
    cache_dest=dest.with_suffix('.recovered-dwm')
    if cache_dest.exists():
        raise FileExistsError(f'Lokal rapportcache finnes allerede: {cache_dest}')
    dest.parent.mkdir(parents=True, exist_ok=True)
    cache_jobs=[job for job in plan.jobs if job.report_needs_cache]
    staging=None
    published_cache=False
    try:
        if cache_jobs:
            staging=Path(tempfile.mkdtemp(prefix='.dwm-recovery-',dir=dest.parent))
            for job in cache_jobs:
                _materialize_report(job, staging/job.job_id)
            staging.replace(cache_dest)
            published_cache=True
            staging=None
        batch = JobBatch()
        for item in plan.jobs:
            # An extraction with no original DWM work root still needs a
            # writable LOCAL place for a later manual period assessment. Do
            # not create a work folder on the archive/source disk or claim
            # that the local folder contains a completed depot report.
            work=(cache_dest/item.job_id
                  if item.report_needs_cache or item.work_operations is None
                  else item.work_operations)
            detail=('Depotrapport funnet' if item.has_report else
                    'Ingen lagret normal DWM-depotrapport; ukjente rapporttall')
            batch.add(Job(job_id=item.job_id, name=item.name,
                source_root=None, source_extraction=None,
                work_operations=work,
                profile_id='noark5', status=JobStatus.READY,
                progress=0.0, workflow_ids=[], checkpoint_after=[],
                message='Rapportjobb (gjenfunnet, ikke kjørbar): ' + detail,
                operation_params={'__dwm_report_recovery__': {
                    'schema': 'ikamr.dwm.report_recovery.a20.7',
                    'report_only': True,
                    'extraction_path': str(item.extraction_folder) if item.extraction_folder else '',
                    'report_file': str(item.report_file) if item.report_file else '',
                    'source_job_id': item.source_job_id or '',
                    'evidence': list(item.evidence),
                    'original_runs': item.original_runs,
                    'legacy_job_list': str(item.legacy_job_list) if item.legacy_job_list else '',
                    'archived_dwm_zips': list(map(str,item.archived_zips)),
                    'report_cache': str(work) if item.report_needs_cache else '',
                }},
            ))
        saved=save_job_list(dest, batch, active_job_id=batch.jobs()[0].job_id,
                            app_version=VERSION)
        return saved
    except Exception:
        if staging and staging.is_dir():
            shutil.rmtree(staging, ignore_errors=True)
        if published_cache:
            shutil.rmtree(cache_dest, ignore_errors=True)
        # save_job_list uses atomic write, but clean up if an unexpected writer
        # already published a partial list before failing.
        raise


def main(argv=None):
    import argparse
    parser=argparse.ArgumentParser(description='Gjenfinn ALLE rapportjobber fra arkiv-noark5 uten ny analyse')
    parser.add_argument('directory')
    parser.add_argument('output', nargs='?')
    parser.add_argument('--inspect', action='store_true')
    args=parser.parse_args(argv)
    if not args.output and not args.inspect:
        parser.error('Angi utfil eller --inspect')
    try:
        plan=discover_available_report_jobs(args.directory, on_progress=print)
        for job in plan.jobs:
            print(job.job_id, job.name, '|', 'DEPOTRAPPORT' if job.has_report else 'DELVIS',
                  '|', '; '.join(job.evidence))
        for warning in plan.warnings:
            print('MERKNAD:',warning)
        if args.inspect:
            return 0
        print('Lagret:',save_available_report_jobs(plan,args.output))
        return 0
    except (RecoveryError,OSError) as exc:
        print('FEIL:',exc)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
