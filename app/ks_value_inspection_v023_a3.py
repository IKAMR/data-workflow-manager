"""v0.2.3-a3: read-only, source-scoped value census and period reconciliation.

A registered standard-value set, the actual XML values and the Arkade 5
assessment are three DIFFERENT claims.  Never infer normative approval or
alter job/Source/Work. The Work report is identified by the SHA-bound KS snapshot.
"""
from __future__ import annotations

from collections import Counter
from datetime import date
from hashlib import sha256
from functools import lru_cache
import json
import re
from pathlib import Path
from typing import Any, Callable

from app.ks_inspector_v023_a1 import resolve_source_xml
from app.ks_workshop_v022_a12 import WorkshopError, _load_json, work_file

# Reads are on demand in a worker, never during the initial KS form load.
MAX_SOURCE_BYTES = 8 * 1024**3
MAX_XML_EVENTS = 35_000_000
MAX_UNIQUE_VALUES = 4000
MAX_VALUE_CHARS = 2000
MAX_METADATA_BYTES = 2 * 1024 * 1024
MAX_RULE_BYTES = 12_000
_XML_NAMES = re.compile(r'^[A-Za-z_][A-Za-z0-9_.-]*$')
_YEAR_PAIR = re.compile(r'(?<!\d)((?:19|20)\d{2})\s*[-–]\s*((?:19|20)\d{2})(?!\d)')


def _local(tag: str) -> str:
    return tag.rsplit('}', 1)[-1]


def _stop(cancel: Callable[[], bool] | None) -> None:
    if cancel is not None and cancel():
        raise WorkshopError('Lesing av XML-verdier avbrutt av bruker')


def registered_field(bundle: dict, version: str, metadata_id: str) -> dict:
    """Exact M-ID and registered name from selected version; no guessed mappings."""
    data = (bundle.get('versions') or {}).get(version) or {}
    matches = [m for m in data.get('metadata') or [] if m.get('metadata_id') == metadata_id]
    if len(matches) != 1:
        raise WorkshopError('M-feltet er ikke entydig registrert for valgt Noark-referanseversjon')
    record = matches[0]
    field = record.get('name')
    if not isinstance(field, str) or not _XML_NAMES.fullmatch(field):
        raise WorkshopError('M-feltet har ikke et entydig XML-feltnavn')
    value_set_id = record.get('registered_value_set_id')
    value_set = (data.get('value_sets') or {}).get(value_set_id) if value_set_id else None
    allowed = tuple(str(v) for v in value_set.get('values', [])) if isinstance(value_set, dict) and isinstance(value_set.get('values'), list) else ()
    return {'metadata_id': metadata_id, 'xml_field': field, 'value_set_id': value_set_id or '',
            'allowed': allowed, 'has_value_set': bool(value_set is not None and isinstance(value_set.get('values'), list)),
            'source_id': str(record.get('source_id') or ''),
            'source_location': str(record.get('source_location') or ''),
            'value_set_role': str(value_set.get('value_set_role') or '') if isinstance(value_set, dict) else '',
            'version': version}




@lru_cache(maxsize=1)
def _delivery_catalogue() -> dict:
    """Source-linked Noark 5.0 delivery condition, NOT a validator.

    Only registered status fields with a checked, exact-source comment are
    listed. All other versions/fields remain unclassified, never silently
    assumed acceptable. The Noark metadata and value-set registry is still
    authoritative for field identity and standard values.
    """
    p = Path(__file__).resolve().parents[1] / 'config/noark5/standards/delivery_value_conditions_v023_a3.json'
    if p.stat().st_size > MAX_RULE_BYTES:
        raise WorkshopError('Avleveringsbetingelser overstiger tillatt registerstørrelse')
    data = json.loads(p.read_text(encoding='utf-8'))
    if (data.get('format_version') != 1 or data.get('reference_version') != '5.0'
            or data.get('model') != 'dwm.noark5.delivery-value-commentary.v1'):
        raise WorkshopError('Avleveringsbetingelsene har ugyldig kildeversjon')
    return data


