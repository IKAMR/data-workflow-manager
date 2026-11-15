"""Versioned Noark 5 meaning IDs with lossless observed values (v0.2.1-a6).

Meaning equivalence is NEVER an XSD pass, a specification conformance decision,
or permission for custom metadata values. The source XSD enumeration layer and
QA-approved semantic mapping layer remain strictly separate.

No XML/source files are modified, and nothing is automatically approved.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import date
import json
from pathlib import Path
import re
from typing import Any, Mapping

from app.noark_xsd_variant_qa_v021_a5 import value_candidate

VERSIONS = frozenset({'3.1', '4.0', '5.0'})
REGISTRY_PATH = (Path(__file__).resolve().parents[1] / 'config' / 'noark5' /
                 'standards' / 'noark5_semantic_values_v021_a6.json')
SEMANTIC_STATES = frozenset({
    'exact_historical_xsd_literal', 'owner_confirmed_semantic_example',
    'qa_approved_semantic_equivalence', 'candidate_requires_qa', 'unmapped_needs_qa',
})
MAX_JSON_BYTES = 4_000_000
_ID = re.compile(r'^N5\.M\d{3}\.[0-9]{3,6}$')
_MID = re.compile(r'^M\d{3}$')


def _read_json(path: str | Path) -> Any:
    p = Path(path)
    if p.stat().st_size > MAX_JSON_BYTES:
        raise ValueError('JSON overstiger størrelsegrensen')
    return json.loads(p.read_text(encoding='utf-8'))


def load_registry(path: str | Path | None = None) -> dict[str, Any]:
    """Load an append-only concept catalogue; detect ambiguous literal identities."""
    registry = _read_json(path or REGISTRY_PATH)
    if registry.get('schema_version') != 1:
        raise ValueError('Ukjent format for semantisk register')
    concepts: dict[str, dict] = {}
    reference_keys: dict[tuple[str, str, str], str] = {}
    for item in registry.get('concepts', []):
        concept_id = item.get('concept_id')
        mid = item.get('metadata_id')
        if not isinstance(concept_id, str) or not _ID.fullmatch(concept_id):
            raise ValueError('Ugyldig menings-ID')
        if not _MID.fullmatch(mid or '') or not concept_id.startswith(f'N5.{mid}.'):
            raise ValueError('Menings-ID og metadata-ID stemmer ikke')
        if concept_id in concepts:
            raise ValueError('Duplisert menings-ID')
        kind = item.get('source_type')
        if kind == 'qa_approved_custom_concept':
            qa = item.get('qa') or {}
            if not all(isinstance(qa.get(k), str) and qa[k].strip()
                       for k in ('decision_id', 'approved_by', 'approved_at', 'reason')):
                raise ValueError('Nytt lokalt begrep krever sporbar faglig QA')
            try:
                date.fromisoformat(qa['approved_at'])
            except ValueError as e:
                raise ValueError('Ugyldig dato for nytt begrep') from e
            if any(item.get('exact_xsd_literals', {}).values()):
                raise ValueError('Egendefinert begrep er ikke XSD-kildeliteral')
        elif kind == 'xsd_enumeration_literal':
            if not any(item.get('exact_xsd_literals', {}).values()):
                raise ValueError('XSD-referansebegrep uten XSD-literal')
        else:
            raise ValueError('Ukjent eller udokumentert begrepsopphav')
        concepts[concept_id] = item
        for version, values in item.get('exact_xsd_literals', {}).items():
            if version not in {'3.1', '4.0'} or not isinstance(values, list):
                raise ValueError('Ukjent XSD-enumeration-versjon eller format')
            for value in values:
                if not isinstance(value, str) or not value:
                    raise ValueError('Ugyldig tom referanseverdi')
                key = (version, mid, value)
                if key in reference_keys:
                    raise ValueError('Referanseverdi tilhører flere menings-ID-er')
                reference_keys[key] = concept_id
    if not concepts:
        raise ValueError('Tomt meningsregister')
    xsd = registry.get('xsd_enumerations_by_version', {})
    for version in ('3.1', '4.0', '5.0'):
        if version not in xsd:
            raise ValueError(f'Mangler XSD-referanseversjon {version}')
        for mid, values in xsd[version].items():
            if not _MID.fullmatch(mid) or len(values) != len(set(values)):
                raise ValueError('Ugyldige/dupliserte XSD-verdier')
            if set(values) != {v for ver, m, v in reference_keys if (ver, m) == (version, mid)}:
                raise ValueError(f'Meningsregister og XSD-liste avviker: {version}/{mid}')
    if xsd['5.0']:
        raise ValueError('v5.0-kilder har ikke disse XSD-enumerationene')
    aliases: dict[tuple[str, str], dict] = {}
    for alias in registry.get('aliases', []):
        mid = alias.get('metadata_id')
        raw = alias.get('raw_value')
        concept_id = alias.get('concept_id')
        if not isinstance(raw, str) or not raw or (mid, raw) in aliases:
            raise ValueError('Alias er tomt eller duplisert')
        if concept_id not in concepts or concepts[concept_id]['metadata_id'] != mid:
            raise ValueError('Alias viser til ugyldig menings-ID')
        if alias.get('status') not in ('owner_confirmed_semantic_example', 'proposal_requires_qa'):
            raise ValueError('Alias har ukjent QA-status')
        # If exact literal exists in any version, an alias must not rewrite its meaning.
        for key, val in reference_keys.items():
            if key[1:] == (mid, raw) and val != concept_id:
                raise ValueError('Alias strider mot XSD-kildens entydige meningskobling')
        aliases[(mid, raw)] = alias
    return registry


def _indices(registry: Mapping[str, Any]) -> tuple[dict, dict, dict]:
    by_id = {x['concept_id']: x for x in registry['concepts']}
    literals: dict[tuple[str, str], str] = {}
    for concept in registry['concepts']:
        for vals in concept['exact_xsd_literals'].values():
            for val in vals:
                key = (concept['metadata_id'], val)
                if key in literals and literals[key] != concept['concept_id']:
                    raise ValueError('Motstridende betydning på tvers av XSD-versjoner')
                literals[key] = concept['concept_id']
    aliases = {(x['metadata_id'], x['raw_value']): x for x in registry.get('aliases', [])}
    return by_id, literals, aliases


def load_decisions(path: str | Path | None, registry: Mapping[str, Any]) -> dict[tuple[str, str], dict]:
    """Optional explicit owner QA decisions from Work; never infer from a candidate."""
    if path is None:
        return {}
    obj = _read_json(path)
    if obj.get('format_version') != 1 or not isinstance(obj.get('decisions'), list):
        raise ValueError('Ukjent QA-beslutningsformat')
    by_id, literals, _ = _indices(registry)
    decisions: dict[tuple[str, str], dict] = {}
    for row in obj['decisions']:
        mid, raw = row.get('metadata_id'), row.get('raw_value')
        action, cid = row.get('decision'), row.get('concept_id')
        if not isinstance(raw, str) or not raw or not _MID.fullmatch(mid or ''):
            raise ValueError('QA-beslutning mangler råverdi/metadata-ID')
        if action not in ('approve_semantic_link', 'reject_semantic_link'):
            raise ValueError('Ukjent QA-beslutning')
        if cid not in by_id or by_id[cid]['metadata_id'] != mid:
            raise ValueError('Beslutning peker på ukjent/fremmed menings-ID')
        if not all(isinstance(row.get(key), str) and row[key].strip()
                   for key in ('decision_id', 'approved_by', 'approved_at', 'reason')):
            raise ValueError('Sporbar QA-beslutning krever ID, ansvarlig, dato, begrunnelse')
        try:
            date.fromisoformat(row['approved_at'])
        except ValueError as e:
            raise ValueError('Ugyldig dato i QA-beslutning') from e
        key = (mid, raw)
        if key in decisions:
            raise ValueError('Motstridende/dupliserte QA-beslutninger')
        if key in literals and literals[key] != cid:
            raise ValueError('QA kan ikke omskrive XSD-literals eksisterende menings-ID')
        decisions[key] = row
    return decisions


def _xsd_listing_status(registry: Mapping[str, Any], mid: str, version: str, raw: str) -> str:
    allowed = registry['xsd_enumerations_by_version'][version].get(mid)
    if allowed is not None:
        return 'listed_in_xsd_enumeration' if raw in allowed else 'not_listed_in_xsd_enumeration'
    if version == '5.0':
        if mid in registry.get('v5_min_length_1_verified_for', []):
            return 'v5_min_length_1_empty' if raw == '' else 'v5_min_length_1_nonempty_not_full_validation'
        return 'no_fixed_xsd_enumeration_not_full_validation'
    return 'xsd_field_not_catalogued'


def resolve_value(metadata_id: str, version: str, raw: str, *,
                  registry: Mapping[str, Any] | None = None,
                  decisions: Mapping[tuple[str, str], dict] | None = None) -> dict[str, Any]:
    """Resolve one literal without normalizing or changing its raw text.

    A confirmed *meaning* never changes original-schema enumeration status.
    """
    if version not in VERSIONS or not _MID.fullmatch(metadata_id):
        raise ValueError('Velg gyldig Noark-versjon og metadata-ID')
    if not isinstance(raw, str):
        raise TypeError('Råverdi må være tekst')
    reg = registry if registry is not None else load_registry()
    by_id, literals, aliases = _indices(reg)
    qa = (decisions or {}).get((metadata_id, raw))
    concept_id = literals.get((metadata_id, raw))
    candidate_id = None
    reason = None
    if concept_id is not None:
        state = 'exact_historical_xsd_literal'
        if qa and qa['decision'] == 'reject_semantic_link':
            # Cannot revoke reference literal identity by local QA; this would
            # contradict the source text and must be raised separately.
            raise ValueError('Kan ikke avvise eksakt XSD-referanseverdi som konsept')
    elif qa:
        if qa['decision'] == 'approve_semantic_link':
            concept_id = qa['concept_id']
            state = 'qa_approved_semantic_equivalence'
        else:
            state = 'unmapped_needs_qa'
            reason = 'rejected_by_explicit_qa'
    else:
        alias = aliases.get((metadata_id, raw))
        if alias and alias['status'] == 'owner_confirmed_semantic_example':
            concept_id = alias['concept_id']
            state = 'owner_confirmed_semantic_example'
        elif alias:
            candidate_id = alias['concept_id']
            state = 'candidate_requires_qa'
            reason = alias['variant_type']
        else:
            field_lits = [x['preferred_label'] for x in reg['concepts']
                          if x['metadata_id'] == metadata_id]
            suggestion = value_candidate(raw, field_lits)
            match = suggestion.get('candidate')
            if match is not None:
                candidate_id = literals.get((metadata_id, match))
                if candidate_id is not None:
                    state = 'candidate_requires_qa'
                    reason = suggestion['status']
                else:
                    state = 'unmapped_needs_qa'
            else:
                state = 'unmapped_needs_qa'
    return {
        'metadata_id': metadata_id,
        'noark_version': version,
        'observed_raw': raw,
        'meaning_id': concept_id,
        'meaning_label': by_id[concept_id]['preferred_label'] if concept_id else None,
        'semantic_state': state,
        'candidate_meaning_id': candidate_id,
        'candidate_reason': reason,
        'xsd_listing_status': _xsd_listing_status(reg, metadata_id, version, raw),
        'normative_conformance': 'not_assessed',
        'full_xsd_validation': 'not_performed',
        'raw_value_modified': False,
        'qa_decision_id': qa['decision_id'] if qa else None,
    }


def analyze_observations(metadata_id: str, version: str, counts: Mapping[str, int], *,
                         registry: Mapping[str, Any] | None = None,
                         decisions: Mapping[tuple[str, str], dict] | None = None) -> dict[str, Any]:
    """Distinct raw literals and distinct confirmed meaning IDs remain separate."""
    reg = registry if registry is not None else load_registry()
    if metadata_id not in reg['historical_xsd_type_names_3_1_4_0']:
        raise ValueError('Metadata-ID mangler i registrert XSD-verdiinventar')
    rows = []
    concept_counts: Counter[str] = Counter()
    concept_variants: dict[str, list[str]] = defaultdict(list)
    unknown_total = 0
    candidate_total = 0
    for raw, count in sorted(counts.items()):
        if not isinstance(raw, str) or isinstance(count, bool) or not isinstance(count, int) or count < 0:
            raise ValueError('Råverdier må være tekst med ikke-negative heltall')
        row = resolve_value(metadata_id, version, raw, registry=reg, decisions=decisions)
        row['occurrences'] = count
        rows.append(row)
        if row['meaning_id'] is not None:
            concept_counts[row['meaning_id']] += count
            concept_variants[row['meaning_id']].append(raw)
        elif row['candidate_meaning_id'] is not None:
            candidate_total += count
        else:
            unknown_total += count
    concepts = {x['concept_id']: x for x in reg['concepts']}
    return {
        'analysis_type': 'literal_and_semantic_counts_not_normative_validation',
        'metadata_id': metadata_id, 'noark_version': version,
        'total_occurrences': sum(counts.values()),
        'distinct_raw_values': len(rows),
        'distinct_assigned_meaning_ids': len(concept_counts),
        'unassigned_occurrences': unknown_total,
        'qa_candidate_occurrences': candidate_total,
        'rows': rows,
        'meanings': [{
            'meaning_id': mid,
            'label': concepts[mid]['preferred_label'],
            'occurrences': n,
            'raw_variants': sorted(concept_variants[mid]),
        } for mid, n in sorted(concept_counts.items())],
        'normative_conformance': 'not_assessed',
        'source_preserved': True,
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--metadata', required=True, choices=sorted({x['metadata_id'] for x in load_registry()['concepts']}))
    p.add_argument('--noark-version', required=True, choices=sorted(VERSIONS))
    p.add_argument('--counts-json', type=Path, required=True,
                   help='JSON-objekt {"rå tekst": antall}; ingen original XML åpnes')
    p.add_argument('--decisions-json', type=Path,
                   help='Eksplisitt QA-beslutningsfil, ikke automatisk læring')
    p.add_argument('--registry', type=Path, default=REGISTRY_PATH)
    args = p.parse_args(argv)
    reg = load_registry(args.registry)
    counts = _read_json(args.counts_json)
    if not isinstance(counts, dict):
        p.error('counts-json må inneholde JSON-objekt fra råverdi til antall')
    decisions = load_decisions(args.decisions_json, reg)
    print(json.dumps(analyze_observations(args.metadata, args.noark_version, counts,
                                          registry=reg, decisions=decisions),
                     ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
