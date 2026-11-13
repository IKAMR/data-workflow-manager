"""Conservative Work source discovery and read-only reporting for canonical v1.

Discovery is advisory: historical runs are never silently merged. A caller must
explicitly select sources before canonical_results.build_canonical_results writes.
"""
from __future__ import annotations

import argparse
from collections import Counter
import json
import os
from pathlib import Path
from typing import Any

MAX_CANDIDATES = 1000
MAX_DEPTH = 12


class WorkAdapterError(ValueError):
    pass


def _within(work: Path, candidate: Path) -> Path:
    root = work.resolve()
    resolved = candidate.resolve()
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise WorkAdapterError(f'Fil utenfor valgt Work: {candidate}') from exc
    return resolved


def _read_json(path: Path) -> dict[str, Any]:
    if path.stat().st_size > 100_000_000:
        raise WorkAdapterError(f'For stor fil: {path}')
    try:
        value = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise WorkAdapterError(f'Ugyldig JSON: {path}: {exc}') from exc
    if not isinstance(value, dict):
        raise WorkAdapterError(f'JSON-objekt forventet: {path}')
    return value


def discover_work_sources(work: str | Path) -> dict[str, Any]:
    """List candidates only in selected Work; don't interpret absent as zero.

    Symlinked folders are ignored, and all candidates are bounded to Work.
    Only known filenames are considered, with no guesses about result contents.
    """
    work = Path(work).resolve()
    if not (work / 'job.json').is_file():
        raise WorkAdapterError('Valgt Work mangler job.json')
    # Validate identity using the exact same boundary contract as the builder.
    from noark5_workflow.analysis.canonical_results import _validate_work
    _validate_work(work)
    categories: dict[str, list[dict[str, Any]]] = {'master': [], 'raw': [], 'external_bank': []}
    search_roots = [('master', work / 'noark5_tests', 'master-results.json'),
                    ('raw', work / 'wf', 'raw-results.jsonl'),
                    ('external_bank', work / 'external_evidence', 'result-bank.json'),
                    ('external_bank', work / 'external_runs', 'result-bank.json'),
                    ('external_bank', work / 'wf', 'result-bank.json')]
    seen: set[str] = set()
    for category, root, filename in search_roots:
        if not root.is_dir() or root.is_symlink():
            continue
        for folder, directories, files in os.walk(root, followlinks=False):
            base = Path(folder)
            depth = len(base.relative_to(root).parts)
            directories[:] = [name for name in directories
                              if depth < MAX_DEPTH and not (base / name).is_symlink()]
            if filename not in files:
                continue
            path = base / filename
            if path.is_symlink() or not path.is_file():
                continue
            resolved = _within(work, path)
            relative = resolved.relative_to(work).as_posix()
            if relative in seen or len(resolved.relative_to(root).parts) > MAX_DEPTH:
                continue
            seen.add(relative)
            if len(seen) > MAX_CANDIDATES:
                raise WorkAdapterError('For mange kandidatfiler; velg kilder manuelt')
            candidate: dict[str, Any] = {'path': relative, 'bytes': resolved.stat().st_size,
                                          'selected': False, 'status': 'candidate'}
            if category == 'master':
                try:
                    data = _read_json(resolved)
                    source = data.get('source') or {}
                    if (data.get('format_version') == 1 and isinstance(source, dict)
                            and source.get('execution_profile') == 'normal'
                            and isinstance(data.get('tests'), list)):
                        candidate['status'] = 'normal_master'
                        candidate['tests'] = len(data['tests'])
                    else:
                        candidate['status'] = 'unsupported_or_historical'
                except (WorkAdapterError, OSError):
                    candidate['status'] = 'unreadable'
            elif category == 'external_bank':
                try:
                    data = _read_json(resolved)
                    candidate['status'] = ('bank_v2' if data.get('format_version') == 2
                                           and isinstance(data.get('resources'), list)
                                           else 'unsupported_format')
                except (WorkAdapterError, OSError):
                    candidate['status'] = 'unreadable'
            categories[category].append(candidate)
    for items in categories.values():
        items.sort(key=lambda x: x['path'].casefold())
    return {'work': str(work), 'candidates': categories,
            'selection_required': True,
            'note': 'Discovery does not select or merge runs; select sources explicitly.'}


def canonical_report(canonical: dict[str, Any]) -> dict[str, Any]:
    """Present a source-separated, non-aggregated index for future reports."""
    if canonical.get('model_id') != 'noark5.canonical-results.v1':
        raise WorkAdapterError('Ukjent kanonisk resultatmodell')
    observations = canonical.get('observations')
    if not isinstance(observations, list):
        raise WorkAdapterError('Mangler observasjoner')
    by_source: dict[str, Counter] = {}
    for item in observations:
        if not isinstance(item, dict):
            raise WorkAdapterError('Ugyldig observasjon')
        kind = str(item.get('source_kind') or 'unknown')
        by_source.setdefault(kind, Counter())[str(item.get('availability') or 'unknown')] += 1
    rows = [{'source_kind': kind, 'observations': sum(c.values()),
             'available': c['available'], 'unavailable': c['unavailable'],
             'unknown': c['unknown']}
            for kind, c in sorted(by_source.items())]
    return {'report_model': 'noark5.canonical-coverage.v1',
            'extraction_stable_id': canonical.get('extraction', {}).get('stable_id'),
            'source_coverage': rows, 'observations': len(observations),
            'totals_aggregated': False, 'technical_approval': None,
            'note': 'Dekningsoversikt, ikke depotgodkjenning eller summering av arkivdata.'}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description='Undersok Work-kilder og kanonisk dekning')
    parser.add_argument('--work', type=Path, required=True)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--discover', action='store_true')
    group.add_argument('--report', action='store_true')
    args = parser.parse_args(argv)
    try:
        if args.discover:
            output = discover_work_sources(args.work)
        else:
            path = _within(args.work, args.work / 'noark5_evidence' / 'canonical-results.json')
            output = canonical_report(_read_json(path))
    except (WorkAdapterError, OSError, ValueError) as exc:
        parser.exit(2, f'FEIL: {exc}\n')
    print(json.dumps(output, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
