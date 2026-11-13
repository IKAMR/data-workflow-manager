"""Strict, Qt-independent source selection contract for canonical Work snapshots."""
from __future__ import annotations

ALLOWED = {'master': {'normal_master'}, 'raw': {'candidate'},
           'external_bank': {'bank_v2'}}


def selected_sources(rows: list[tuple[str, str, bool, str]]) -> dict:
    """Only sources explicitly checked by the operator may become inputs."""
    selection = {'master_paths': [], 'raw_results_path': None,
                 'external_bank_path': None}
    seen = set()
    for category, path, checked, status in rows:
        if not checked:
            continue
        if not path or not isinstance(path, str) or path in seen:
            raise ValueError('Ugyldig eller duplisert resultatkilde')
        seen.add(path)
        if status not in ALLOWED.get(category, set()):
            raise ValueError(f'Kilden kan ikke brukes: {path} ({status})')
        if category == 'master':
            selection['master_paths'].append(path)
        elif category == 'raw':
            if selection['raw_results_path'] is not None:
                raise ValueError('Velg bare en raaresultatlogg om gangen')
            selection['raw_results_path'] = path
        elif category == 'external_bank':
            if selection['external_bank_path'] is not None:
                raise ValueError('Velg bare en ekstern resultatbank om gangen')
            selection['external_bank_path'] = path
    if not (selection['master_paths'] or selection['raw_results_path'] or
            selection['external_bank_path']):
        raise ValueError('Velg minst en resultatkilde')
    selection['master_paths'] = tuple(selection['master_paths'])
    return selection