def delivery_condition(bundle: dict, version: str, metadata_id: str) -> dict | None:
    """Only present a documented rule where ID, XML-name and values agree."""
    if version != '5.0':
        return None
    field = registered_field(bundle, version, metadata_id)
    rule_doc = _delivery_catalogue()
    matches = [r for r in rule_doc.get('rules') or [] if r.get('metadata_id') == metadata_id]
    if not matches:
        return None
    if len(matches) != 1:
        raise WorkshopError('Flere konkurrerende avleveringsbetingelser for samme M-felt')
    rule = matches[0]
    accepted = rule.get('delivery_values')
    if (rule.get('xml_field') != field['xml_field'] or not field['has_value_set']
            or not isinstance(accepted, list) or not accepted
            or not set(accepted).issubset(set(field['allowed']))):
        raise WorkshopError('Avleveringsbetingelse kan ikke knyttes sikkert til registrert M-verdisett')
    src = rule_doc['source']
    return {'metadata_id': metadata_id, 'xml_field': field['xml_field'],
            'version': '5.0', 'delivery_values': tuple(accepted),
            'page': rule.get('page'), 'applies_to': rule.get('applies_to') or '',
            'source_title': src.get('title') or '', 'source_url': src.get('url') or '',
            'publisher': src.get('publisher') or '', 'source_date': src.get('document_date') or ''}


def delivery_relation(value: str, condition: dict | None) -> str:
    if not condition:
        return 'Ingen dokumentert avleveringsbetingelse for valgt M-felt og versjon'
    return ('Angitt som tillatt ved avlevering (Noark 5.0)' if value in condition['delivery_values']
            else 'IKKE angitt som tillatt ved avlevering (Noark 5.0)')


