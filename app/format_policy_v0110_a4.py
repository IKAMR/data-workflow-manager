"""v0.1.10-a4: separate, read-only assessment of identified file formats.

The identified PUID comes from external evidence (today Arkade5/Siegfried,
future direct Siegfried). An institution-specific, versioned JSON rule profile
is an INDEPENDENT interpretation: this module never edits evidence or AIP.
"""
from __future__ import annotations

import csv
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import re
from typing import Any, Iterable, Mapping

FORMAT_PROFILE_DIR = Path(__file__).resolve().parents[1] / 'config' / 'formats'
MAX_PROFILE_BYTES = 2_000_000
MAX_PROFILE_ENTRIES = 10_000
PUID_PATTERN = re.compile(r'(?:fmt|x-fmt)/[0-9]+\Z', re.IGNORECASE)
STATUS_ACCEPTED = 'accepted'
STATUS_CLARIFY = 'clarify'
STATUS_UNIDENTIFIED = 'unidentified'
STATUS_NOT_ASSESSED = 'not_assessed'
STATUS_LABELS = {
    STATUS_ACCEPTED: 'Akseptert i valgt profil',
    STATUS_CLARIFY: 'Til avklaring',
    STATUS_UNIDENTIFIED: 'Ikke identifisert',
    STATUS_NOT_ASSESSED: 'Ikke vurdert',
}


@dataclass(frozen=True)
class FormatRule:
    puid: str
    name: str
    extensions: str = ''
    versions: str = ''


@dataclass(frozen=True)
class FormatPolicy:
    policy_id: str
    title: str
    edition: str
    captured_at: str
    source_url: str
    authority: str
    entries: Mapping[str, FormatRule]
    sha256: str
    path: Path

    @property
    def label(self) -> str:
        return f'{self.title} ({self.edition})'

    def provenance(self) -> dict[str, str]:
        return {
            'policy_id': self.policy_id,
            'title': self.title,
            'edition': self.edition,
            'captured_at': self.captured_at,
            'source_url': self.source_url,
            'authority': self.authority,
            'sha256': self.sha256,
        }


@dataclass(frozen=True)
class FormatDecision:
    status: str
    puid: str
    explanation: str
    matched_rule: FormatRule | None = None

    @property
    def label(self) -> str:
        return STATUS_LABELS[self.status]


def _text(value: Any) -> str:
    return str(value or '').replace('\u00a0', ' ').strip()


def normalize_puid(raw: Any) -> str:
    return _text(raw).casefold()


def load_format_policy(path: str | Path) -> FormatPolicy:
    """Read a data-only, pinned policy; reject partial/ambiguous profiles."""
    file = Path(path).expanduser()
    if file.suffix.lower() != '.json' or not file.is_file():
        raise ValueError('Velg en eksisterende JSON-fil med formatregler.')
    if file.stat().st_size > MAX_PROFILE_BYTES:
        raise ValueError('Formatprofilen er for stor (maksimalt 2 MB).')
    raw = file.read_bytes()
    try:
        model = json.loads(raw.decode('utf-8-sig'))
    except (UnicodeError, ValueError) as exc:
        raise ValueError('Uleselig JSON-formatprofil.') from exc
    if not isinstance(model, dict) or model.get('schema_version') != 1:
        raise ValueError('Ukjent formatprofil eller skjemaversjon (forventet 1).')
    mandatory = ('policy_id', 'title', 'edition', 'captured_at', 'source_url', 'authority')
    fields = {key: _text(model.get(key)) for key in mandatory}
    if any(not value for value in fields.values()):
        raise ValueError('Formatprofilen mangler identitet, utgave eller kildeinformasjon.')
    if not re.fullmatch(r'[a-z0-9][a-z0-9_.-]{1,100}', fields['policy_id']):
        raise ValueError('Ugyldig formatprofil-ID.')
    records = model.get('accepted_puids')
    if not isinstance(records, list) or not records or len(records) > MAX_PROFILE_ENTRIES:
        raise ValueError('Formatprofilen må ha 1–10 000 PUID-definisjoner.')
    rules: dict[str, FormatRule] = {}
    for index, row in enumerate(records, 1):
        if not isinstance(row, dict):
            raise ValueError(f'Ugyldig PUID-oppføring {index}.')
        puid = normalize_puid(row.get('puid'))
        name = _text(row.get('name'))
        if not PUID_PATTERN.fullmatch(puid) or not name:
            raise ValueError(f'Ugyldig PUID eller formatnavn på rad {index}.')
        if puid in rules:
            raise ValueError(f'Dobbel PUID i formatprofil: {puid}.')
        rules[puid] = FormatRule(
            puid=puid, name=name,
            extensions=_text(row.get('extensions')),
            versions=_text(row.get('versions')),
        )
    return FormatPolicy(
        **fields, entries=rules, sha256=hashlib.sha256(raw).hexdigest(),
        path=file.resolve(strict=True),
    )


