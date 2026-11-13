"""Human-readable extract label for result tables; display only, no identity mutation."""
from __future__ import annotations

import json
import re
from pathlib import Path, PureWindowsPath

GENERIC = {'content', 'sip', 'data', 'extraction', 'uttrekk', 'source', 'unpacked', 'archive'}
EXTRACT_CODE = re.compile(r'(?<![0-9A-Za-z])([0-9]{4}_[0-9]{3,})(?![0-9A-Za-z])')
MAX_JOB_BYTES = 512_000


def _short_label(value: object) -> str:
    raw = str(value or '').strip()
    if not raw or raw.casefold() in GENERIC:
        return ''
    match = EXTRACT_CODE.search(raw)
    if match:
        return match.group(1)
    # LABEL may include an explanatory suffix after an explicit separator.
    for separator in (' | ', ' — ', ' - '):
        if separator in raw:
            return raw.split(separator, 1)[0].strip()
    return raw


def _extract_from_source(path: object) -> str:
    if not path:
        return ''
    raw = str(path).replace('/', '\\')
    for name in reversed(PureWindowsPath(raw).parts):
        match = EXTRACT_CODE.search(name)
        if match:
            return match.group(1)
    return ''


def extract_display_name(job_name: str, report_path: Path | None = None) -> str:
    """Prefer an explicit LABEL; ignore generic `content` names.

    Only reads a bounded job.json located in an ancestor of the existing report;
    never traverses or changes Source. All path comparisons are logical,
    and do not equate Windows alias strings with file identity.
    """
    display_name = _short_label(job_name)
    if display_name:
        return display_name
    if report_path is not None:
        path = Path(report_path)
        for ancestor in path.parents:
            candidate = ancestor / 'job.json'
            if not candidate.is_file():
                continue
            try:
                if candidate.stat().st_size > MAX_JOB_BYTES:
                    break
                obj = json.loads(candidate.read_text(encoding='utf-8'))
                job = obj.get('job', {})
                if not isinstance(job, dict):
                    break
                for key in ('label', 'name'):
                    value = _short_label(job.get(key))
                    if value:
                        return value
                for key in ('source_extraction', 'source_root', 'source_unzipped'):
                    value = _extract_from_source(job.get(key))
                    if value:
                        return value
            except (OSError, ValueError, UnicodeError, TypeError):
                pass
            break
        # The extract container also appears above the Work report in the
        # existing repository layout; no reliance on fixed drive letters.
        value = _extract_from_source(path)
        if value:
            return value
    return str(job_name or '').strip() or 'Ukjent uttrekk'