def count_actual_xml_values(work: str | Path, bundle: dict, version: str, metadata_id: str,
                            *, archive_part_id: str = '',
                            cancel: Callable[[], bool] | None = None) -> dict:
    """Count observed field values in the ACTUAL, complete current Source XML.

    The parser is streaming and only retains count dictionaries, not archive
    objects.  Failed/incomplete parses raise; never return partial totals as
    completed results.  Archive part counts use actual XML systemID linkage,
    not Arkade's textual title. No filesystem writes or test execution.
    """
    field = registered_field(bundle, version, metadata_id)
    condition = delivery_condition(bundle, version, metadata_id)
    source = resolve_source_xml(work, 'arkivstruktur.xml')
    if source is None:
        raise WorkshopError('Original arkivstruktur.xml er ikke tilgjengelig i jobbens registrerte Source')
    try:
        source = source.resolve(strict=True)
        stat_before = source.stat()
    except OSError as exc:
        raise WorkshopError('Registrert Source-XML er ikke lenger tilgjengelig') from exc
    if stat_before.st_size > MAX_SOURCE_BYTES:
        raise WorkshopError('XML er større enn trygg skannegrense; ingen ufullstendige verdier presenteres')
    from lxml import etree
    counts: Counter[str] = Counter()
    scoped: Counter[str] = Counter()
    unresolved_part = 0
    events = 0
    scanned = 0
    frames: list[dict[str, Any]] = []
    # Each direct field is counted once; the parent is included to distinguish
    # status fields from unrelated nested elements with the same local name.
    parent_rules = {'saksstatus': {'mappe'}, 'journalstatus': {'registrering'},
                    'dokumentstatus': {'dokumentbeskrivelse'}}
    expected_parents = parent_rules.get(field['xml_field'])
    _stop(cancel)
    with source.open('rb') as stream:
        ctx = etree.iterparse(stream, events=('start', 'end'), resolve_entities=False,
                              no_network=True, load_dtd=False, huge_tree=False)
        try:
            for event, element in ctx:
                events += 1
                if events % 4096 == 0:
                    _stop(cancel)
                    if events > MAX_XML_EVENTS:
                        raise WorkshopError('XML overgår trygg grense for antall elementer')
                if not isinstance(element.tag, str):
                    continue
                tag = _local(element.tag)
                if event == 'start':
                    frames.append({'tag': tag, 'part_id': ''})
                    continue
                if not frames:
                    continue
                if tag == 'systemID' and len(frames) > 1 and frames[-2]['tag'] == 'arkivdel':
                    frames[-2]['part_id'] = (element.text or '').strip()
                parent = frames[-2]['tag'] if len(frames) > 1 else ''
                if tag == field['xml_field'] and len(element) == 0 and (
                    expected_parents is None or parent in expected_parents):
                    value = (element.text or '').strip()
                    if len(value) > MAX_VALUE_CHARS:
                        raise WorkshopError('En XML-feltverdi overstiger trygg tekstgrense')
                    if value not in counts and len(counts) >= MAX_UNIQUE_VALUES:
                        raise WorkshopError('For mange ulike feltverdier; ingen ufullstendige tall rapporteres')
                    counts[value] += 1
                    scanned += 1
                    part = next((x for x in reversed(frames[:-1]) if x['tag'] == 'arkivdel'), None)
                    part_id = part['part_id'] if part else ''
                    if archive_part_id:
                        if part_id == archive_part_id:
                            scoped[value] += 1
                        elif not part_id:
                            unresolved_part += 1
                frames.pop()
                element.clear()
                while element.getprevious() is not None:
                    del element.getparent()[0]
        except etree.XMLSyntaxError as exc:
            raise WorkshopError('XML kan ikke telles fullstendig: ' + str(exc)) from exc
        finally:
            del ctx
    _stop(cancel)
    stat_after = source.stat()
    if (stat_before.st_size, stat_before.st_mtime_ns) != (stat_after.st_size, stat_after.st_mtime_ns):
        raise WorkshopError('Kilde-XML ble endret under opptellingen; resultatet forkastes')
    known = set(field['allowed'])
    # Registered values including zero counts first; genuinely observed values
    # absent from the reference set are still shown and never hidden.
    if field['has_value_set']:
        ordered = list(field['allowed']) + sorted(set(counts) - known, key=str.casefold)
    else:
        ordered = sorted(counts, key=lambda x: (-counts[x], x.casefold()))
    values = []
    for value in ordered:
        relation = ('Registrert standardverdi' if value in known
                    else 'Ikke i registrert verdisett' if field['has_value_set']
                    else 'Intet registrert verdisett – ikke klassifisert')
        values.append({'value': value, 'total': counts[value],
                       'archive_part': scoped[value] if archive_part_id else None,
                       'reference_relation': relation,
                       'delivery_relation': delivery_relation(value, condition)})
    return {
        'version': version, 'metadata_id': metadata_id, 'xml_field': field['xml_field'],
        'source_path': str(source), 'source_size': stat_before.st_size,
        'source_mtime_ns': stat_before.st_mtime_ns, 'events_read': events,
        'complete': True, 'scope': 'hele Source-XML-filen',
        'archive_part_id': archive_part_id,
        'archive_part_unresolved_occurrences': unresolved_part,
        'observed_total': scanned, 'observed_distinct': len(counts),
        'inside_registered_set': sum(n for v, n in counts.items() if v in known) if field['has_value_set'] else None,
        'outside_registered_set': sum(n for v, n in counts.items() if v not in known) if field['has_value_set'] else None,
        'values': tuple(values), 'reference': field,
        'delivery_condition': condition,
        'eligible_at_delivery': sum(n for v, n in counts.items() if v in condition['delivery_values']) if condition else None,
        'not_eligible_at_delivery': sum(n for v, n in counts.items() if v not in condition['delivery_values']) if condition else None,
        'provenance_note': (
            'Faktisk verdiopptelling fra nåværende Source, ikke en ny Arkade-test. '
            'Antall er feltforekomster, ikke nødvendigvis unike arkivobjekter. '
            'Registrert kodeverdi betyr ikke godkjent for avlevering. '
            'Kilden er ikke dokumentert byte-identisk med Arkades opprinnelige testfil.'),
    }


def _assert_hash_bound_report(work: str | Path, snapshot: dict) -> tuple[dict, str]:
    matches = [row for row in snapshot.get('evidence_manifest') or ()
               if isinstance(row, dict) and row.get('kind') == 'dwm_depot']
    if len(matches) != 1:
        raise WorkshopError('Finner ikke entydig depotrapport i KS-evidensmanifestet')
    row = matches[0]
    relative = str(row.get('path') or '')
    path = work_file(work, relative)
    if sha256(path.read_bytes()).hexdigest() != row.get('sha256'):
        raise WorkshopError('Depotrapportens SHA-256 stemmer ikke med KS-grunnlaget')
    return _load_json(work, relative), relative


