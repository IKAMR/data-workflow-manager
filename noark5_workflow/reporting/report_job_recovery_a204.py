"""Discover report-only jobs from existing DWM work artifacts.

Recovery is read-only until the operator explicitly saves a NEW .n5jobs file.
Never traverse DOKUMENT/source payloads, change a source path, invent missing
workflow history, or map the same JOB-nnn to different archive extractions.
"""
from __future__ import annotations

import json
import re
from collections import deque
from dataclasses import dataclass
from pathlib import Path, PureWindowsPath
from threading import Event

_JOB_RUN = re.compile(r"^(JOB-[0-9]{3,})__", flags=re.IGNORECASE)
_REPORT_DIR = Path('noark5_reports') / 'depot_validation'
# Only archive, administrative and DWM work directories are traversed.
# Source XML/document payloads, archived ZIP files and analysis evidence trees
# must NEVER be walked while recovering a report-only job list.
_SKIP_DIRS = {
    'DOKUMENT', 'DOKUMENTER', 'CONTENT', 'AIP', 'SIP', '.GIT', 'TEMP',
    '_TEMP', 'NODE_MODULES', '_WORK', '_NOARK5', '_DEBUG',
    'DESCRIPTIVE_METADATA', 'GODKJENNING', 'ABSTRACT', 'ANALYSE',
    'ARKADE5', 'DROID', 'QUARANTINE', 'QUERIES', 'TEMPLATES', 'UTILITIES',
    'VERAPDF', 'METADATA', 'NOARK5_TESTS', 'NOARK5_VIEWS',
    'EXTERNAL_EVIDENCE', 'WF', 'RESULTS', 'LOGS', 'JOBS',
    'NOARK5_REPORTS', 'DEPOT_VALIDATION',
}
_EXTRACT_NAME = re.compile(r'^\d{4}_\d{3}(?!\d)', re.IGNORECASE)
_WORK_ROOT_NAMES = {'REPOSITORY_OPERATIONS', 'WORK_OPERATIONS'}
_MAX_ROOT_CHILDREN = 1000
_MAX_SCAN_DIRS = 20000
_MAX_SCAN_DEPTH = 8
_MAX_REPORT_RUNS = 2000


class RecoveryError(ValueError):
    """No safe, unambiguous report-only job list can be reconstructed."""


class RecoveryCancelled(RecoveryError):
    """The operator cancelled a bounded read-only scan."""


@dataclass(frozen=True)
class RecoveredReportJob:
    job_id: str
    work_operations: Path
    report_file: Path
    name: str
    source_extraction_note: str
    original_runs: int
    manifest_verified: bool


@dataclass(frozen=True)
class RecoveryPlan:
    scanned_root: Path
    jobs: tuple[RecoveredReportJob, ...]
    warnings: tuple[str, ...]
    report_roots: tuple[Path, ...]
    extraction_folders: tuple[Path, ...] = ()
    existing_job_lists: tuple[Path, ...] = ()
    archived_dwm_zips: tuple[Path, ...] = ()
    missing_report_extractions: tuple[Path, ...] = ()


def _check_cancel(cancelled: Event | None):
    if cancelled is not None and cancelled.is_set():
        raise RecoveryCancelled('Gjenfinning avbrutt; ingen filer er skrevet.')


def _read_json(path: Path):
    try:
        result = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, ValueError) as exc:
        raise RecoveryError(f'Kan ikke lese {path}: {exc}') from exc
    if not isinstance(result, dict):
        raise RecoveryError(f'Ikke et JSON-objekt: {path}')
    return result


