"""Selection of the assessment authority, independent of identification evidence.

The historical RAF-220301 column is a preserved Arkade observation, not a
current format policy. The dated Nasjonalarkivet JSON is a policy lookup, not
file-format validation and not approval of an archival deposit.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

FORMAT_SOURCE_NASJONALARKIVET = 'nasjonalarkivet_2026_11_10'
FORMAT_SOURCE_ARKADE_RAF = 'arkade_raf220301'
DEFAULT_FORMAT_SOURCE = FORMAT_SOURCE_NASJONALARKIVET

FORMAT_SOURCES = (
    (FORMAT_SOURCE_NASJONALARKIVET,
     'Nasjonalarkivet - datert formatliste (2026-11-10)',
     'Vurder identifiserte PUID-er mot den daterte JSON-kopien. '
     'Treff betyr bare at formatet finnes i listen, ikke godkjenning.'),
    (FORMAT_SOURCE_ARKADE_RAF,
     'Arkade 5 - RAF-220301 (historisk)',
     'Vis den lagrede, historiske klassifiseringen fra Arkade 5. '
     'Dette er ikke en kontroll mot gjeldende regelverk.'),
)


@dataclass(frozen=True)
class HistoricalStatus:
    code: str
    label: str


def require_format_source(value: object) -> str:
    source = str(value or '').strip()
    if source not in {item[0] for item in FORMAT_SOURCES}:
        raise ValueError('Ukjent grunnlag for filformatvurdering: ' + source)
    return source


def chosen_format_source(settings: Mapping[str, object] | None) -> str:
    source = (settings or {}).get('format_assessment_source', DEFAULT_FORMAT_SOURCE)
    return require_format_source(source)


def historical_arkade_status(raw: object) -> HistoricalStatus:
    """Interpret an already *saved* RAF status, without editing its raw text.

    Unknown values remain unknown, not automatically invalid.  Check negative
    and conditional statuses before bare 'valid'/'gyldig' substring matches.
    """
    value = ' '.join(str(raw or '').casefold().replace('_', ' ').split())
    if not value or value in {'-', 'ukjent', 'unknown', 'none', 'n/a'}:
        return HistoricalStatus('unknown', 'Ukjent')
    if any(token in value for token in ('ikke gyldig', 'ugyldig', 'ikke arkivformat',
                                        'invalid', 'not valid', 'not accepted')):
        return HistoricalStatus('invalid', 'Ikke gyldig arkivformat')
    if any(token in value for token in ('*', 'forbehold', 'merknad', 'conditional')):
        return HistoricalStatus('conditional', 'Gyldig med forbehold')
    if 'gyldig' in value or value in {'valid', 'arkivformat'}:
        return HistoricalStatus('valid', 'Gyldig arkivformat')
    return HistoricalStatus('unknown', 'Ukjent')