def load_period_evidence(work: str | Path, snapshot: dict) -> dict:
    """Use only Work-bound, preserved sources. Never treat job label as fact."""
    root = Path(work)
    job = _load_json(root, 'job.json', max_bytes=MAX_METADATA_BYTES)
    uid = str(job.get('job_uid') or '')
    if uid != str((snapshot.get('work_identity') or {}).get('job_uid') or ''):
        raise WorkshopError('KS-jobb og Work-jobb har ulik identitet')
    report, report_ref = _assert_hash_bound_report(root, snapshot)
    metadata = _load_json(root, 'metadata/depot_metadata.json', max_bytes=MAX_METADATA_BYTES) if (
        root / 'metadata/depot_metadata.json').is_file() else {}
    if metadata and str(metadata.get('job_id') or '') != str((job.get('job') or {}).get('job_id') or ''):
        raise WorkshopError('Ytre depotmetadata viser til en annen jobb')
    imports = [x for x in metadata.get('source_imports') or []
               if isinstance(x, dict) and x.get('kind') == 'dias-mets']
    if len(imports) > 1:
        # Select no arbitrary import when multiple prior versions exist.
        imports = []
    first = imports[0] if imports else {}
    info = first.get('fields') if isinstance(first.get('fields'), dict) else {}
    info = info or {}
    info_ref = str(first.get('preserved_file') or '')
    if info_ref:
        try:
            preserved = work_file(root, info_ref)
            if sha256(preserved.read_bytes()).hexdigest() != first.get('sha256'):
                raise WorkshopError('Bevart info.xml avviker fra registrert SHA-256')
        except (OSError, WorkshopError) as exc:
            raise WorkshopError('Kildeintegritet for ytre info.xml: ' + str(exc)) from exc
    period = (report.get('period_reconciliation') or {}).get('declared_period') or {}
    if period.get('source') != 'arkivuttrekk.xml':
        period = {}
    name = str((job.get('job') or {}).get('name') or '')
    label = str(info.get('label') or info.get('archive_description') or name)
    found = _YEAR_PAIR.search(label)
    label_start, label_end = (found.group(1), found.group(2)) if found else ('', '')
    parts = []
    for entry in report.get('archive_parts') or ():
        obj = entry.get('archive_part') if isinstance(entry, dict) else None
        if not isinstance(obj, dict):
            continue
        parts.append({'id': str(obj.get('system_id') or ''), 'title': str(obj.get('title') or ''),
                      'start': str(obj.get('archive_period_start_date') or ''),
                      'end': str(obj.get('archive_period_end_date') or ''),
                      'status': str(obj.get('status') or '')})
    observed = (report.get('period_reconciliation') or {}).get('observed_series') or {}
    series = {}
    for key in ('folder_created', 'registration_created', 'journal_date',
                'document_description_created'):
        vals = observed.get(key) or {}
        span = vals.get('span') or {}
        series[key] = {'first_year': str(span.get('first_year') or ''),
                       'last_year': str(span.get('last_year') or ''),
                       'count_last_year': (vals.get('counts') or {}).get(str(span.get('last_year') or ''), 0)}
    return {
        'job_name': name, 'label': label, 'label_start': label_start,
        'label_end': label_end, 'outer_start': str(info.get('period_start') or ''),
        'outer_end': str(info.get('period_end') or ''),
        'outer_source': info_ref, 'inner_start': str(period.get('start_date') or ''),
        'inner_end': str(period.get('end_date') or ''),
        'inner_source': report_ref + ' / period_reconciliation.declared_period',
        'archive_parts': parts, 'observed_series': series,
        'source_note': ('Tre separate opplysninger: LABEL er beskrivelse, info.xml er ytre '
                        'METS-periode, arkivuttrekk.xml er indre uttrekksmetadata. '
                        'Motstrid krever faglig avklaring; ingen felt korrigeres automatisk.'),
    }


