"""Source-backed, bounded historical comparison of individual XSD field facets.

These *shipped reference XSD* restrictions are not a substitute for validating
against the actual extraction's XSD, and are not the full Noark specification.
"""
from __future__ import annotations
from functools import lru_cache
from pathlib import Path
import json

RULES = Path(__file__).resolve().parents[1] / 'config/noark5/standards/noark5_xsd_field_constraints_v0114_a6.json'
ORDER = ('5.0', '4.0', '3.1')

@lru_cache(maxsize=1)
def _rules():
    return json.loads(RULES.read_text(encoding='utf-8'))


def historical_constraints(metadata_id: str, extraction_version: str | None):
    """Current standard first, historical predecessors newest first; never future versions."""
    obj = _rules()['fields'].get(metadata_id)
    if obj is None:
        return ()
    if extraction_version not in ORDER:
        return ()
    versions = ORDER[ORDER.index(extraction_version):]
    return tuple({'version': ver, 'current': ver == extraction_version,
                  'source': f'noark5/v{ver}/schemas/metadatakatalog.xsd',
                  **obj['versions'][ver]} for ver in versions if ver in obj['versions'])


def describe_constraint(rule: dict, value: str | None = None) -> str:
    restriction = rule['restriction']
    if restriction == 'enumeration':
        allowed = rule['values']
        if value is None:
            return f'XSD enumeration: {len(allowed)} tillatte verdier'
        return ('Opplistet i denne XSD-en' if value in allowed
                else 'Ikke opplistet i denne XSD-en')
    if restriction == 'minLength':
        n = rule['min_length']
        if value is None:
            return f'XSD minLength={n}; ingen enumeration i denne type-definisjonen'
        return (f'Oppfyller minLength={n}; ikke begrenset til en fast verdiliste i denne type-definisjonen'
                if len(value) >= n else f'Oppfyller ikke minLength={n}')
    return 'XSD-type uten enumeration/minLength i denne type-definisjonen; ikke en samlet validering'


def comparison_rows(metadata_id: str, extraction_version: str | None, observed: dict):
    """Describe each version once regardless of duplicated saved test rows."""
    records = []
    for rule in historical_constraints(metadata_id, extraction_version):
        entries = tuple({'value': v, 'count': count, 'explanation': describe_constraint(rule, v)}
                        for v, count in observed.items())
        records.append({**rule, 'description': describe_constraint(rule), 'observations': entries})
    return tuple(records)