def discover_format_policies(directory: str | Path = FORMAT_PROFILE_DIR) -> tuple[FormatPolicy, ...]:
    """Discover bundled, fixed-edition policies; invalid files are not accepted."""
    folder = Path(directory)
    if not folder.is_dir():
        return ()
    found = []
    for path in sorted(folder.glob('*.json'), key=lambda p: p.name.casefold()):
        try:
            found.append(load_format_policy(path))
        except (ValueError, OSError):
            continue
    return tuple(found)


def evaluate_puid(puid: Any, policy: FormatPolicy | None) -> FormatDecision:
    """Classify evidence against the chosen profile, not against Arkade's RAF flag.

    A PUID absent from one institution's profile is NOT automatically invalid,
    non-standard or a conversion requirement. It needs a professional decision.
    """
    value = normalize_puid(puid)
    if not PUID_PATTERN.fullmatch(value):
        return FormatDecision(
            STATUS_UNIDENTIFIED, value,
            'Sikker PRONOM PUID mangler. Kontroller identifiseringen før formatvurdering.',
        )
    if policy is None:
        return FormatDecision(
            STATUS_NOT_ASSESSED, value,
            'Ingen formatregelprofil er valgt. Identifiseringen er likevel bevart.',
        )
    rule = policy.entries.get(value)
    if rule is not None:
        return FormatDecision(
            STATUS_ACCEPTED, value,
            f'PUID finnes i valgt regelprofil: {rule.name}. '
            'Gjelder bare denne institusjonens valgte formatliste og erstatter ikke faglig godkjenning.',
            rule,
        )
    return FormatDecision(
        STATUS_CLARIFY, value,
        'PUID står ikke i valgt regelprofil. Dette betyr ikke automatisk at filen '
        'er feil eller skal konverteres; vurder avtale, formål og bevaringsbehov.',
    )


def _amount(raw: Any) -> int:
    if isinstance(raw, bool):
        return 0
    value = _text(raw).replace(' ', '').replace('\u202f', '')
    if not value:
        return 0
    try:
        return max(0, int(value))
    except ValueError:
        return 0


def summarize_format_assessments(
    rows: Iterable[Mapping[str, Any]],
    policy: FormatPolicy | None,
) -> dict[str, Any]:
    """A backend-neutral summary of already-identified format observations."""
    sums = {status: {'rows': 0, 'files': 0} for status in STATUS_LABELS}
    for row in rows:
        puid = row.get('format_id', row.get('puid', row.get('Format-ID', row.get('PUID'))))
        count = row.get('count', row.get('Antall', 0))
        decision = evaluate_puid(puid, policy)
        sums[decision.status]['rows'] += 1
        sums[decision.status]['files'] += _amount(count)
    return {
        'policy': policy.provenance() if policy is not None else None,
        'statuses': sums,
    }


def export_format_assessments_csv(
    target: str | Path,
    rows: Iterable[Mapping[str, Any]],
    policy: FormatPolicy | None,
    *,
    overwrite: bool = False,
) -> Path:
    """Explicit read-only assessment export; no Source, AIP or source CSV writes."""
    target = Path(target)
    if target.suffix.casefold() != '.csv':
        raise ValueError('Eksportfilen må ha filendelsen .csv.')
    header = (
        'Uttrekk', 'Format-ID / PUID', 'Filtype', 'Versjon', 'Antall',
        'Arkade RAF (historisk observasjon)', 'Vurdering', 'Forklaring',
        'Regelprofil', 'Utgave', 'Profil SHA-256', 'Kilde URL', 'Kilde/import',
    )
    mode = 'w' if overwrite else 'x'
    with target.open(mode, encoding='utf-8-sig', newline='') as stream:
        writer = csv.writer(stream, delimiter=';')
        writer.writerow(header)
        for row in rows:
            decision = evaluate_puid(row.get('format_id'), policy)
            writer.writerow((
                _text(row.get('job')), _text(row.get('format_id')),
                _text(row.get('file_type')), _text(row.get('version')),
                _amount(row.get('count')), _text(row.get('raf')),
                decision.label, decision.explanation,
                policy.policy_id if policy else '',
                policy.edition if policy else '',
                policy.sha256 if policy else '',
                policy.source_url if policy else '',
                _text(row.get('evidence_source')),
            ))
    return target