def _children(path: Path, *, max_items: int):
    """Read one directory level, avoiding symlinks and Windows junctions."""
    children = []
    try:
        for child in path.iterdir():
            if child.name.upper() in _SKIP_DIRS:
                continue
            # No traversal through symlinks, Windows junctions or other reparse
            # locations which could leave the selected storage area.
            if child.is_symlink() or getattr(child, 'is_junction', lambda: False)():
                continue
            if child.is_dir():
                children.append(child)
                if len(children) > max_items:
                    raise RecoveryError(
                        f'For mange undermapper i {path}; velg en mer spesifikk mappe.')
        return tuple(children)
    except OSError as exc:
        raise RecoveryError(f'Kunne ikke skanne {path}: {exc}') from exc


def _extraction_ancestor(path: Path) -> Path | None:
    """Find the extraction enclosing repository_operations, never from a guess."""
    for current in (path, *path.parents):
        if current.name.upper() in _WORK_ROOT_NAMES:
            parent = current.parent
            if _EXTRACT_NAME.match(parent.name):
                return parent
            break
    return None


def _candidate_dwm_roots(selected: Path, *, cancelled: Event | None,
                         on_progress=None):
    """Bounded, structure-aware search beneath a chosen collection root.

    Covers: collection/municipality/extraction/repository_operations/dwm/b03,
    plus direct selections of any level, without scanning content/DOKUMENT.
    """
    roots = []
    seen_roots = set()
    seen_dirs = set()
    extraction_folders = set()
    existing_job_lists = set()
    archived_dwm_zips = set()
    queue = deque([(selected, 0)])
    completed = 0

    def add(path):
        key = str(path).casefold()
        if key in seen_roots:
            return
        seen_roots.add(key)
        try:
            if (path / _REPORT_DIR).is_dir():
                roots.append(path)
        except OSError as exc:
            raise RecoveryError(f'Kunne ikke lese rapportområde {path}: {exc}') from exc

    # Direct selection of the last two directory levels is also supported.
    if selected.name.casefold() == 'noark5_reports':
        add(selected.parent)
    if (selected.name.casefold() == 'depot_validation'
            and selected.parent.name.casefold() == 'noark5_reports'):
        add(selected.parent.parent)

    def may_descend(parent: Path, child: Path, depth: int) -> bool:
        # At the extraction level, only read the work tree (not SIP/AIP or
        # independently generated Arkade 5/KDRS input).
        if _EXTRACT_NAME.match(parent.name):
            return child.name.upper() in _WORK_ROOT_NAMES or child.name.casefold() == 'dwm'
        # Work root has hundreds of unrelated folders in older depots.
        if parent.name.upper() in _WORK_ROOT_NAMES:
            return child.name.upper() not in _SKIP_DIRS
        # A DWM area can be either the report root or contain b01/b02/b03.
        # All DWM evidence subtrees are in the skip set.
        if parent.name.casefold() in {'dwm'}:
            return True
        if parent.parent.name.casefold() == 'dwm':
            return True
        # For top-level collection roots, traverse municipalities, extraction
        # directories and a small number of customary work structures only.
        if child.name.isdigit() and len(child.name) == 4:
            return True
        if _EXTRACT_NAME.match(child.name):
            return True
        if child.name.upper() in _WORK_ROOT_NAMES or child.name.casefold() == 'dwm':
            return True
        # Allow grouping folders (including a generic caller-supplied folder)
        # only in the first levels. Never recurse freely through source trees.
        return depth < 2 and not parent.name.isdigit()

    while queue:
        _check_cancel(cancelled)
        path, depth = queue.popleft()
        key = str(path).casefold()
        if key in seen_dirs:
            continue
        seen_dirs.add(key)
        completed += 1
        if completed > _MAX_SCAN_DIRS:
            raise RecoveryError('For mange arbeidsmapper under valgt rot. Velg en kommune eller et uttrekk.')
        if _EXTRACT_NAME.match(path.name):
            extraction_folders.add(path)
        add(path)
        if on_progress is not None and (completed == 1 or completed % 25 == 0):
            on_progress(f'Skanner {completed} arbeidsmapper; '
                        f'{len(extraction_folders)} uttrekk, {len(roots)} DWM-rapportområder funnet ...')
        if depth <= 1 or path.name.upper() in _WORK_ROOT_NAMES:
            try:
                if depth <= 1:
                    for item in path.glob('*.n5jobs'):
                        if item.is_file():
                            existing_job_lists.add(item)
                if path.name.upper() in _WORK_ROOT_NAMES:
                    # ZIP manifests are inventory hints only. Archived DWM
                    # results are NOT treated as directly readable reports.
                    for item in path.glob('*.zip'):
                        if item.is_file() and 'dwm' in item.name.casefold():
                            archived_dwm_zips.add(item)
            except OSError as exc:
                raise RecoveryError(f'Kunne ikke lese indeksfiler i {path}: {exc}') from exc
        if depth >= _MAX_SCAN_DEPTH:
            continue
        for child in _children(path, max_items=_MAX_ROOT_CHILDREN):
            if may_descend(path, child, depth):
                queue.append((child, depth + 1))
    if on_progress is not None:
        on_progress(f'Ferdig: {len(extraction_folders)} uttrekksmapper og '
                    f'{len(roots)} arbeidsområder med depotrapporter.')
    return (tuple(roots), tuple(sorted(extraction_folders, key=str)),
            tuple(sorted(existing_job_lists, key=str)),
            tuple(sorted(archived_dwm_zips, key=str)))