def _year(date_text: str) -> int | None:
    text = str(date_text or '').strip()
    if not re.match(r'^\d{4}(-\d{2}(-\d{2})?)?$', text):
        return None
    try:
        if len(text) == 10:
            date.fromisoformat(text)
    except ValueError:
        return None
    return int(text[:4])


def period_review_text(period: dict, metadata: dict, *, archive_part_id: str = '') -> str:
    """Readable, precise period comparison for the selected object, not a new test."""
    if not period:
        return 'PERIODEGRUNNLAG: Ikke tilgjengelig for denne Work-jobben.'
    fields = {str(f.get('field') or ''): str(f.get('value') or '')
              for f in metadata.get('fields') or () if isinstance(f, dict)}
    # Show the actual object's documented dates rather than infer from metadata label.
    date_keys = ('saksdato', 'opprettetDato', 'journalDato', 'dokumentDato',
                 'avsluttetDato', 'saksaar')
    observed = [(k, fields[k]) for k in date_keys if fields.get(k)]
    part = next((p for p in period.get('archive_parts') or ()
                 if archive_part_id and p['id'] == archive_part_id), None)
    lines = [
        'PERIODEKILDER – IKKE EN AUTOMATISK FEILDOM',
        'Jobb/LABEL (beskrivelse): ' + str(period.get('label') or '(mangler)'),
        '  År i LABEL: ' + (str(period.get('label_start')) + '–' + str(period.get('label_end'))
                              if period.get('label_start') and period.get('label_end') else 'ikke entydig'),
        'Ytre info.xml: ' + (period.get('outer_start') or '?') + ' – ' + (period.get('outer_end') or '?'),
        'Indre arkivuttrekk.xml: ' + (period.get('inner_start') or '?') + ' – ' + (period.get('inner_end') or '?'),
    ]
    if part:
        lines.extend((f"Arkivdel: {part['title']} ({part['status']})",
                      '  Oppgitt arkivdelperiode: ' + (part['start'] or '?') + ' – ' + (part['end'] or '(ingen sluttdato)')))
    lines.append('OBSERVERTE DATOFELT I VALGT XML-OBJEKT')
    lines.extend(f'  {k} = {v}' for k, v in observed)
    if not observed:
        lines.append('  Ingen av de oppgitte datofeltene er dokumentert i dette objektet.')
    inner_start, inner_end = _year(period.get('inner_start')), _year(period.get('inner_end'))
    outer_start, outer_end = _year(period.get('outer_start')), _year(period.get('outer_end'))
    label_start, label_end = _year(period.get('label_start')), _year(period.get('label_end'))
    lines.extend(('', 'KILDESAMMENLIGNING'))
    if period.get('inner_end') and period.get('outer_end') and period['inner_end'] != period['outer_end']:
        lines.append('  Ytre og indre sluttdato er forskjellige – krever faglig avklaring.')
    if label_end is not None and inner_end is not None and label_end != inner_end:
        lines.append('  LABEL-sluttår og indre uttrekksmetadata er forskjellige; LABEL er ikke en kontrollgrense.')
    for key, value in observed:
        y = _year(value[:10]) if len(value) > 10 else _year(value)
        if y is None:
            continue
        # Prefer a genuine day-level comparison when the XML observation and
        # metadata limits contain complete ISO dates; year-only fields cannot
        # establish whether a date fell before or after a day within that year.
        actual = date.fromisoformat(value[:10]) if re.fullmatch(r'\d{4}-\d{2}-\d{2}', value[:10]) else None
        inner_low = date.fromisoformat(period['inner_start']) if re.fullmatch(r'\d{4}-\d{2}-\d{2}', str(period.get('inner_start') or '')) else None
        inner_high = date.fromisoformat(period['inner_end']) if re.fullmatch(r'\d{4}-\d{2}-\d{2}', str(period.get('inner_end') or '')) else None
        outer_low = date.fromisoformat(period['outer_start']) if re.fullmatch(r'\d{4}-\d{2}-\d{2}', str(period.get('outer_start') or '')) else None
        outer_high = date.fromisoformat(period['outer_end']) if re.fullmatch(r'\d{4}-\d{2}-\d{2}', str(period.get('outer_end') or '')) else None
        if actual and inner_low and inner_high:
            inside = inner_low <= actual <= inner_high
            lines.append(f'  {key} ({value}): ' + ('INNENFOR indre angitte datoer'
                      if inside else 'UTENFOR indre angitte datoer – må vurderes'))
        elif inner_start is not None and inner_end is not None:
            inside = inner_start <= y <= inner_end
            lines.append(f'  {key} ({y}): ' + ('INNENFOR indre angitte år (dag ikke vurdert)'
                      if inside else 'UTENFOR indre angitte år – må vurderes'))
        if actual and outer_low and outer_high:
            outside_outer = not outer_low <= actual <= outer_high
        else:
            outside_outer = (outer_start is not None and outer_end is not None
                             and not outer_start <= y <= outer_end)
        if outside_outer:
            lines.append(f'  {key} ({value}): UTENFOR ytre info.xml-periode, men dette er en separat kilde.')
    if period.get('observed_series'):
        lines.append('LAGREDE OBSERVERTE ÅRSSERIER (DWM, hele uttrekket)')
        descriptions = {'folder_created': 'Mappeopprettelser',
                        'registration_created': 'Registreringer',
                        'journal_date': 'Journaldatoer',
                        'document_description_created': 'Dokumentbeskrivelser'}
        for k, entry in period['observed_series'].items():
            if entry.get('last_year'):
                lines.append('  ' + descriptions.get(k, k) + ': seneste registrerte år '
                             + entry['last_year'] + ', antall i det året '
                             + str(entry.get('count_last_year', 'ukjent')))
    lines.extend(('', 'Ingen perioder, saksstatuser eller KS-beslutninger endres automatisk.',
                  'Sammenlign kildenes omfang og eventuelle avtaler før faglig konklusjon.'))
    return '\n'.join(lines)


