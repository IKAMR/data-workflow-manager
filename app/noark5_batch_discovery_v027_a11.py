"""Safe read-only Noark 5 package discovery and explicit Work planning.

Discover only extraction content with arkivstruktur.xml and a document folder.
Never traverse document payload, old Work or repository_operations. Work paths
are plans, never auto-created by discovery.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Mapping
import os
import re

SKIP = frozenset({
    'dokument', 'dokumenter', 'repository_operations', 'external_evidence',
    '.git', 'wf', 'diagnostics', 'node_modules', '_work', 'work',
})
_BAD = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
_EXTRACT_ID = re.compile(r'^(\d{4}_\d{3})(?:_|$)', re.IGNORECASE)


@dataclass(frozen=True)
class Candidate:
    source: Path
    package_root: Path
    info_xml: Path | None = None


def component(value: str) -> str:
    value = str(value or '').strip()
    if not value or value in ('.', '..') or _BAD.search(value) or value.endswith(('.', ' ')):
        raise ValueError('Bruk ett gyldig mappenavn, f.eks. a01 (uten skr\u00e5strek).')
    return value


def extraction_id(candidate: Candidate) -> str:
    match = _EXTRACT_ID.match(candidate.package_root.name)
    return match.group(1) if match else candidate.package_root.name


def package_root_for(source: Path, search_root: Path) -> Path:
    """Find the SIP package root without accidentally using an old Work tree."""
    parts = source.parts
    lowered = [part.casefold() for part in parts]
    for i in range(len(parts) - 2):
        if lowered[i:i + 3] == ['content', 'sip', 'content']:
            return Path(*parts[:i])
    relative = source.relative_to(search_root)
    if len(relative.parts) >= 2:
        return search_root / relative.parts[0]
    return source.parent


def _normal_directory(path: Path) -> bool:
    return (path.is_dir() and not path.is_symlink()
            and not getattr(path, 'is_junction', lambda: False)())


def _is_source(here: Path, dirs: list[str], names: list[str]) -> bool:
    xml = next((here / name for name in names if name.casefold() == 'arkivstruktur.xml'), None)
    if xml is None or not xml.is_file() or xml.is_symlink():
        return False
    return any(_normal_directory(here / name) for name in dirs
               if name.casefold() in {'dokument', 'dokumenter'})


def discover(root: str | Path, *, max_directories: int = 100000,
             cancelled=None) -> tuple[Candidate, ...]:
    root = Path(root).resolve(strict=True)
    if not _normal_directory(root):
        raise ValueError('Hovedmappen m\u00e5 v\u00e6re en eksisterende vanlig mappe.')
    found: list[Candidate] = []
    visited = 0
    for folder, dirs, names in os.walk(root, topdown=True, followlinks=False):
        if cancelled and cancelled():
            raise InterruptedError('S\u00f8ket er avbrutt.')
        visited += 1
        if visited > max_directories:
            raise ValueError('S\u00f8ket oversteg kataloggrensen. Velg en mer avgrenset hovedmappe.')
        here = Path(folder)
        if _is_source(here, dirs, names):
            found.append(Candidate(here, package_root_for(here, root)))
        # A SIP source is never inferred from old Work; document files are not scanned.
        dirs[:] = sorted((name for name in dirs if name.casefold() not in SKIP
                          and _normal_directory(here / name)), key=str.casefold)
    return tuple(sorted(found, key=lambda candidate: str(candidate.source).casefold()))


def rejected_sip_packages(root: str | Path, found: tuple[Candidate, ...]) -> tuple[tuple[str, str], ...]:
    """Explain missing SIP sources among direct child packages, without payload scan."""
    root = Path(root)
    accepted = {candidate.package_root.resolve(strict=False) for candidate in found}
    result: list[tuple[str, str]] = []
    if not _normal_directory(root):
        return ()
    for package in sorted(root.iterdir(), key=lambda p: p.name.casefold()):
        if not _normal_directory(package) or package.resolve(strict=False) in accepted:
            continue
        sip = package / 'content' / 'sip' / 'content'
        if not _normal_directory(sip):
            continue
        names = {p.name.casefold(): p for p in sip.iterdir()}
        xml = names.get('arkivstruktur.xml')
        xml_ok = bool(xml and xml.is_file() and not xml.is_symlink())
        docs_ok = any(_normal_directory(names[key]) for key in ('dokument', 'dokumenter') if key in names)
        missing = []
        if not xml_ok:
            missing.append('arkivstruktur.xml')
        if not docs_ok:
            missing.append('DOKUMENT/dokumenter')
        if missing:
            result.append((package.name, 'Mangler ' + ' og '.join(missing) + ' i content/sip/content'))
    return tuple(result)


def _info_name_for_package(filename: str, package_name: str) -> bool:
    """Recognize 1525_004_<uuid>_info.xml without matching another package."""
    name = filename.casefold()
    if not name.endswith('_info.xml'):
        return False
    prefix = _EXTRACT_ID.match(package_name)
    if prefix:
        return name.startswith(prefix.group(1).casefold() + '_')
    return name.startswith(package_name.casefold() + '_')


def info_xml_candidates(candidate: Candidate, info_root: str | Path | None = None) -> tuple[Path, ...]:
    """Direct package-local or explicitly selected matching XML, no fuzzy guessing."""
    places: list[tuple[Path, bool]] = [
        (candidate.source, True),
        (candidate.source.parent, True),
        (candidate.package_root, True),
        (candidate.package_root / 'metadata', True),
    ]
    if info_root:
        base = Path(info_root).resolve(strict=True)
        if not _normal_directory(base):
            raise ValueError('Valgt info.xml-katalog finnes ikke.')
        places.extend([
            (base / candidate.package_root.name, True),
            (base / candidate.source.name, True),
            # If several extractions share this directory, a prefixed file
            # must match the candidate ID; an unqualified info.xml is unsafe.
            (base, base.resolve(strict=False) == candidate.package_root.resolve(strict=False)),
        ])
    matches: set[Path] = set()
    for place, allow_generic in places:
        if not _normal_directory(place):
            continue
        for file in place.iterdir():
            name = file.name.casefold()
            if not ((allow_generic and name == 'info.xml')
                    or _info_name_for_package(file.name, candidate.package_root.name)):
                continue
            try:
                if file.is_file() and not file.is_symlink() and file.stat().st_size <= 8_000_000:
                    matches.add(file.resolve(strict=True))
            except OSError:
                pass
    return tuple(sorted(matches, key=lambda p: str(p).casefold()))


def resolve_info_xml(candidate: Candidate, info_root: str | Path | None = None) -> Path | None:
    matches = info_xml_candidates(candidate, info_root)
    return matches[0] if len(matches) == 1 else None


def work_folder_alternatives(package_root: str | Path, configured: str = 'dwm') -> tuple[str, ...]:
    """Find likely existing DWM folders; do not suggest unrelated operations."""
    ops = Path(package_root) / 'repository_operations'
    if not _normal_directory(ops):
        return ()
    configured = str(configured or '')
    names: list[str] = []
    for child in ops.iterdir():
        if not _normal_directory(child) or child.name.casefold() == configured.casefold():
            continue
        name = child.name.casefold()
        likely_name = (name.startswith('dwm')
                       or (configured and name.startswith(configured.casefold())))
        has_dwm_results = False
        if not likely_name:
            # A user may have configured an entirely different folder name.
            for run in child.iterdir():
                if _normal_directory(run) and (
                        (run / 'job.json').is_file() or (run / 'wf' / 'results').is_dir()):
                    has_dwm_results = True
                    break
        if likely_name or has_dwm_results:
            names.append(child.name)
    return tuple(sorted(names, key=str.casefold))


def plan_work(candidate: Candidate, *, dwm_folder: str = 'dwm',
              run_folder: str = 'a01') -> Path:
    base = candidate.package_root / 'repository_operations'
    if dwm_folder:
        base /= component(dwm_folder)
    return base / component(run_folder)


def assign_work(candidates: tuple[Candidate, ...], *, dwm_folder: str = 'dwm',
                run_folder: str = 'a01',
                folder_overrides: Mapping[Path, str] | None = None) -> dict[Path, Path]:
    """One Work per Source, while allowing explicit folder choices per package."""
    plans: dict[Path, Path] = {}
    used: set[str] = set()
    for candidate in candidates:
        chosen = dwm_folder if folder_overrides is None else folder_overrides.get(candidate.source, dwm_folder)
        target = plan_work(candidate, dwm_folder=chosen, run_folder=run_folder)
        key = str(target).casefold()
        if key in used:
            safe = re.sub(r'[^\w.-]', '_', candidate.source.name).strip('._') or 'uttrekk'
            target = target / safe
            key = str(target).casefold()
        if key in used:
            raise ValueError('Uttrekkene gir samme Work-mappe: ' + str(target))
        used.add(key)
        plans[candidate.source] = target
    return plans


def work_target_state(target: str | Path) -> str:
    target = Path(target)
    # A parent redirected through a junction/symlink is not a safe Work base.
    for part in (target, target.parent, target.parent.parent):
        if part.is_symlink() or getattr(part, 'is_junction', lambda: False)():
            return 'blocked'
    if target.exists():
        if not target.is_dir():
            return 'blocked'
        return 'occupied' if any(target.iterdir()) else 'empty'
    return 'new'


def create_direct_work_job(api, candidate: Candidate, target: Path, *,
                           on_created=None, workflow_ids=None) -> str:
    """Register one approved batch job using precisely the selected Work path.

    The GUI calls this only after explicit operator confirmation. Existing Work
    data are never modified. On failure the new job is removed and any newly
    created EMPTY directories are removed; prior folders are left untouched.
    """
    target = Path(target)
    operations = candidate.package_root / 'repository_operations'
    if not target.is_absolute() or operations not in target.parents:
        raise ValueError('Work må ligge under uttrekkets repository_operations.')
    state = work_target_state(target)
    if state not in ('new', 'empty'):
        raise ValueError('Work er blokkert eller inneholder allerede data: ' + str(target))

    missing: list[Path] = []
    folder = target
    while not folder.exists():
        missing.append(folder)
        folder = folder.parent
    view = None
    try:
        if state == 'new':
            target.mkdir(parents=True, exist_ok=False)
        if work_target_state(target) != 'empty':
            raise ValueError('Work ble endret under importen: ' + str(target))

        view = api.create_job(
            source_extraction=str(candidate.source),
            name=candidate.package_root.name or candidate.source.name,
            profile_id='noark5',
        )
        # Apply the *new* common run profile, not the legacy discovery sequence.
        # Leave explicitly configured jobs untouched; batch creates fresh jobs.
        apply_flow = getattr(api, 'set_workflow', None)
        if callable(apply_flow):
            if workflow_ids is None:
                from app.run_profiles_v022_a8 import selected_default
                workflow_ids = selected_default(api.settings).operation_ids
            if not workflow_ids:
                raise ValueError('Kjøreprofilen mangler deljobber.')
            apply_flow(view.job_id, tuple(workflow_ids))
        elif workflow_ids is not None:
            # Explicit profile requests may never be silently ignored.
            raise ValueError('Workbench API mangler støtte for moderne kjøreprofil.')
        # Basic mode requires BOTH paths to equal the selected Work directory.
        # package_root is only the provenance of Source, not the Work root.
        api.update_storage(view.job_id, {
            'work_root': str(target),
            'work_operations': str(target),
        })
        api.use_selected_work_directly(view.job_id)
        current_job = api.job_details(view.job_id).job
        effective = (getattr(current_job, 'effective_work_operations', None)
                     or getattr(current_job, 'work_operations', None))
        if effective is None or Path(effective).resolve(strict=False) != target.resolve(strict=False):
            raise ValueError('Effektiv Work er ulik valgt mappe. Jobben er ikke importert.')
        if on_created is not None:
            on_created(current_job)
        return view.job_id
    except Exception:
        if view is not None:
            try:
                api.remove_job(view.job_id)
            except Exception:
                pass
        # Only directories created by this call, and only while still empty.
        for directory in missing:
            try:
                directory.rmdir()
            except OSError:
                break
        raise


# Batch UI helpers. Keep them independent of PySide6 for regression coverage.
def suggest_batch_joblist_path(
        candidates: tuple[Candidate, ...], *, search_root: str | Path,
        dwm_folder: str = 'dwm', run_folder: str = 'a01',
        folder_overrides: Mapping[Path, str] | None = None,
        settings: Mapping | None = None, version: str | None = None,
) -> Path:
    """Propose one persistent list beside all packages, never in temp or Work.

    An explicit job-list directory in Setup takes precedence. Otherwise a
    common parent/Jobblister is used. Merely proposing creates nothing.
    """
    if not candidates:
        raise ValueError('Ingen uttrekk er valgt.')
    if version is None:
        from version import VERSION
        version = VERSION
    config = settings or {}
    explicit = str(config.get('job_list_dir') or '').strip()
    if explicit:
        directory = Path(explicit).expanduser()
    else:
        parents = [candidate.package_root.resolve(strict=False).parent
                   for candidate in candidates]
        if all(parent == parents[0] for parent in parents):
            common = parents[0]
        else:
            try:
                common = Path(os.path.commonpath([str(p) for p in parents]))
            except ValueError:
                common = None
        # A drive/volume root is not a good shared Jobblister location.
        if common is None or common.parent == common:
            common = Path.home() / 'Documents' / 'DWM'
        existing = next((common / name for name in ('Jobblister', 'jobblister')
                         if (common / name).is_dir()), None)
        directory = existing or common / 'Jobblister'

    identifiers = sorted({extraction_id(c) for c in candidates})
    groups = [re.fullmatch(r'(\d{4})_(\d{3,4})', identifier)
              for identifier in identifiers]
    if (len(identifiers) > 1 and all(groups)
            and len({m.group(1) for m in groups}) == 1):
        numbers = [int(m.group(2)) for m in groups]
        if numbers == list(range(min(numbers), max(numbers) + 1)):
            item_label = identifiers[0] + '-' + identifiers[-1].split('_')[-1]
        else:
            item_label = '_'.join(identifiers)
    else:
        item_label = '_'.join(identifiers) if len(identifiers) <= 3 else (
            identifiers[0] + '_og_' + str(len(identifiers)-1) + '_andre')
    folders = set((folder_overrides or {}).get(c.source, dwm_folder)
                  for c in candidates)
    dwm_label = next(iter(folders)) if len(folders) == 1 else 'flere-dwm'
    # Only the filename is sanitized; preserve the operator's chosen path.
    safe = lambda t: re.sub(r'[^A-Za-z0-9._-]+', '_', str(t)).strip('._-')
    stem = '_'.join(filter(None, (
        safe(item_label), safe(dwm_label), safe(run_folder),
        'v' + safe(version),
    )))
    proposal = directory / (stem + '.n5jobs')
    # Never suggest silently replacing an existing job list.
    number = 2
    while proposal.exists():
        proposal = directory / (stem + '_' + str(number) + '.n5jobs')
        number += 1
    return proposal


def activate_batch_job_in_window(window, job_id: str) -> None:
    """Synchronize Basic's selector/form after a batch API import.

    The API and the Basic selector have separate active/draft state. Importing
    directly through API without this call leaves Basic stuck at a blank draft.
    """
    window.api.select_job(job_id)
    window._active_id = job_id
    window._basic_job_id = job_id
    window._v022_draft = False
    window._basic_selection_edited = False
    window._a2_pending_dirty = False
    previous = getattr(window, '_v022_loading_job', False)
    window._v022_loading_job = True
    try:
        if getattr(window, '_basic_active', False):
            window._load_basic_active_job()
    finally:
        window._v022_loading_job = previous
    window._refresh(force=True)
    if hasattr(window, '_v022_refresh_selector'):
        window._v022_refresh_selector(force=True)
    if getattr(window, '_basic_active', False):
        if hasattr(window, '_a2_refresh_overview'):
            window._a2_refresh_overview()
        if hasattr(window, '_sync_basic_status'):
            window._sync_basic_status()
