"""Shared DIAS editing bridge for Basic/Advanced (v0.1.13-a2).

The existing depot_metadata.json remains authoritative; immutable imported
info.xml evidence is managed by the existing depot metadata implementation.
"""
from __future__ import annotations

from pathlib import Path
from contextlib import nullcontext
import json
import shutil
import xml.etree.ElementTree as ET

# Future Setup/per-job option. For a2 the requested default is fixed.
DIAS_LINK_LABEL_DELIVERYSPECIFICATION = True
METS_NS = 'http://www.loc.gov/METS/'


def linked_values(values: dict[str, str], changed: str = 'label') -> dict[str, str]:
    """Copy metadata and keep the two agreed fields identical."""
    result = dict(values)
    if DIAS_LINK_LABEL_DELIVERYSPECIFICATION:
        if changed == 'archive_description':
            result['label'] = str(result.get('archive_description') or '').strip()
        else:
            label = str(result.get('label') or '').strip()
            if 'label' not in result:
                label = str(result.get('archive_description') or '').strip()
            result['label'] = label
            result['archive_description'] = label
    return result


def candidate_info_xml(source: str | Path) -> Path | None:
    """Find nearby *package-level* METS without recursively scanning an extraction."""
    from noark5_workflow.operations.dias_mets import read_meta_from_mets
    start = Path(source).expanduser().resolve(strict=False)
    parents = (start, *list(start.parents)[:4])
    for base in parents:
        for relative in ('info.xml', 'INFO.XML', 'Info.xml', 'metadata/info.xml'):
            candidate = base / relative
            try:
                if not candidate.is_file() or candidate.stat().st_size > 8_000_000:
                    continue
            except OSError:
                continue
            try:
                # Existing DIAS parser provides one canonical field mapping.
                read_meta_from_mets(candidate)
            except (ValueError, OSError, ET.ParseError):
                continue
            return candidate
    return None


def read_original(path: str | Path) -> dict[str, str]:
    from noark5_workflow.operations.dias_mets import read_meta_from_mets
    return read_meta_from_mets(Path(path))


def _direct_context(job):
    """Scope resolution to the Work explicitly selected in the shared job.

    Advanced-mode paths are not touched. In particular, never guess based on
    a folder name such as a03 or dwm2.
    """
    from noark5_workflow.core.work_paths import selected_direct_work
    work = getattr(job, 'work_operations', None)
    getter = getattr(job, 'get_operation_params', None)
    layout = getter('__dwm_work_layout__') if callable(getter) else {}
    if work and isinstance(layout, dict) and layout.get('mode') == 'selected':
        return selected_direct_work(work)
    return nullcontext()


def _old_metadata_dir(job) -> Path | None:
    """Location mistakenly used by a2/a3 before job.json existed."""
    work = getattr(job, 'work_operations', None)
    if not work:
        return None
    getter = getattr(job, 'get_operation_params', None)
    layout = getter('__dwm_work_layout__') if callable(getter) else {}
    if not isinstance(layout, dict) or layout.get('mode') != 'selected':
        return None
    from settings import load_config
    folder = str(load_config().get('app_work_subfolder', 'dwm') or '').strip()
    sub = Path(folder)
    if not folder or sub.is_absolute() or '..' in sub.parts:
        return None
    return Path(work) / sub / 'metadata'


def _legacy_payload(job) -> dict | None:
    """Read legacy misplaced metadata without modifying or moving anything."""
    directory = _old_metadata_dir(job)
    if directory is None:
        return None
    path = directory / 'depot_metadata.json'
    if not path.is_file() or path.is_symlink():
        return None
    try:
        payload = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, ValueError, UnicodeError):
        return None
    if (not isinstance(payload, dict) or payload.get('file_type') != 'dwm-depot-metadata'
            or str(payload.get('job_id')) != str(job.job_id)):
        return None
    return payload


def _copy_misplaced_metadata(job) -> None:
    """Recover prior a3 metadata into the selected Work, without deleting it.

    Never overwrite a correct Work metadata directory, merge unrelated jobs,
    follow symlinks, or modify an original source file.
    """
    wrong = _old_metadata_dir(job)
    if wrong is None or not wrong.is_dir():
        return
    if wrong.is_symlink():
        raise ValueError('Kan ikke migrere symbolsk lenket metadataområde.')
    from noark5_workflow.reporting.depot_metadata import metadata_root_path
    with _direct_context(job):
        correct = metadata_root_path(job)
    if correct is None or correct == wrong:
        return
    if correct.exists():
        # Never silently merge two potentially divergent sets of metadata.
        return
    if _legacy_payload(job) is None:
        raise ValueError('Eldre metadata kan ikke knyttes til denne jobben. Ingen filer er endret.')
    for candidate in wrong.rglob('*'):
        if candidate.is_symlink():
            raise ValueError('Eldre metadata inneholder symbolske lenker. Ingen filer er endret.')
    correct.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(wrong, correct)


