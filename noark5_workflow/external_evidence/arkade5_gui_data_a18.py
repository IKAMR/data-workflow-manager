"""Read-only Arkade 5 and Siegfried/PRONOM snapshot for the results GUI.

Only existing imports are read; no analysis, import, or report regeneration occurs.
"""
from __future__ import annotations

from pathlib import Path

from .arkade5 import list_arkade5_imports, load_arkade5_import
from .arkade5_pronom import load_arkade5_pronom_statistics, summarize_arkade5_pronom_statistics


def build_arkade5_gui_snapshot(work_operations: str | Path) -> dict:
    work = Path(work_operations)
    runs = []
    for manifest in list_arkade5_imports(work):
        import_id = str(manifest.get('import_id') or '')
        if not import_id:
            continue
        try:
            loaded = load_arkade5_import(work, import_id)
            normalized = loaded.get('normalized') or {}
            raw_tests = normalized.get('tests') or []
            tests = []
            for test in raw_tests:
                if not isinstance(test, dict):
                    continue
                tests.append({
                    'test_id': str(test.get('test_id') or ''),
                    'test_name': str(test.get('test_name') or ''),
                    'status': str(test.get('source_status') or 'ukjent'),
                    'errors': test.get('number_of_errors'),
                    'description': str(test.get('test_description') or ''),
                    'details': test,
                })
            pronom_normalized = load_arkade5_pronom_statistics(work, manifest)
            pronom = summarize_arkade5_pronom_statistics(pronom_normalized, manifest=manifest)
            source = normalized.get('source') or {}
            summary = normalized.get('summary') or {}
            original = manifest.get('source') or {}
            runs.append({
                'import_id': import_id,
                'source_version': normalized.get('source_version'),
                'date': summary.get('date_of_testing'),
                'imported_at': manifest.get('imported_at'),
                'source_file': original.get('original_name') or source.get('file'),
                'source_sha256': original.get('sha256') or source.get('sha256'),
                'tests': tests,
                'pronom': pronom,
                'status': 'importert',
            })
        except (OSError, ValueError, TypeError, KeyError) as exc:
            runs.append({
                'import_id': import_id,
                'source_version': None,
                'date': None,
                'imported_at': manifest.get('imported_at'),
                'source_file': (manifest.get('source') or {}).get('original_name'),
                'source_sha256': (manifest.get('source') or {}).get('sha256'),
                'tests': [],
                'pronom': {'available': False},
                'status': 'kan ikke leses',
                'diagnostic': str(exc),
            })
    return {
        'work_operations': str(work),
        'runs': runs,
        'import_count': len(runs),
        'readable_imports': sum(x['status'] == 'importert' for x in runs),
        'pronom_imports': sum(bool((x.get('pronom') or {}).get('available')) for x in runs),
    }
