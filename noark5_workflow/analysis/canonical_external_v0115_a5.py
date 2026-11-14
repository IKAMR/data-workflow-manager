"""Strict, non-approval interpretation of selected Siegfried JSON evidence.

Only native Siegfried JSON with recognizable signature and files/matches is
understood. Anything else stays opaque, including unknown Arkade formats.
This deliberately never converts format identification into a passed test.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

MAX_RECORDS = 100000
MAX_MATCHES = 1000000


def inspect_external(path: Path) -> dict[str, Any]:
    """Return a bounded, source-separated analysis; unknown formats stay opaque."""
    if path.suffix.lower() != '.json':
        return {'format': 'unrecognized', 'interpretation': 'not_parsed', 'reason': 'Not a recognized JSON result'}
    try:
        # Bounded by the context adapter before entering this function.
        doc = json.loads(path.read_text(encoding='utf-8-sig'))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        return {'format': 'unrecognized', 'interpretation': 'not_parsed', 'reason': f'Unreadable JSON: {type(exc).__name__}'}
    if not isinstance(doc, dict):
        return {'format': 'unrecognized', 'interpretation': 'not_parsed', 'reason': 'JSON root is not object'}
    # Siegfried's official JSON output has `siegfried` signature metadata,
    # and `files` records with `matches`. No invented statuses.
    signature = doc.get('siegfried')
    files = doc.get('files')
    if not isinstance(signature, str) or not signature.strip() or not isinstance(files, list):
        return {'format': 'unrecognized', 'interpretation': 'not_parsed', 'reason': 'No supported signature'}
    if len(files) > MAX_RECORDS:
        return {'format': 'siegfried_json', 'interpretation': 'not_parsed', 'reason': 'Too many file records'}
    matches_count = 0
    matched_files = 0
    unmatched_files = 0
    identifiers: dict[str, int] = {}
    for file in files:
        if not isinstance(file, dict) or not isinstance(file.get('matches'), list):
            return {'format': 'siegfried_json', 'interpretation': 'not_parsed', 'reason': 'Invalid file/matches structure'}
        matches = file['matches']
        matches_count += len(matches)
        if matches_count > MAX_MATCHES:
            return {'format': 'siegfried_json', 'interpretation': 'not_parsed', 'reason': 'Too many matches'}
        if matches:
            matched_files += 1
        else:
            unmatched_files += 1
        for entry in matches:
            if not isinstance(entry, dict):
                return {'format': 'siegfried_json', 'interpretation': 'not_parsed', 'reason': 'Invalid match entry'}
            namespace = entry.get('ns')
            identifier = entry.get('id')
            if isinstance(namespace, str) and isinstance(identifier, str) and namespace and identifier:
                key = namespace + ':' + identifier
                identifiers[key] = identifiers.get(key, 0) + 1
    return {'format': 'siegfried_json', 'interpretation': 'format_identification_only',
            'file_records': len(files), 'files_with_matches': matched_files,
            'files_without_matches': unmatched_files, 'format_matches': matches_count,
            'identifiers': [{'id': key, 'matches': value} for key, value in sorted(identifiers.items())],
            'technical_test_status': None, 'approval': None,
            'note': 'Formatidentifikasjon, ikke bevis paa filintegritet, Noark-validitet eller depotaksept.'}


def discover_external_candidates(work: str | Path, *, limit: int = 150, max_depth: int = 5) -> list[dict[str, Any]]:
    """Advisory, bounded discovery under known external-result locations.

    No file is selected, loaded wholesale or promoted to a valid result. The
    caller must explicitly pick a file before inspection or association.
    """
    import os
    root = Path(work).resolve()
    from noark5_workflow.analysis.canonical_results import _validate_work
    _validate_work(root)
    found: list[dict[str, Any]] = []
    for dirname in ('external_evidence', 'external_runs', 'arkade5_v2.13.1'):
        parent = root / dirname
        if not parent.is_dir() or parent.is_symlink():
            continue
        for folder, directories, files in os.walk(parent, followlinks=False):
            current = Path(folder)
            depth = len(current.relative_to(parent).parts)
            directories[:] = sorted(n for n in directories if depth < max_depth
                                    and not (current / n).is_symlink())
            for filename in sorted(files):
                candidate = current / filename
                if candidate.is_symlink() or candidate.suffix.lower() not in ('.json', '.xml', '.csv', '.txt'):
                    continue
                resolved = candidate.resolve()
                try:
                    relative = resolved.relative_to(root).as_posix()
                except ValueError:
                    continue
                found.append({'path': relative, 'bytes': resolved.stat().st_size,
                              'status': 'unselected', 'interpretation': 'not_inspected'})
                if len(found) >= limit:
                    return found
    return found
