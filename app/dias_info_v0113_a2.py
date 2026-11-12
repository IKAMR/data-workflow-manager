"""Shared DIAS editing bridge for Basic/Advanced (v0.1.13-a2).

The existing depot_metadata.json remains authoritative; immutable imported
info.xml evidence is managed by the existing depot metadata implementation.
"""
from __future__ import annotations

from pathlib import Path
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
            if not label:
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


def current_values(job) -> dict[str, str]:
    from noark5_workflow.reporting.depot_metadata import load_depot_metadata
    return dict(load_depot_metadata(job)['current'])


def original_evidence_path(job) -> Path | None:
    """Return the preserved original if there is one, not its mutable Source."""
    from noark5_workflow.reporting.depot_metadata import load_depot_metadata, metadata_root_path
    root = metadata_root_path(job)
    if root is None:
        return None
    for source in reversed(load_depot_metadata(job)['source_imports']):
        path = str(source.get('preserved_file') or '')
        if path:
            base = root.parent
            candidate = (base / path).resolve(strict=False)
            if candidate.is_relative_to(base.resolve(strict=False)) and candidate.is_file():
                return candidate
    return None


def persist_metadata(job, values: dict[str, str], original: str | Path | None = None) -> tuple[Path, Path]:
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