def _display_name(source_extraction: str, fallback: str) -> str:
    # Do not assume the current client can access the original source disk.
    if not source_extraction:
        return fallback + ' – gjenfunnet depotrapport'
    name = PureWindowsPath(source_extraction).name or Path(source_extraction).name
    # Avoid displaying a full potentially sensitive historical file path.
    return name if name else fallback + ' – gjenfunnet depotrapport'


def discover_report_jobs(directory: str | Path, *, cancelled: Event | None = None, on_progress=None) -> RecoveryPlan:
    """Find readable depot reports and their original list-local JOB identities.

    Multiple DWM roots with DISTINCT job IDs can be combined. Duplicate IDs
    across roots (or multiple sources inside one root) require separate lists,
    not renumbering: renumbering breaks report and assessment provenance.
    """
    selected = Path(directory).expanduser()
    if not selected.is_dir():
        raise RecoveryError(f'Mappen finnes ikke eller er frakoblet: {selected}')
    start_device = selected.stat().st_dev
    roots, extraction_folders, job_lists, archived_zips = _candidate_dwm_roots(
        selected, cancelled=cancelled, on_progress=on_progress)
    if not roots:
        hint = (' Eksisterende .n5jobs: ' + '; '.join(map(str, job_lists))
                if job_lists else '')
        raise RecoveryError('Ingen lagrede depotrapporter fra DWM funnet i søkeområdet. '
                            'Fant ' + str(len(extraction_folders)) + ' uttrekksmapper, '
                            + str(len(archived_zips)) + ' arkiverte DWM ZIP-filer. '
                            'Eldre Arkade 5/KDRS-filer og ZIP-filer er ikke '
                            'depot_validation_report.json.' + hint)

    found: dict[str, list[tuple[Path, Path, str, bool]]] = {}
    warnings = []
    for root in roots:
        _check_cancel(cancelled)
        report_base = root / _REPORT_DIR
        try:
            before = report_base.stat()
            runs = tuple(report_base.iterdir())
        except OSError as exc:
            raise RecoveryError(f'Disk eller rapportmappe utilgjengelig: {report_base}: {exc}') from exc
        if len(runs) > _MAX_REPORT_RUNS:
            raise RecoveryError(f'For mange rapportkjøringer under {report_base}; velg én dwm-mappe.')
        for run in runs:
            _check_cancel(cancelled)
            match = _JOB_RUN.match(run.name)
            if not match or not run.is_dir():
                continue
            job_id = match.group(1).upper()
            report_file = run / 'depot_validation_report.json'
            if not report_file.is_file():
                continue
            try:
                report = _read_json(report_file)
            except RecoveryError as exc:
                warnings.append(str(exc))
                continue
            if not isinstance(report.get('summary'), dict) and not isinstance(report.get('archive_parts'), list):
                warnings.append(f'Ikke en gjenkjennelig depotrapport: {report_file}')
                continue
            source = ''
            verified = False
            manifest_file = run / 'artifact_manifest.json'
            if manifest_file.is_file():
                try:
                    manifest = _read_json(manifest_file)
                    actual_id = str(manifest.get('job_id') or '').upper()
                    if actual_id and actual_id != job_id:
                        warnings.append(f'Avvist: jobb-ID stemmer ikke mellom mappe og manifest: {run}')
                        continue
                    actual_root = str(manifest.get('source_extraction') or '').strip()
                    if actual_root:
                        source = actual_root
                        verified = True
                    else:
                        warnings.append(f'Manifest mangler uttrekksidentitet: {run}')
                except RecoveryError as exc:
                    warnings.append(str(exc))
                    continue
            else:
                warnings.append(f'Eldre kjøring uten manifest: {run}; uttrekksidentitet er ikke verifisert')
            found.setdefault(job_id, []).append((root, report_file, source, verified))
        # A USB disconnect during discovery must never produce a plausible
        # but incomplete job list. Check the scan root again before offering save.
        try:
            after = report_base.stat()
            if before.st_dev != after.st_dev:
                raise RecoveryError(f'Lagringsmediet ble byttet under søk: {report_base}')
        except OSError as exc:
            raise RecoveryError(f'Lagringsmediet ble utilgjengelig under søk: {report_base}: {exc}') from exc

    if not found:
        raise RecoveryError('Ingen lesbare depot_validation_report.json ble funnet. '
                            'Kopier loggen eller kontroller om rapportoperasjonen er kjørt.')
    jobs = []
    for job_id, items in sorted(found.items()):
        work_roots = {str(root).casefold() for root, _p, _s, _v in items}
        source_roots = {s.casefold().replace('\\', '/') for _r, _p, s, _v in items if s}
        if len(work_roots) > 1:
            locations = '\n'.join('  ' + str(r) for r in sorted({r for r, *_ in items}, key=str))
            raise RecoveryError(f'{job_id} finnes i flere arbeidsområder. '
                                'Jobb-ID-er er lokale for en jobbliste og kan ikke kombineres trygt:\n'
                                + locations + '\nVelg én konkret dwm-mappe og lag separate jobblister.')
        if len(source_roots) > 1:
            raise RecoveryError(f'{job_id} peker til flere ulike uttrekk i samme dwm-område. '
                                'Kan ikke velge automatisk. Velg en smalere arbeidsmappe.')
        # Without source manifests multiple runs cannot safely be attributed.
        if len(items) > 1 and any(not valid for _r, _p, _s, valid in items):
            raise RecoveryError(f'{job_id} har flere kjøringer der minst én mangler verifisert '
                                'uttrekksidentitet. Kan ikke slå dem sammen sikkert.')
        def modified(item):
            try:
                return item[1].stat().st_mtime_ns
            except OSError:
                return -1
        newest = max(items, key=modified)
        source = newest[2]
        work, report_file = newest[0], newest[1]
        archive_path = _extraction_ancestor(work)
        fallback_name = archive_path.name if archive_path is not None else job_id
        jobs.append(RecoveredReportJob(job_id=job_id, work_operations=work,
                                      report_file=report_file,
                                      name=_display_name(source, fallback_name),
                                      source_extraction_note=source,
                                      original_runs=len(items), manifest_verified=bool(newest[3])))
    try:
        if selected.stat().st_dev != start_device:
            raise RecoveryError('Lagringsmediet ble byttet under gjenfinning. Prøv igjen.')
    except OSError as exc:
        raise RecoveryError(f'Lagringsmediet ble utilgjengelig under gjenfinning: {exc}') from exc
    recovered_extractions = {v for v in (_extraction_ancestor(j.work_operations)
                                         for j in jobs) if v is not None}
    missing = tuple(sorted(set(extraction_folders) - recovered_extractions, key=str))
    return RecoveryPlan(selected, tuple(jobs), tuple(warnings), roots,
                        extraction_folders, job_lists, archived_zips, missing)


