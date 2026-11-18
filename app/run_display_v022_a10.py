"""Plain-language labels for A10 GUI; no Noark result counts are inferred."""
from __future__ import annotations

from pathlib import Path


def ready_job_list(jobs) -> tuple:
    """Preserve the immutable joblist order, excluding non-ready jobs."""
    return tuple(job for job in jobs if str(getattr(job, 'status', '')) == 'Klar')


def ready_label(jobs) -> str:
    return f'Kj\u00f8r alle klare ({len(ready_job_list(jobs))})'


def readable_job_name(source_path: str, metadata_label: str = '') -> str:
    """Never rename existing jobs. Caller uses this for newly created jobs only."""
    label = str(metadata_label or '').strip()
    if label:
        return label[:120]
    p = Path(source_path)
    # Noark packages typically use content/sip/content, which is not a name.
    parent = p
    while parent.name.casefold() in {'content', 'sip', 'uttrekk'} and parent != parent.parent:
        parent = parent.parent
    return str(parent.name or p.name or 'Noark 5-uttrekk')[:120]


def result_file_explanation(count: int, warning_count: int | None = None) -> str:
    count = max(0, int(count))
    lines = [f'{count} registrerte resultatfiler. Dette er IKKE antall testfunn eller feil.']
    if warning_count is not None:
        lines.append(f'{max(0, int(warning_count))} tekniske loggadvarsler; '
                     'eksterne kontrollfunn kan ligge i egne rapporter.')
    return '\n'.join(lines)
