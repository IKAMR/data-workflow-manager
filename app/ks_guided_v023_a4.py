"""Pure, read-only navigation and evidence projections for linear Noark 5 KS.

The inspection never makes a finding disappear, changes Arkade's technical
result, chooses the reference version for the operator, or approves a delivery.
Only the established append-only save_review API can persist an assessment.
"""
from __future__ import annotations

from typing import Iterable, Mapping

# Exact documented Arkade-test target fields from the existing a1 XML inspector.
# These are *inspection targets*, not claims that KDRS, Arkade or the metadata
# catalogue implement semantically identical controls.
from app.ks_inspector_v023_a1 import _XML_FIELDS


def ordered_findings(findings: Iterable[dict], *, errors_only: bool = True) -> tuple[dict, ...]:
    """Stable source-order navigation: all distinct issue rows, not 177 tests."""
    rows = tuple(findings)
    if errors_only:
        return tuple(r for r in rows if str(r.get('severity') or '').upper() == 'ERROR')
    severity = {'ERROR': 0, 'WARNING': 1, 'REVIEW': 2, 'NOTE': 3, 'INFORMATION': 4}
    return tuple(r for _, r in sorted(enumerate(rows), key=lambda t: (
        severity.get(str(t[1].get('severity') or '').upper(), 5), t[0])))


def find_index(rows: Iterable[dict], finding_key: str) -> int:
    return next((i for i, r in enumerate(rows)
                 if str(r.get('finding_key') or '') == finding_key), -1)


def metadata_for_test(test_id: str, bundle: Mapping | None, version: str) -> dict:
    """Resolve an a1-inspector field against the *actual* versioned registry.

    Never fabricate an M-number, and never confuse a valid value-set code with
    a delivery approval.  The caller supplies its explicit reference version.
    """
    candidate = _XML_FIELDS.get(str(test_id or '').strip(), ())
    xml_field = candidate[0] if candidate else ''
    result = {'xml_field': xml_field, 'object_type': candidate[1] if candidate else '',
              'metadata_id': '', 'standard_values': (), 'value_set_role': '',
              'state': 'not_mapped' if not xml_field else 'registry_unavailable',
              'source_id': '', 'reference_version': version, 'delivery_condition': None}
    if not xml_field or not isinstance(bundle, Mapping):
        return result
    catalogue = (bundle.get('versions') or {}).get(version) or {}
    entries = [r for r in catalogue.get('metadata') or () if r.get('name') == xml_field]
    if len(entries) != 1:
        result['state'] = 'not_registered' if not entries else 'ambiguous'
        return result
    entry = entries[0]
    mid = str(entry.get('metadata_id') or '')
    result.update(metadata_id=mid, state='registered_field_identity',
                  source_id=str(entry.get('source_id') or ''))
    value_id = entry.get('registered_value_set_id')
    values = (catalogue.get('value_sets') or {}).get(value_id) or {}
    if isinstance(values.get('values'), list):
        result['standard_values'] = tuple(str(v) for v in values['values'])
        result['value_set_role'] = str(values.get('value_set_role') or '')
    return result


def inspect_relation(observed_value: str, metadata: Mapping, delivery: Mapping | None) -> dict:
    """Separate code membership from delivery rules and technical test status."""
    standard = tuple(metadata.get('standard_values') or ())
    code = ('registrert' if observed_value in standard else
            'ikke registrert' if standard else 'ikke dokumentert')
    if not delivery or 'delivery_values' not in delivery:
        allowed = 'ikke kildeavklart'
    else:
        allowed = 'ja' if observed_value in delivery['delivery_values'] else 'nei etter registrert avleveringsbetingelse'
    return {'observed': observed_value or '(ikke dokumentert)',
            'registered_code': code, 'delivery_allowed': allowed,
            'technical_result_unchanged': True}


def review_evidence_note(finding: Mapping, *, source_sha256: str,
                         anchor: Mapping | None = None,
                         xml: Mapping | None = None,
                         metadata: Mapping | None = None,
                         delivery: Mapping | None = None) -> str:
    """An explicitly chosen source note, never an automated professional conclusion."""
    lines = [
        'KILDEGRUNNLAG FOR FAGLIG VURDERING (operatørvalgt, ikke vedtak)',
        'Arkade-kontroll: ' + str(finding.get('test_id') or ''),
        'Rapportert feil: ' + str(finding.get('message') or '')[:400],
        'Kildereferanse i Work: ' + str(finding.get('source_ref') or ''),
        'Arkade SHA-256: ' + str(source_sha256 or 'ikke dokumentert'),
    ]
    if anchor:
        lines.extend((
            'Arkivdel: ' + str(anchor.get('archive_part_title') or anchor.get('archive_part_id') or ''),
            'Kilde-XML og linje: ' + str(anchor.get('file') or '') + ':' + str(anchor.get('line') or ''),
        ))
    if xml and xml.get('available'):
        xmeta = xml.get('metadata') or {}
        lines.extend((
            'Objekt systemID: ' + str(xmeta.get('system_id') or '(ikke funnet)'),
            'Observert XML-felt: ' + str(xmeta.get('element') or ''),
            'Observert verdi: ' + str(xmeta.get('xml_value') or ''),
            'Faktisk XPath: ' + str(xmeta.get('xpath') or ''),
        ))
    elif anchor:
        lines.append('XML fra Source er ikke inspisert eller ikke tilgjengelig; Arkade-linjereferanse alene.')
    if metadata and metadata.get('metadata_id'):
        lines.extend((
            'Koblet metadatafelt: ' + str(metadata['metadata_id']) + ' / ' + str(metadata.get('xml_field') or ''),
            'Noark-referanseversjon (ikke automatisk verifisert): ' + str(metadata.get('reference_version') or ''),
        ))
        if xml and xml.get('available'):
            relation = inspect_relation(str((xml.get('metadata') or {}).get('xml_value') or ''), metadata, delivery)
            lines.extend((
                'Registrert standardverdi: ' + relation['registered_code'],
                'Avleveringsbetingelse: ' + relation['delivery_allowed'],
            ))
    lines.append('Faglig årsak og vurdering må begrunnes av saksbehandler; teknisk Arkade-status endres ikke.')
    return '\n'.join(lines)