def current_values(job) -> dict[str, str]:
    from noark5_workflow.reporting.depot_metadata import load_depot_metadata, metadata_root_path
    with _direct_context(job):
        root = metadata_root_path(job)
        if root is not None and not (root / 'depot_metadata.json').is_file():
            legacy = _legacy_payload(job)
            if legacy is not None and isinstance(legacy.get('current'), dict):
                return dict(legacy['current'])
        return dict(load_depot_metadata(job)['current'])


def original_evidence_path(job) -> Path | None:
    """Return preserved original, including read-only legacy location fallback."""
    from noark5_workflow.reporting.depot_metadata import load_depot_metadata, metadata_root_path
    with _direct_context(job):
        root = metadata_root_path(job)
        if root is None:
            return None
        payload = load_depot_metadata(job)
        base = root.parent
        if not (root / 'depot_metadata.json').is_file():
            legacy = _legacy_payload(job)
            wrong = _old_metadata_dir(job)
            if legacy is not None and wrong is not None:
                payload = legacy
                base = wrong.parent
        for source in reversed(payload.get('source_imports') or []):
            path = str(source.get('preserved_file') or '')
            if path:
                candidate = (base / path).resolve(strict=False)
                if candidate.is_relative_to(base.resolve(strict=False)) and candidate.is_file():
                    return candidate
    return None


def persist_metadata(job, values: dict[str, str], original: str | Path | None = None) -> tuple[Path, Path]:
    """Persist in the selected Work; recover any misplaced a3 metadata safely."""
    _copy_misplaced_metadata(job)
    with _direct_context(job):
        return _persist_metadata_in_resolved_work(job, values, original)


def _persist_metadata_in_resolved_work(job, values: dict[str, str], original: str | Path | None = None) -> tuple[Path, Path]:
    """Save canonical metadata and an editable Work XML; never write to Source.

    The generated XML is a working metadata document, not a claim of XSD
    validation or a finished AIP. Historical original evidence stays unchanged.
    """
    from noark5_workflow.reporting.depot_metadata import (
        import_info_xml, load_depot_metadata, metadata_root_path, update_current_metadata,
    )
    from noark5_workflow.operations.dias_mets import (
        build_submission_description, DIAS_METADATA_FIELDS,
    )
    # The canonical model is also read by Advanced and DIAS export.
    root = metadata_root_path(job)
    if root is None:
        raise ValueError('Velg Work før DIAS-metadata kan lagres.')
    if original:
        path = Path(original).resolve(strict=True)
        if not path.is_file():
            raise ValueError('Original info.xml finnes ikke.')
        # Existing DWM importer copies and checksums the original as evidence.
        import_info_xml(job, path, overwrite_current=False, apply_current=False)
    canonical = {key: str(value or '').strip() for key, value in values.items()
                 if key in DIAS_METADATA_FIELDS}
    canonical = linked_values(canonical)
    metadata_json = update_current_metadata(job, canonical)
    effective = load_depot_metadata(job)['current']
    root.mkdir(parents=True, exist_ok=True)
    target = root / 'info-working.xml'
    # Keep the original package identifier stable across edits, if available.
    stable_id = None
    package_type = 'SIP'
    for identity_source in (original, target if target.is_file() else None):
        if not identity_source:
            continue
        try:
            document = ET.parse(str(identity_source)).getroot()
            if document.tag == '{' + METS_NS + '}mets':
                stable_id = document.get('OBJID') or stable_id
                package_type = document.get('TYPE') or package_type
                break
        except (ET.ParseError, OSError):
            pass
    tree = build_submission_description(effective, object_id=stable_id, package_type=package_type)
    temp = root / 'info-working.xml.tmp'
    try:
        tree.write(temp, encoding='utf-8', xml_declaration=True)
        temp.replace(target)
    finally:
        temp.unlink(missing_ok=True)
    return metadata_json, target
