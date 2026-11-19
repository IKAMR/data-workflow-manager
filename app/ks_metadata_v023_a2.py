"""v0.2.3-a2: read-only Noark metadata links for already inspected XML objects.

The existing versioned source registries and the advanced-mode XPath/metadata
crosswalk are authoritative.  An XML field-name match is a registered *field
identity*, not proof of a Noark rule or an Arkade/DWM test equivalence.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

VERSIONS = ('3.1', '4.0', '5.0')
MAX_FIELDS = 96
MAX_VALUE = 1000
MAX_LINKS = 12


def load_reference_bundle(project: str | Path | None = None) -> dict[str, Any]:
    """Reuse the exact analysis and registries exposed by Advanced mode.

    This is called in a worker thread, only after a user explicitly requests
    XML inspection.  Never searches Source or Work; never executes XPath tests.
    """
    from app.noark5_xpath_metadata_qa_v021_a4 import build_metadata_qa
    from app.noark5_xpath_version_qa_v021_a3 import _standard_registry
    from app.noark5_xpath_audit_v021_a1 import repo_root

    root = Path(project) if project is not None else repo_root()
    audit = build_metadata_qa(root)
    standard = _standard_registry(root)
    result: dict[str, Any] = {
        'versions': {}, 'source_registry_status': audit.get('source_registry_status', 'unavailable'),
        'source_registry_sha256': audit.get('source_registry_sha256'),
        'value_registry_status': standard.get('status', 'unavailable'),
        'value_registry_sha256': standard.get('sha256'),
        'note': ('Registrert metadata/XPath-kobling er ikke kontrollutfall eller automatisk '
                 'normativ godkjenning. Verdi i et registrert kodeverk kan fremdeles være '
                 'et avleveringsavvik.'),
    }
    for version in VERSIONS:
        data = (audit.get('versions') or {}).get(version) or {}
        values = (standard.get('versions') or {}).get(version) or {}
        result['versions'][version] = {
            'state': str(data.get('state') or 'unavailable'),
            'metadata_registry_status': str(data.get('metadata_registry_status') or 'unavailable'),
            'metadata': list(data.get('metadata') or ())[:10000],
            'value_sets': dict(values.get('value_sets') or {}),
        }
    return result


def _selected_registry(bundle: dict[str, Any], version: str) -> dict[str, Any]:
    if version not in VERSIONS:
        raise ValueError('Ukjent Noark-referanseversjon')
    return (bundle.get('versions') or {}).get(version) or {}


def _matching_entry(entries: list[dict], field_name: str) -> dict | None:
    # Source XML local-name and registry name must agree exactly.  Do not
    # infer an M-number from an Arkade test number or from a similar spelling.
    found = [e for e in entries if e.get('name') == field_name]
    return found[0] if len(found) == 1 else None


def _value_relation(value: str, value_set: dict | None) -> str:
    if not isinstance(value_set, dict) or not isinstance(value_set.get('values'), list):
        return 'Ingen registrert verdioversikt'
    values = value_set['values']
    if value in values:
        opt = value_set.get('optional_values') or []
        return ('Registrert valgfri kodeverdi' if value in opt
                else 'Finnes i registrert verdisett')
    return 'Ikke identisk med registrerte verdier – faglig kontroll nødvendig'


def field_rows(xml_metadata: dict, bundle: dict[str, Any], version: str) -> tuple[dict, ...]:
    """Map genuine direct-child XML values to source-registered M fields only."""
    data = _selected_registry(bundle, version)
    entries = list(data.get('metadata') or ())
    values = data.get('value_sets') or {}
    observed = list(xml_metadata.get('fields') or ())[:MAX_FIELDS]
    result = []
    for field in observed:
        name = str(field.get('field') or '')
        if not name:
            continue
        value = str(field.get('value') or '')[:MAX_VALUE]
        mapped = _matching_entry(entries, name)
        value_id = mapped.get('registered_value_set_id') if mapped else None
        value_set = values.get(value_id) if value_id else None
        result.append({
            'xml_field': name, 'value': value,
            'line': field.get('line'), 'xpath': str(field.get('xpath') or ''),
            'metadata_id': str(mapped.get('metadata_id') or '') if mapped else '',
            'source_location': str(mapped.get('source_location') or '') if mapped else '',
            'mapping_state': str(mapped.get('mapping_state') or '') if mapped else '',
            'verification_status': str(mapped.get('verification_status') or '') if mapped else '',
            'value_set_id': str(value_id or ''),
            'value_relation': (_value_relation(value, value_set) if mapped
                               else 'Ingen dokumentert M-feltkobling i valgt register'),
            'is_selected': name == xml_metadata.get('element'),
        })
    return tuple(result)


def catalogue_ids(bundle: dict, version: str) -> tuple[tuple[str, str], ...]:
    data = _selected_registry(bundle, version)
    return tuple(sorted(((str(e.get('metadata_id') or ''), str(e.get('name') or ''))
                         for e in data.get('metadata') or () if e.get('metadata_id') and e.get('name')),
                        key=lambda r: r[0]))


def field_detail(xml_metadata: dict, bundle: dict, version: str, metadata_id: str,
                 *, rows: tuple[dict, ...] | None = None) -> str:
    """Show source references and *candidate* XPath links without claiming PASS."""
    data = _selected_registry(bundle, version)
    found = [e for e in data.get('metadata') or () if str(e.get('metadata_id')) == metadata_id]
    if len(found) != 1:
        return ('Dette M-feltet er ikke entydig registrert for Noark v' + version + '.\n'
                'Ingen normativ kobling kan utledes fra Arkade-testnummeret.')
    entry = found[0]
    name = str(entry.get('name') or '')
    present = [r for r in (rows if rows is not None else field_rows(xml_metadata, bundle, version))
               if r.get('metadata_id') == metadata_id]
    set_id = str(entry.get('registered_value_set_id') or '')
    value_set = (data.get('value_sets') or {}).get(set_id) if set_id else None
    lines = [
        f'METADATAFELT {metadata_id} · {name}',
        f'Noark v{version} – eksplisitt valgt REFERANSEVERSJON, ikke automatisk påvist fra uttrekket',
        'Kilde: DWMs versjonerte metadatakatalog og standardverdiregister (samme som Avansert modus)',
        f'Registerstatus: {data.get("metadata_registry_status") or "ukjent"}',
        f'Verifiseringsomfang: {entry.get("source_scope") or "ikke dokumentert"}',
        f'Metadata-kilde: {entry.get("source_id") or "ikke oppgitt"}',
        f'Kildested: {entry.get("source_location") or "ikke oppgitt"}',
        f'Verdisett: {set_id or "ikke registrert"}',
        '',
        'OBSERVERTE VERDIER I VALGT XML-OBJEKT',
    ]
    if not present:
        lines.append('Ingen direkte forekomst av dette XML-feltet i det inspiserte objektet.')
    for row in present:
        lines.append(f'- {row["xml_field"]} = {row["value"]} (XML-linje {row.get("line") or "?"})')
        lines.append(f'  {row["value_relation"]}')
        if row.get('xpath'):
            lines.append('  Faktisk XML-XPath: ' + row['xpath'])
    lines.extend(('', 'REGISTRERTE STANDARDVERDIER'))
    if isinstance(value_set, dict) and isinstance(value_set.get('values'), list):
        for value in value_set['values'][:150]:
            lines.append('- ' + str(value))
        lines.append('Koderegisterets rolle: ' + str(value_set.get('value_set_role') or 'ikke oppgitt'))
    else:
        lines.append('Ingen kildebekreftet standardverdiliste tilgjengelig for feltet her.')
    lines.extend(('', 'XPATH- OG KONTROLLKOBLINGER (FRA EKSISTERENDE KDRS/DWM-KATALOG)'))
    candidates = list(entry.get('xpath_candidates') or [])
    explicit = list(entry.get('explicit_value_set_references') or [])
    if not candidates and not explicit:
        lines.append('Ingen dokumentert XPath-kandidat eller eksplisitt verdisettreferanse.')
    for candidate in candidates[:MAX_LINKS]:
        lines.append('Kandidat (ikke attestert semantisk identitet): '
                     + str(candidate.get('test_id') or '?') + ' / KDRS '
                     + str(candidate.get('kdrs_id') or '?'))
        for expr in (candidate.get('metrics') or ())[:3]:
            lines.append('  ' + str(expr.get('xpath') or '')[:1200])
    for link in explicit[:MAX_LINKS]:
        lines.append('Eksplisitt registrert verdisettreferanse (ikke resultat): '
                     + str(link.get('test_id') or '?'))
        for ref in (link.get('references') or ())[:3]:
            lines.append('  Status: ' + str(ref.get('status') or '?') + ' · ' + str(ref.get('check_id') or '?'))
    lines.extend(('', 'FAGLIG FORBEHOLD',
                  'Arkades N5-kontroll, DWMs XPath-katalog og metadatakatalogens M-nummer '
                  'er forskjellige evidenslag. En verdi som finnes i et kodeverk kan likevel '
                  'være uakseptabel i et avleveringsuttrekk; faglig vurdering kreves.',
                  'Denne visningen lagrer ingen ny vurdering og endrer verken XML eller testresultater.'))
    return '\n'.join(lines)


def inspection_note(arkade: dict, xml_result: dict, bundle: dict,
                    version: str) -> str:
    """Operator-selected evidence note; caller must explicitly save KS review.

    Never calls the Work review API itself, and never treats this source
    observation as proof of a normative decision.
    """
    if not xml_result.get('available'):
        raise ValueError('Original XML er ikke tilgjengelig for denne forekomsten')
    meta = xml_result.get('metadata') or {}
    field_name = str(meta.get('element') or '')
    observed = str(meta.get('xml_value') or '')[:500]
    selected = next((r for r in field_rows(meta, bundle, version)
                     if r['xml_field'] == field_name and r['is_selected']), None)
    mid = str(selected.get('metadata_id') or '') if selected else ''
    m_number = (mid + ' ' + field_name) if mid else field_name + ' (M-felt ikke verifisert)'
    return '\n'.join([
        'INSPEKSJON AV KILDEEVIDENS (operatørvalgt)',
        'Arkade-test: ' + str(arkade.get('test_id') or ''),
        'Arkade-funn: ' + str(arkade.get('message') or '')[:400],
        'Arkivdel: ' + str(arkade.get('archive_part_title') or arkade.get('archive_part_id') or ''),
        'Arkivdel systemID: ' + str(arkade.get('archive_part_id') or ''),
        'XML-fil/linje: ' + str(arkade.get('file') or '') + ':' + str(arkade.get('line') or ''),
        'Objekt systemID: ' + str(meta.get('system_id') or 'ikke dokumentert'),
        'Objekt XPath: ' + str(meta.get('xpath') or 'ikke beregnet'),
        'Felt: ' + m_number + ' = ' + observed,
        'Kodeverkstilknytning: ' + (str(selected['value_relation']) if selected else 'ikke dokumentert'),
        'Noark 5 v' + version + ': valgt referanseversjon, IKKE automatisk verifisert uttrekksversjon.',
        'Arkade-kilde i Work: ' + str(arkade.get('source_ref') or ''),
        'Kildeavgrensning: Dette er en observasjon, IKKE faglig konklusjon. '
        'Byteidentitet for gjeldende Source mot Arkades opprinnelige testkilde er ikke attestert.',
    ])
