"""v0.2.0-a3: Qt-neutral adapter for DWM's existing two-stage depot ingest.

This layer never invents receipt structures or runs AV/copy/restore. Preview is
read-only; only explicit operator confirmation in the GUI calls create().
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

DEFAULT_RECEIVING_SETUP = (
    Path(__file__).resolve().parents[1] / 'config' / 'receiving_folder_profiles.json'
)


@dataclass(frozen=True)
class IngestRequest:
    mode: str
    setup_file: str
    profile_id: str
    disk: str
    group: str
    owner_code: str
    receipt_number: str
    label: str
    extraction_id: str = ''
    unpack_date: str = ''
    info_xml: str = ''


def available_profiles(setup_file: str):
    """Return only the grouped receiving profiles defined in external Setup."""
    from app.grouped_ingest import grouped_profiles
    return grouped_profiles(setup_file)


def prepare_ingest(request: IngestRequest):
    """Delegate all validations and planning to existing authoritative backend.

    Does not mkdir, copy, download, record an AV decision, or touch a job.
    """
    from app.grouped_ingest import plan_receipt, plan_extraction
    profiles = {profile.profile_id: profile for profile in available_profiles(request.setup_file)}
    if request.profile_id not in profiles:
        raise ValueError('Velg en gyldig mottaksprofil fra valgt depot-setup')
    profile = profiles[request.profile_id]
    xml = request.info_xml.strip() or None
    if xml:
        # Use existing METS reader to reject unsuitable info.xml before create.
        from app.receiving_folders import read_info_xml
        read_info_xml(xml)
    common = (request.disk.strip(), request.group.strip(), profile,
              request.owner_code.strip(), request.receipt_number.strip(),
              request.label.strip())
    if request.mode == 'receipt':
        return plan_receipt(*common, info_xml=xml)
    if request.mode == 'extraction':
        return plan_extraction(*common, request.extraction_id.strip(),
                               request.unpack_date.strip(), info_xml=xml)
    raise ValueError('Ukjent mottakshandling')


def preview_ingest(plan) -> str:
    """Portable textual preview of the exact backend plan; read-only."""
    lines = [
        'Handling: ' + ('Mottak' if plan.mode == 'receipt' else 'Uttrekk'),
        'Eierkommune: ' + plan.owner_code,
        'Mottaksnummer: ' + plan.receipt_number,
        'LABEL: ' + plan.label,
        'Mottaksmappe: ' + str(plan.receipt_root),
        'Ny mappe: ' + str(plan.root),
    ]
    if plan.mode == 'extraction':
        lines.extend(['Uttrekks-ID: ' + plan.extraction_id,
                      'Dato: ' + plan.ingest_date])
    lines.extend(['', 'Planlagte mapper:'])
    lines.extend('  ' + str(folder.relative_to(plan.group)) + '/'
                 for folder in plan.paths)
    lines.extend([
        '', 'Kanonisk mottakslogg: ' + str(plan.audit_path),
        'Lesbar mottakslogg: ' + str(plan.receipt_root / 'depot-log.txt'),
    ])
    if plan.mode == 'receipt':
        lines.extend([
            '', 'Mottaket er en flat E-mappe; ingen undermapper opprettes her.',
            'Leveransen må lastes ned manuelt. Ingen filer er lastet ned eller skannet.',
        ])
    else:
        operations_root = plan.root / plan.profile.operations_folder
        lines.extend([
            'Uttrekkslogg: ' + str(operations_root / 'depot-log.txt'),
            'Portabel hendelseslogg: ' + str(operations_root / 'ingest.events.jsonl'),
            '', 'Uttrekksmappen opprettes separat fra mottaksmappen.',
            'Ingen filer pakkes ut, kopieres eller flyttes.',
        ])
    return '\n'.join(lines)


def create_ingest(plan):
    """Perform ONLY the backend's directory+audit creation after GUI consent."""
    from app.grouped_ingest import create_grouped_ingest
    from app.identity_provider import LocalUserProfileIdentityProvider
    actor = LocalUserProfileIdentityProvider().current_identity()
    return create_grouped_ingest(plan, actor=actor)
