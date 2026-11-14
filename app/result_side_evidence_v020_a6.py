"""Bounded, read-only evidence renderer for narrow side-by-side result panels.

This is a display-only projection. Complete unchanged values remain available
from the existing raw text / JSON editor.
"""
from __future__ import annotations

from collections.abc import Mapping
from html import escape
import re
from typing import Any

_LABELS = {
    'import_id': 'Import-ID', 'sha256': 'SHA-256',
    'kilde_sha256': 'Kilde SHA-256', 'source_sha256': 'Kilde SHA-256',
    'has_results': 'Har resultater', 'hasresults': 'Har resultater',
    'number_of_errors': 'Antall feil', 'numberoferrors': 'Antall feil',
    'result_set_tree': 'Resultatstruktur', 'resultset': 'Resultatsett',
    'resultsets': 'Resultatsett', 'source_status': 'Kildestatus',
    'status': 'Status', 'name': 'Navn', 'test': 'Test',
    'title': 'Tittel', 'summary': 'Sammendrag',
    'system_id': 'System-ID', 'job_uid': 'Jobb-UUID',
    'report_path': 'Rapportfil', 'kilde_fil': 'Kildefil',
    'period_evidence': 'Periodeevidens', 'archive_parts': 'Arkivdeler',
    'archive_part': 'Arkivdelmetadata', 'metrics': 'Måledata',
    'counts': 'Antall', 'span': 'Periode', 'observed_last_years': 'Siste observerte år',
}

_TOKENS = re.compile(r'(\s+|[^\s]+)')
_WORD_CHUNK = 22


def _label(value: Any) -> str:
    key = str(value)
    return escape(_LABELS.get(key, key.replace('_', ' ')))


def _value(value: Any, *, max_chars: int = 2500) -> str:
    if value is None or value == '':
        return '<i>Ikke oppgitt</i>'
    if isinstance(value, bool):
        return 'Ja' if value else 'Nei'
    raw = str(value)
    if len(raw) > max_chars:
        raw = raw[:max_chars] + ' ... [avkortet i visning]'
    result: list[str] = []
    for matched in _TOKENS.finditer(raw):
        token = matched.group(0)
        if token.isspace():
            result.append('<br>' if '\n' in token else ' ')
        else:
            pieces = [token[i:i + _WORD_CHUNK] for i in range(0, len(token), _WORD_CHUNK)]
            result.append('&#8203;'.join(escape(piece) for piece in pieces))
    return ''.join(result)


def readable_side_evidence(data: Any, *, max_nodes: int = 1000,
                           max_depth: int = 9) -> str:
    """Render one flowing column, not a fixed-width nested HTML table."""
    remaining = [max(0, min(3000, int(max_nodes)))]
    depth_limit = max(1, min(20, int(max_depth)))
    parts = ['<html><body><h3>Detaljer og evidens</h3>']
    truncated = [False]

    def section(name: str, count: int | None = None) -> None:
        suffix = f' ({count} oppføringer)' if count is not None else ''
        parts.append('<p style="margin-top:10px; margin-bottom:3px; '
                     'border-bottom:1px solid #888;"><b>'
                     + _label(name) + suffix + '</b></p>')

    def walk(value: Any, depth: int) -> None:
        if remaining[0] <= 0 or depth >= depth_limit:
            truncated[0] = True
            return
        remaining[0] -= 1
        if isinstance(value, Mapping):
            if not value:
                parts.append('<p><i>Ingen opplysninger</i></p>')
            for key, item in value.items():
                if remaining[0] <= 0:
                    truncated[0] = True
                    break
                if isinstance(item, Mapping):
                    section(str(key))
                    walk(item, depth + 1)
                elif isinstance(item, (list, tuple)):
                    section(str(key), len(item))
                    walk(item, depth + 1)
                else:
                    parts.append('<p style="margin:3px 0;"><b>' + _label(key)
                                 + ':</b> ' + _value(item) + '</p>')
                    remaining[0] -= 1
        elif isinstance(value, (list, tuple)):
            if not value:
                parts.append('<p><i>Ingen oppføringer</i></p>')
            for idx, item in enumerate(value, 1):
                if remaining[0] <= 0:
                    truncated[0] = True
                    break
                if isinstance(item, (Mapping, list, tuple)):
                    section(f'Oppføring {idx}')
                    walk(item, depth + 1)
                else:
                    parts.append('<p style="margin:3px 0;"><b>' + str(idx)
                                 + ':</b> ' + _value(item) + '</p>')
                    remaining[0] -= 1
        else:
            parts.append('<p>' + _value(value) + '</p>')

    walk(data, 0)
    if truncated[0]:
        parts.append('<p><i>Visningen er forkortet. Velg Råtekst / JSON '
                     'for fullstendig grunnlag.</i></p>')
    parts.append('<p><i>Lesbar visning av lagret evidens. Originaldata er uendret.</i></p>')
    parts.append('</body></html>')
    return ''.join(parts)