def save_recovered_report_jobs(plan: RecoveryPlan, filename: str | Path) -> Path:
    """Write a separate .n5jobs using the supported native store, never overwrite."""
    if not plan.jobs:
        raise RecoveryError('Ingen jobber å gjenfinne.')
    dest = Path(filename).expanduser()
    if dest.suffix.lower() != '.n5jobs':
        dest = dest.with_suffix('.n5jobs')
    for root in plan.report_roots:
        try:
            dest.resolve().relative_to(root.resolve())
        except ValueError:
            pass
        else:
            raise RecoveryError('Lagre den nye jobblisten utenfor DWM-resultatmappene.')
    if dest.exists():
        raise FileExistsError(f'Filen finnes allerede. Velg et nytt filnavn: {dest}')
    from noark5_workflow.core.job import Job, JobBatch, JobStatus
    from noark5_workflow.core.job_store import save_job_list
    from version import VERSION
    batch = JobBatch()
    for item in plan.jobs:
        # Keep the source fields unset: the historic source may be offline,
        # copied or under a different drive letter. We only need Work/operations
        # and original JOB-nnn for honest report generation.
        batch.add(Job(
            job_id=item.job_id, name=item.name, work_operations=item.work_operations,
            source_root=None, source_extraction=None, profile_id='noark5',
            status=JobStatus.READY, workflow_ids=[], progress=0.0,
            message=('Gjenfunnet for rapport fra lagret depotrapport. Ikke klar for kjøring. '
                     + ('Uttrekk oppgitt i manifest: ' + item.source_extraction_note
                        if item.source_extraction_note else 'Uttrekkskilde kunne ikke verifiseres.')),
        ))
    return save_job_list(dest, batch, active_job_id=batch.jobs()[0].job_id,
                         app_version=VERSION)


