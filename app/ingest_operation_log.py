"""Human-readable and portable projections of the canonical ingest event store.

The receipt's original ``ingest.events.jsonl`` remains the authoritative ledger.
On extraction creation, the relevant receipt event and extraction event are
copied WITH THEIR ORIGINAL IDs to the new extraction work root. Imports must
therefore deduplicate by event_id; copies are never treated as new events.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Mapping

READABLE_NAME = 'depot-log.txt'
PORTABLE_NAME = 'ingest.events.jsonl'


def _read_records(path: Path) -> list[dict]:
    records = []
    with path.open('r', encoding='utf-8') as f:
        for number, line in enumerate(f, start=1):
            if line.strip():
                try:
                    record = json.loads(line)
                except json.JSONDecodeError as exc:
                    raise ValueError(f'Ugyldig hendelseslogg, linje {number}: {exc}') from exc
                if not isinstance(record, dict):
                    raise ValueError(f'Ikke en hendelse på linje {number}')
                records.append(record)
    return records


def _description(rec: Mapping) -> str:
    kind = rec.get('kind')
    return {'ingest.receipt.created': 'Mottaksmappe opprettet',
            'ingest.extraction.created': 'Uttrekksmappe opprettet'}.get(str(kind), str(kind))


def format_record(rec: Mapping) -> str:
    """Stable, legible audit entry. Never include passwords or secret material."""
    d = rec.get('data') or {}
    if not isinstance(d, Mapping):
        d = {}
    user = rec.get('user') or {}
    if not isinstance(user, Mapping):
        user = {}
    actor = user.get('name') or user.get('username') or user.get('user_id') or 'Ikke registrert'
    fields = [
        ('Hendelse', _description(rec)),
        ('Tidspunkt', rec.get('timestamp', '')),
        ('Hendelses-ID', rec.get('event_id', '')),
        ('Run-ID', rec.get('run_id', '')),
        ('Utførende', actor),
        ('Resultat', 'OK' if rec.get('success', True) else 'FEIL'),
        ('Mottaksnummer', d.get('receipt_number', '')),
        ('Eierkommune', d.get('owner_municipality', '')),
        ('LABEL', d.get('label', '')),
        ('Uttrekks-ID', d.get('extraction_id', '')),
        ('Dato for uttrekksmappe', d.get('unpack_date', '')),
        ('Profil', d.get('profile_id', '')),
        ('Disk', d.get('disk', '')),
        ('Karantenegruppe', d.get('group', '')),
        ('Mottaksmappe', d.get('receiving_path', '')),
        ('Opprettet mappe', d.get('created_path', '')),
        ('Opprettede mapper', ', '.join(map(str, d.get('folders', [])))),
        ('Leveransestatus', 'Venter på manuell nedlasting' if d.get('delivery_state') == 'awaiting_download' else ''),
        ('Kilde info.xml', d.get('info_xml', '')),
        ('SHA-256 info.xml', d.get('info_xml_sha256', '')),
    ]
    return '\n'.join(f'{key}: {value}' for key, value in fields if value not in ('', None)) + '\n' + ('-' * 72) + '\n'


def _append_text(path: Path, entry: str) -> None:
    if not path.parent.is_dir():
        raise ValueError(f'Loggmappen eksisterer ikke: {path.parent}')
    with path.open('a', encoding='utf-8', newline='\n') as f:
        f.write(entry)


def log_ingest_creation(plan) -> None:
    """Called after canonical JSONL append. Fail visibly; do not lose the folder."""
    entries = _read_records(plan.audit_path)
    if not entries:
        raise ValueError('Hendelsesloggen inneholder ingen opprettelseshendelse')
    newest = entries[-1]
    data = newest.get('data') or {}
    if data.get('created_path') != str(plan.root) or data.get('receipt_number') != plan.receipt_number:
        raise ValueError('Siste logghendelse matcher ikke opprettet mappe; behold mapper til kontroll')
    # Receipt is a flat directory, even when this function is called while
    # creating an extraction. Do not create repository_operations at receipt.
    receipt_text = plan.receipt_root / READABLE_NAME
    if receipt_text.is_symlink():
        raise ValueError('Depotloggen er en symbolsk lenke. Stopp for manuell kontroll.')
    if receipt_text.exists():
        _append_text(receipt_text, format_record(newest))
    else:
        # Backfill from canonical JSONL for old receipts (fix3/fix4). A
        # pre-existing repository_operations/depot-log.txt is left untouched.
        # No extra directory is created and no event is replayed into JSONL.
        with receipt_text.open('x', encoding='utf-8', newline='\n') as f:
            f.write('DWM – Depotlogg for mottak (fra kanonisk hendelseslogg)\n\n')
            for record in entries:
                f.write(format_record(record))
    if plan.mode == 'extraction':
        extraction_ops = plan.root / plan.profile.operations_folder
        receipt_created = next((x for x in entries if x.get('kind') == 'ingest.receipt.created'
                          and (x.get('data') or {}).get('receipt_number') == plan.receipt_number), None)
        selected = [receipt_created, newest] if receipt_created is not None else [newest]
        # New extraction tree: these paths do not exist before this operation.
        # Reuse original event IDs so a later importer can deduplicate copies.
        portable = extraction_ops / PORTABLE_NAME
        with portable.open('x', encoding='utf-8', newline='\n') as f:
            for record in selected:
                f.write(json.dumps(record, ensure_ascii=False) + '\n')
        local_log = extraction_ops / READABLE_NAME
        with local_log.open('x', encoding='utf-8', newline='\n') as f:
            f.write('DWM – Depotlogg for uttrekk (inkludert mottaksreferanse)\n')
            f.write('Hendelsene er kopier av opprinnelige hendelses-ID-er.\n\n')
            for record in selected:
                f.write(format_record(record))