def value_review_text(counts: dict) -> str:
    """Evidence draft for an explicitly completed count, never saved automatically."""
    if not counts or not counts.get('complete'):
        return ''
    lines = [
        'VERDIFORDELING (Source, full opptelling) ' + counts['metadata_id']
        + ' / ' + counts['xml_field'],
        'Kilde: ' + counts['source_path'],
        f"Forekomster: {counts['observed_total']}; ulike verdier: {counts['observed_distinct']}",
        f"I registrert standardverdisett: {counts['inside_registered_set'] if counts['inside_registered_set'] is not None else 'ikke klassifisert'}; "
        f"utenfor: {counts['outside_registered_set'] if counts['outside_registered_set'] is not None else 'ikke klassifisert'}",
        f"Angitt som tillatt ved avlevering: {counts.get('eligible_at_delivery') if counts.get('eligible_at_delivery') is not None else 'ingen registrert avleveringsbetingelse'}; "
        f"ikke angitt som tillatt: {counts.get('not_eligible_at_delivery') if counts.get('not_eligible_at_delivery') is not None else 'ikke klassifisert'}",
    ]
    condition = counts.get('delivery_condition')
    if condition:
        lines.append('Betingelseskilde: ' + condition['source_title'] + ', s. '
                     + str(condition['page']) + '; ' + condition['source_url'])
    lines.append('FAKTISK OBSERVERTE VERDIER (utvalg av opptellingen)')
    observed = [r for r in counts.get('values') or () if r['total']]
    for row in observed[:25]:
        scoped = ('; i valgt arkivdel: ' + str(row['archive_part'])
                  if row.get('archive_part') is not None else '')
        lines.append('- ' + row['value'] + ': ' + str(row['total']) + scoped
                     + ' | ' + row['reference_relation'] + ' | ' + row['delivery_relation'])
    if len(observed) > 25:
        lines.append('... ' + str(len(observed) - 25) + ' flere verdier finnes i inspeksjonsvisningen.')
    lines.append('Kildebasert sammenligning – ikke ny Arkade-test, automatisk normativ'
                 ' godkjenning eller faglig depotbeslutning.')
    return '\n'.join(lines)
