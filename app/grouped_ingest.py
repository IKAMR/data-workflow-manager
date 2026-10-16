"""Two-stage depot receiving on grouped quarantine disks.

An intake number identifies an *incoming delivery*, not an archive extraction.
One receiving directory may therefore be related to several independently
numbered extraction work directories beside it under the same quarantine group.
The event ledger belongs to the receipt, and is append-only.
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from string import Formatter
from typing import Any, Mapping
from uuid import uuid4

from app.receiving_folders import (_check_segment, _segments, SETUP_FILE_TYPE, SETUP_VERSION)

RECEIPT = re.compile(r"^E-(\d{4})-(\d{4})-(\d{4,})$")
EXTRACTION = re.compile(r"^(\d{4})_(\d{3,})$")
DEFAULT_PATTERN = "{date}_{extraction_id}_{receipt_number}"


@dataclass(frozen=True)
class GroupedProfile:
    profile_id: str
    name: str
    group_prefix: str
    extraction_pattern: str
    extraction_folders: tuple[str, ...]
    receipt_log: str
    operations_folder: str = "repository_operations"


@dataclass(frozen=True)
class IngestPlan:
    mode: str
    disk: Path
    group: Path
    root: Path
    paths: tuple[Path, ...]
    receipt_root: Path
    receipt_number: str
    owner_code: str
    label: str
    extraction_id: str
    ingest_date: str
    profile: GroupedProfile
    info_xml: Path | None = None

    @property
    def audit_path(self) -> Path:
        return self.receipt_root / self.profile.receipt_log


def grouped_profiles(path: str | Path) -> tuple[GroupedProfile, ...]:
    """Only profiles explicitly marked grouped_ingest are exposed to this flow."""
    data = json.loads(Path(path).read_text(encoding='utf-8'))
    if (not isinstance(data, dict) or data.get('file_type') != SETUP_FILE_TYPE
            or data.get('format_version') != SETUP_VERSION):
        raise ValueError('Ugyldig mottaks-setup')
    result = []
    for row in data.get('profiles', []):
        options = row.get('grouped_ingest') if isinstance(row, dict) else None
        if not isinstance(options, dict):
            continue
        prefix = str(options.get('group_prefix', '')).strip()
        pattern = str(options.get('extraction_pattern', DEFAULT_PATTERN)).strip()
        folders = options.get('extraction_folders', [])
        receipt_log = str(options.get('receipt_log', 'ingest.events.jsonl')).strip()
        operations_folder = str(options.get('operations_folder', 'repository_operations')).strip()
        if not prefix or '/' in prefix or '\\' in prefix or not re.fullmatch(r'[A-Za-z0-9_-]+', prefix):
            raise ValueError('Ugyldig group_prefix i depot-setup')
        if (not isinstance(folders, list) or not folders or
                not all(isinstance(folder, str) for folder in folders)):
            raise ValueError('grouped_ingest.extraction_folders må være en ikke-tom liste')
        fields = set()
        try:
            for _, field, format_spec, conversion in Formatter().parse(pattern):
                if field is not None:
                    if field not in {'date', 'extraction_id', 'receipt_number'} or format_spec or conversion:
                        raise ValueError('Ugyldig felt i extraction_pattern')
                    fields.add(field)
        except ValueError as exc:
            raise ValueError(f'Ugyldig extraction_pattern: {exc}') from exc
        if fields != {'date', 'extraction_id', 'receipt_number'}:
            raise ValueError('Uttrekksmappen må inneholde dato, uttrekks-ID og mottaksnummer')
        sample = pattern.format(date='2026-10-15', extraction_id='1505_019', receipt_number='E-1505-2026-0004')
        _check_segment(sample)
        for folder in folders:
            _segments(folder)
        _check_segment(receipt_log)
        _check_segment(operations_folder)
        result.append(GroupedProfile(str(row['id']), str(row['name']), prefix,
                                     pattern, tuple(folders), receipt_log, operations_folder))
    return tuple(result)


def _is_child(candidate: Path, parent: Path) -> bool:
    return candidate.is_relative_to(parent)


def resolve_group(disk: str | Path, group: str | Path, profile: GroupedProfile) -> tuple[Path, Path]:
    """Validate canonical containment, preserve the caller's Windows path spelling.

    On Windows, Path.resolve() can expand an 8.3 short user-directory name.
    Use resolved paths for authorization and the original disk path for the
    returned, consistently spelled group/receipt/extraction paths.
    """
    disk_input = Path(disk).expanduser()
    group_input = disk_input / Path(group).expanduser()
    disk_real = disk_input.resolve(strict=True)
    group_real = group_input.resolve(strict=True)
    if not disk_real.is_dir():
        raise ValueError('Velg tilgjengelig karantenedisk')
    if (not group_real.is_dir() or not _is_child(group_real, disk_real)
            or group_real == disk_real or group_real.parent != disk_real):
        raise ValueError('Gruppemappen må være direkte under den valgte disken')
    if not re.fullmatch(re.escape(profile.group_prefix) + r'\d+', group_input.name, re.I):
        raise ValueError(f'Velg en eksisterende gruppemappe {profile.group_prefix}nn')
    # Even if the caller passed the same directory using another spelling,
    # normalize only to the original disk path, not to Path.resolve() output.
    group_view = disk_input / group_input.name
    if (not group_view.is_dir() or group_view.is_symlink()
            or group_view.resolve(strict=True) != group_real):
        raise ValueError('Gruppemappen må være en direkte mappe på valgt disk')
    return disk_input, group_view


def _casefold_exists(folder: Path) -> bool:
    return (folder.exists() or folder.is_symlink() or
            (folder.parent.is_dir() and any(p.name.casefold() == folder.name.casefold() for p in folder.parent.iterdir())))


def _groups(disk: Path, profile: GroupedProfile):
    matcher = re.compile(re.escape(profile.group_prefix) + r'\d+', re.I)
    return (p for p in disk.iterdir() if p.is_dir() and not p.is_symlink() and matcher.fullmatch(p.name))


def _receipt_locations(disk: Path, profile: GroupedProfile, receipt_number: str) -> tuple[Path, ...]:
    return tuple(p for g in _groups(disk, profile) for p in g.iterdir()
                 if p.is_dir() and not p.is_symlink() and p.name.casefold() == receipt_number.casefold())


def _owner(value: str) -> str:
    v = str(value).strip()
    if not re.fullmatch(r'\d{4}', v):
        raise ValueError('Eierkommune skal være fire siffer (gjeldende kommunenummer)')
    return v


def _number(value: str, owner: str) -> str:
    v = str(value or '').strip().upper()
    m = RECEIPT.fullmatch(v)
    if not m or m.group(1) != owner or not 1900 <= int(m.group(2)) <= 9999:
        raise ValueError('Mottaksnummer skal være E-FFKK-YYYY-nnnn med riktig eierkommune')
    return v


def suggest_receipt_number(disk: str | Path, profile: GroupedProfile, owner: str,
                           *, year: int | None = None) -> str:
    """Suggest next number from ALL grouped folders visible on selected disk.

    This is not a cross-disk authoritative registry; the GUI must state this.
    """
    disk = Path(disk).expanduser().resolve(strict=True)
    owner = _owner(owner)
    yr = int(year or date.today().year)
    if not 1900 <= yr <= 9999:
        raise ValueError('Ugyldig år')
    seq = 0
    for group in _groups(disk, profile):
        for entry in group.iterdir():
            if not entry.is_dir():
                continue
            m = RECEIPT.fullmatch(entry.name.upper())
            if m and m.group(1) == owner and int(m.group(2)) == yr:
                seq = max(seq, int(m.group(3)))
    return f'E-{owner}-{yr}-{seq + 1:04d}'


def _expected_receipt(disk: Path, group: Path, number: str, profile: GroupedProfile) -> Path:
    locations = _receipt_locations(disk, profile, number)
    if len(locations) != 1 or locations[0].parent != group:
        raise ValueError('Eksisterende mottaksnummer er ikke funnet entydig i valgt karantenegruppe')
    return locations[0]


def _date(value: str) -> str:
    value = str(value).strip()
    if not re.fullmatch(r'\d{4}-\d{2}-\d{2}', value):
        raise ValueError('Bruk dato YYYY-MM-DD')
    try:
        date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError('Bruk dato YYYY-MM-DD') from exc
    return value


def _extraction(value: str, label: str) -> str:
    v = str(value or '').strip()
    if not EXTRACTION.fullmatch(v):
        raise ValueError('Uttrekks-ID skal være FFKK_nnn (arkivskaperkommune, også historisk)')
    if not str(label or '').strip():
        raise ValueError('LABEL må ha verdi')
    return v


def _tree(root: Path, folders: tuple[str, ...]) -> tuple[Path, ...]:
    nodes = {root}
    for folder in folders:
        current = root
        for part in _segments(folder):
            current = current / part
            nodes.add(current)
    return tuple(sorted(nodes, key=lambda x: (len(x.relative_to(root).parts), str(x).casefold())))


def plan_receipt(disk: str | Path, group: str | Path, profile: GroupedProfile,
                 owner: str, number: str, label: str, info_xml: str | Path | None = None) -> IngestPlan:
    disk, group = resolve_group(disk, group, profile)
    owner = _owner(owner)
    number = _number(number, owner)
    label = str(label or '').strip()
    if not label:
        raise ValueError('LABEL må ha verdi')
    if _receipt_locations(disk, profile, number) or _casefold_exists(group / number):
        raise FileExistsError(f'Mottaksnummer finnes allerede på disken: {number}')
    root = group / number
    # A new receipt is a single flat E-... directory. No operations/content
    # subdirectories are created until a separate extraction is established.
    return IngestPlan('receipt', disk, group, root,
                      (root,), root, number, owner,
                      label, '', '', profile, Path(info_xml) if info_xml else None)


def plan_extraction(disk: str | Path, group: str | Path, profile: GroupedProfile,
                    owner: str, number: str, label: str, extraction_id: str,
                    unpack_date: str, info_xml: str | Path | None = None) -> IngestPlan:
    disk, group = resolve_group(disk, group, profile)
    owner = _owner(owner)
    number = _number(number, owner)
    label = str(label or '').strip()
    extraction_id = _extraction(extraction_id, label)
    unpack_date = _date(unpack_date)
    receipt_root = _expected_receipt(disk, group, number, profile)
    name = _check_segment(profile.extraction_pattern.format(
        date=unpack_date, extraction_id=extraction_id, receipt_number=number))
    root = group / name
    if _casefold_exists(root):
        raise FileExistsError(f'Uttrekksmappen finnes allerede: {root}')
    return IngestPlan('extraction', disk, group, root,
                      _tree(root, profile.extraction_folders + (profile.operations_folder,)), receipt_root,
                      number, owner, label, extraction_id, unpack_date, profile,
                      Path(info_xml) if info_xml else None)


def create_grouped_ingest(plan: IngestPlan, *, actor=None) -> tuple[Path, ...]:
    """Create an entire empty tree; persist event in the receipt event ledger.

    For extraction creation, the pre-existing receipt ledger MUST be writable
    before anything is created. We never remove previous events on failure.
    """
    disk, group = resolve_group(plan.disk, plan.group, plan.profile)
    if plan.mode == 'receipt':
        _number(plan.receipt_number, _owner(plan.owner_code))
        if _receipt_locations(disk, plan.profile, plan.receipt_number):
            raise FileExistsError('Mottaksnummer finnes allerede')
    elif plan.mode == 'extraction':
        _expected_receipt(disk, group, plan.receipt_number, plan.profile)
        if not plan.audit_path.is_file():
            raise ValueError('Mottaket mangler hendelseslogg; kan ikke opprette uttrekk uten sporing')
    else:
        raise ValueError('Ukjent mottaksoperasjon')
    if _casefold_exists(plan.root):
        raise FileExistsError(f'Mappen finnes allerede: {plan.root}')
    if plan.info_xml is not None and not plan.info_xml.is_file():
        raise ValueError('Valgt info.xml finnes ikke lenger')
    sha = hashlib.sha256(plan.info_xml.read_bytes()).hexdigest() if plan.info_xml else ''
    try:
        log_size_before = plan.audit_path.stat().st_size if plan.audit_path.is_file() else 0
    except OSError:
        log_size_before = 0
    created = []
    try:
        for directory in plan.paths:
            directory.mkdir(exist_ok=False)
            created.append(directory)
        from noark5_workflow.core.events import WorkflowEvent
        from noark5_workflow.sinks.event_store import GenericEventStoreSink
        event = WorkflowEvent.now(
            'ingest.receipt.created' if plan.mode == 'receipt' else 'ingest.extraction.created',
            run_id=f'INGEST-{uuid4().hex}',
            operation_id='ingest.create_receipt' if plan.mode == 'receipt' else 'ingest.create_extraction',
            operation_name='Opprett mottaksmappe' if plan.mode == 'receipt' else 'Opprett uttrekksmappe',
            user=actor,
            data={
                'owner_municipality': plan.owner_code,
                'receipt_number': plan.receipt_number,
                'label': plan.label,
                'extraction_id': plan.extraction_id,
                'unpack_date': plan.ingest_date,
                'disk': str(plan.disk),
                'group': str(plan.group),
                'created_path': str(plan.root),
                'receiving_path': str(plan.receipt_root),
                'profile_id': plan.profile.profile_id,
                'folders': [str(path.relative_to(plan.root)) for path in plan.paths],
                'info_xml': str(plan.info_xml) if plan.info_xml else '',
                'info_xml_sha256': sha,
                # The receipt has NOT been downloaded by this operation.
                'delivery_state': 'awaiting_download' if plan.mode == 'receipt' else '',
            },
        )
        GenericEventStoreSink(plan.audit_path).handle(event)
        # The receipt is flat: its JSONL and text logs are both files directly
        # inside E-... . Only extraction work directories have a
        # repository_operations subdirectory and portable event snapshot.
        from app.ingest_operation_log import log_ingest_creation
        log_ingest_creation(plan)
    except Exception:
        # If any bytes were written to the append-only ledger, NEVER delete the
        # associated directories. Preserve all evidence for operator recovery.
        try:
            after_size = plan.audit_path.stat().st_size if plan.audit_path.is_file() else 0
        except OSError:
            after_size = log_size_before
        if after_size != log_size_before:
            raise RuntimeError('Hendelsesloggen kan være delvis skrevet. Mapper beholdes for manuell kontroll; undersøk loggen før nytt forsøk.')
        for directory in reversed(created):
            try:
                directory.rmdir()
            except OSError:
                pass
        raise
    return tuple(created)
