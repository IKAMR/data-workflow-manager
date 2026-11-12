"""Qt-free formatting for evidence-based live workflow feedback in Basic.

Elapsed time is NOT progress. UI refresh is not proof the external CLI is active.
"""
from __future__ import annotations


def operation_caption(operations, completed: int, total: int) -> str:
    total = max(0, int(total))
    completed = max(0, min(int(completed), total))
    if not total:
        return 'Klargjør kontrollene ...'
    if completed == total:
        return f'{completed} av {total} deljobber fullført.'
    name = ''
    try:
        name = str(getattr(operations[completed], 'name', '') or '').strip()
    except (IndexError, KeyError, TypeError):
        pass
    return (f'Aktiv deljobb {completed + 1} av {total}: {name}' if name
            else f'Aktiv deljobb {completed + 1} av {total}')


def latest_signal_text(last_signal: float | None, now: float) -> str:
    if last_signal is None:
        return 'Ingen kjøremelding mottatt ennå.'
    seconds = max(0, int(now - last_signal))
    if seconds >= 60:
        return (f'Ingen ny kjøremelding på {seconds // 60} min {seconds % 60} sek. '
                'Et eksternt verktøy kan fortsatt arbeide.')
    return f'Siste faktiske kjøremelding for {seconds} sek siden.'


def sanitized_activity_message(message: str, kind: str) -> str:
    """Do not surface raw JSON or potentially sensitive Arkade stdout lines."""
    value = str(message or '').strip()
    if not value:
        return ''
    if kind == 'run.log':
        if value.startswith('[Arkade 5/'):
            return 'Mottar kjørelogg fra Arkade 5.'
        if not value.startswith(('START:', 'OK:', 'FEIL:', 'AVBRUTT',
                                 'ADVARSEL:', '[Siegfried]')):
            return ''
    line = value.splitlines()[0].strip()
    return ''.join(ch for ch in line if ch.isprintable())[:210]


def elapsed_clock(last_signal: float | None, now: float) -> str:
    """Fixed-width elapsed clock; refresh cadence is not evidence of progress."""
    if last_signal is None:
        return '--:--:--'
    total = max(0, int(now - last_signal))
    hours, remaining = divmod(total, 3600)
    minutes, seconds = divmod(remaining, 60)
    return f'{hours:02d}:{minutes:02d}:{seconds:02d}'


def planned_operation_rows(operations, status: str, current_operation: int):
    """Reuse the authoritative JobDetails cursor for each operation's current state.

    Completed steps are based on persisted cursor, not an inferred OK result.
    Exact historical outcomes remain in the independent run log/history.
    """
    rows = []
    current = max(0, int(current_operation or 0))
    for index, operation in enumerate(operations, 1):
        name = str(getattr(operation, 'name', '') or getattr(operation, 'operation_id', '') or '')
        op_id = str(getattr(operation, 'operation_id', '') or '')
        if bool(getattr(operation, 'completed', False)) or index <= current:
            state = 'Fullført'
        elif index == current + 1 and status == 'Kjører':
            state = 'Kjører'
        elif index == current + 1 and status == 'Venter ved kontrollpunkt':
            state = 'Venter'
        elif index == current + 1 and status in ('Feil', 'Hoppet over'):
            state = 'Stoppet'
        else:
            state = 'Ikke startet'
        rows.append((index, name, state, op_id))
    return tuple(rows)
