"""Readable, source-specific annual period evidence for a manual depot review.

Never merge Standard/U1/U2, infer dates from change logs, or select a period.
This module is display-only; it never changes source evidence or assessments.
"""
from __future__ import annotations

from typing import Any

from .period_kdrs_evidence_a18 import YEAR_METRICS, PERIOD_METRICS

# Fixed presentation order reflects different date semantics.  In particular,
# three journal series are never added together and are never called documents.
COLUMNS = (
    ('folders_by_creation_year', 'Mapper'),
    ('registrations_by_creation_year', 'Registr.'),
    ('journalposts_by_journal_year', 'JP dato'),
    ('running_journal_by_year', 'JP løp.'),
    ('public_journal_by_year', 'JP off.'),
    ('change_log_events_by_year', 'Endr.logg'),
)


def _values(scope: dict[str, Any]) -> dict[str, dict[int, int | None]]:
    """Normalize recorded annual facts, preserving zero, missing and conflicts."""
    values = {}
    for metric, records in (scope.get('series') or {}).items():
        if metric not in YEAR_METRICS or not isinstance(records, dict):
            continue
        years = {}
        for raw_year, raw_number in records.items():
            try:
                year = int(raw_year)
                if not 1000 <= year <= 9999:
                    continue
                if raw_number is None:
                    number = None
                else:
                    number = int(raw_number)
                    if number < 0:
                        continue
                years[year] = number
            except (TypeError, ValueError):
                continue
        if years:
            values[metric] = years
    return values


def has_period_year_series(scope: dict[str, Any]) -> bool:
    """Does the source hold positive annual production/journal observations?"""
    return any(metric in PERIOD_METRICS and any(n is not None and n > 0 for n in years.values())
               for metric, years in _values(scope).items())


def preferred_source_label(labels: list[str], source_scopes: dict, *,
                           has_dwm_years: bool, review_system_id: str | None = None,
                           part_source_labels: dict[str, str] | None = None) -> str:
    """Pick readable evidence without silently mapping a U2 part to a DWM ID.

    A native archive part should only get its native DWM annual series by
    default. Selecting a KDRS U2 source remains an explicit user action.
    """
    if review_system_id is not None:
        return (part_source_labels or {}).get(review_system_id, 'Samlet uttrekk')
    if has_dwm_years:
        return 'Samlet uttrekk'
    candidates = []
    for label, (run, scope) in source_scopes.items():
        if scope.get('scope_id') != 'whole' or not has_period_year_series(scope):
            continue
        priority = {'standard': 0, 'u01': 1, 'u02': 2}.get(run.get('report_type'), 3)
        candidates.append((priority, labels.index(label) if label in labels else len(labels), label))
    return min(candidates)[2] if candidates else 'Samlet uttrekk'


def _number(value):
    if value is None:
        return 'Konflikt'
    return f'{value:,}'.replace(',', ' ')


def _percentage(value: int, total: int) -> str:
    return f'{value * 100 / total:.2f} %'.replace('.', ',') if total else '–'


def format_year_profile(run: dict, scope: dict) -> list[str]:
    """Full annual matrix plus interpretable endpoints, strictly one KDRS source.

    Every percentage is within ONE date series. Values from different kinds of
    dates, imports or sources are never summed into a synthetic total.
    """
    lines = [
        'KDRS QUERY – ÅRSPROFIL (én kilde om gangen)',
        f"Rapport: {run.get('report_type') or 'ukjent'}  |  Område: {scope.get('label') or 'ukjent'}",
        'Import-ID: ' + str(run.get('import_id') or 'ukjent'),
        'Kilde: ' + ('; '.join(run.get('sources') or []) or 'ikke oppgitt'),
    ]
    values = _values(scope)
    if not values:
        return lines + ['', 'Ingen tolkbare årsserier i denne importen.',
                        'Dette betyr ikke at arkivinnholdet er tomt.']

    lines.extend(['', 'YTTERÅR PER DATOTYPE – antall og andel innen samme serie'])
    for metric, full_label in YEAR_METRICS.items():
        records = values.get(metric)
        if not records:
            continue
        observed = [(y, n) for y, n in records.items() if n is not None and n > 0]
        total = sum(n for n in records.values() if n is not None)
        if not observed:
            lines.append(f'{full_label}: ingen positive entydige årsverdier')
            continue
        first, last = min(y for y, _ in observed), max(y for y, _ in observed)
        endpoints = [first] if first == last else [first, last]
        suffix = ' (IKKE automatisk arkivperiode)' if metric not in PERIOD_METRICS else ''
        lines.append(full_label + suffix)
        for year in endpoints:
            number = records[year]
            lines.append(f'  {year}: {_number(number)} / {_number(total)} kjente totalt '
                         f'({_percentage(number, total)} av denne serien)')
        conflicts = sum(v is None for v in records.values())
        if conflicts:
            lines.append(f'  Obs: {conflicts} årsverdier med motstrid; andeler er kun av kjente verdier')

    # One matrix, with one source per metric. Missing means unknown, not 0.
    active = [(key, short) for key, short in COLUMNS if key in values]
    years = sorted({year for rows in values.values() for year in rows})
    width = max(10, *(len(name) for _, name in active))
    lines += ['', 'HELE ÅRSFORDELINGEN – KDRS (ikke slått sammen med andre importer)',
              'År' + ''.join(f'{label:>{width + 2}}' for _, label in active),
              '-' * (4 + (width + 2) * len(active))]
    period_years = sorted({year for metric, records in values.items()
                           if metric in PERIOD_METRICS
                           for year, number in records.items()
                           if number is not None and number > 0})
    boundaries = set(period_years[:1] + period_years[-1:])
    for year in years:
        year_text = f'{year}' + ('*' if year in boundaries else ' ')
        cells = []
        for metric, _ in active:
            item = values[metric].get(year, 'missing')
            cells.append('–' if item == 'missing' else '!' if item is None else _number(item))
        lines.append(f'{year_text:<5}' + ''.join(f'{text:>{width + 2}}' for text in cells))
    if not period_years:
        lines.append('Ingen sikre positive årsverdier fra produksjons-/journaldatoer.')
    else:
        lines.append(f'* = ytterår i denne kildens produksjons-/journaldatoserier: '
                     f'{period_years[0]}–{period_years[-1]}; krever faglig vurdering.')
    lines += ['– = ikke registrert i denne serien (IKKE null). '
              '0 = observert null. ! = motstridende kildeverdier.',
              'Registreringsdato, journaldato og endringslogg er ulike dateringsgrunnlag.',
              'Ytterårene kan være avvik. Vurder dette mot antall, '
              'andre kilder og metadata; ingen år fjernes automatisk.']
    if scope.get('conflicts'):
        lines += ['', 'KILDEKONFLIKTER:'] + [str(s) for s in scope['conflicts']]
    return lines