def main(argv: list[str] | None = None) -> int:
    """Optional console fallback when Tk cannot be used on an unstable disk."""
    import argparse
    parser = argparse.ArgumentParser(description='Gjenfinn rapportjobber fra eksisterende dwm-data')
    parser.add_argument('dwm_folder', help='dwm, repository_operations eller en overordnet arbeidsmappe')
    parser.add_argument('output', nargs='?', help='Ny .n5jobs på en stabil disk')
    parser.add_argument('--inspect', action='store_true', help='Vis funn uten å skrive ny jobbliste')
    args = parser.parse_args(argv)
    if not args.inspect and not args.output:
        parser.error('Angi en ny .n5jobs-fil, eller bruk --inspect.')
    try:
        plan = discover_report_jobs(args.dwm_folder)
        for job in plan.jobs:
            print(job.job_id, '|', job.name, '|', job.work_operations,
                  '| manifest' if job.manifest_verified else '| uverifisert', sep=' ')
        print('Uttrekksmapper:', len(plan.extraction_folders),
              '| uten DWM-depotrapport:', len(plan.missing_report_extractions))
        for folder in plan.missing_report_extractions:
            print('MANGLER DWM-DEPOTRAPPORT:', folder)
        for jobfile in plan.existing_job_lists:
            print('EKSISTERENDE JOBBLISTE:', jobfile)
        for archive in plan.archived_dwm_zips:
            print('ARKIVERT DWM (ikke analysert):', archive)
        for note in plan.warnings:
            print('MERKNAD:', note)
        if args.inspect:
            print('KUN INSPEKSJON. Ingen filer er skrevet.')
            return 0
        output = save_recovered_report_jobs(plan, args.output)
        print('Lagret gjenfunnet jobbliste:', output)
        return 0
    except (RecoveryError, OSError) as exc:
        print('FEIL:', exc)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
