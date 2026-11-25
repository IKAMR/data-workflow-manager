"""Bounded-memory implementation of the legacy U1 v1 result model.

The source XML is parsed once with lxml.iterparse. No entire XML tree or
unbounded global XPath node sets are retained. Fields follow U1's legacy
spelling, including sakstatus/filstoerrelse.
"""
from __future__ import annotations

from collections import Counter
from datetime import date
from pathlib import Path
from typing import Callable
from lxml import etree

from .u1_total import XSI, _safe_date, _size_buckets


def _sorted(counter):
    return dict(sorted(((k, v) for k, v in counter.items() if k != '') if hasattr(counter, 'items') else counter,
                       key=lambda pair: str(pair[0]).casefold()))


def run_u1_stream(path: str | Path, *, progress_cb: Callable[[int], None] | None = None) -> dict:
    source = Path(path)
    totals = Counter()
    kinds = {key: Counter() for key in ('mappe', 'registrering')}
    dates = {key: [None, None] for key in (
        'archive_created', 'archive_closed', 'archive_part_created', 'archive_part_closed',
        'folder_created', 'folder_closed', 'case_date', 'meeting_date',
        'registration_archived', 'journal_date', 'document_created')}
    date_fields = {
        'arkiv': [('opprettetDato', 'archive_created'), ('avsluttetDato', 'archive_closed')],
        'arkivdel': [('opprettetDato', 'archive_part_created'), ('avsluttetDato', 'archive_part_closed')],
        'mappe': [('opprettetDato', 'folder_created'), ('avsluttetDato', 'folder_closed'),
                  ('saksdato', 'case_date'), ('moetedato', 'meeting_date')],
        'registrering': [('arkivertDato', 'registration_archived')],
        'dokumentbeskrivelse': [('opprettetDato', 'document_created')],
    }
    counters = {k: Counter() for k in (
        'folder_status', 'registration_type', 'journal_type', 'journal_status',
        'folder_year', 'registration_year', 'journal_year', 'doc_medium', 'doc_status',
        'doc_relation', 'doc_type', 'variant', 'format', 'format_detail',
        'correspondence_parent', 'writeoff_method', 'sletting_type',
        'convert_from', 'convert_to', 'convert_tool')}
    direct = Counter()
    numbers = {'dokumentnummer': Counter(), 'versjonsnummer': Counter(), 'filstoerrelse': Counter()}
    file_sum = file_count = file_max = 0
    filesize_buckets = _size_buckets([])
    archive_rows, creator_rows, part_rows = [], [], []
    stack = []
    report_every = 100_000

    def text(frame, name):
        return frame['values'].get(name, '')

    def add_date(key, value):
        d = _safe_date(value)
        if d is not None:
            start, end = dates[key]
            dates[key][0] = min(start, d) if start else d
            dates[key][1] = max(end, d) if end else d

    def year(frame, name, key):
        value = text(frame, name)
        if len(value) >= 4:
            counters[key][value[:4]] += 1

    def relevant_ancestor(tag):
        for frame in reversed(stack):
            if frame['tag'] == tag:
                return frame
        return None

    for event, elem in etree.iterparse(str(source), events=('start', 'end'),
                                       resolve_entities=False, no_network=True,
                                       huge_tree=True):
        if event == 'start':
            tag = etree.QName(elem).localname
            if stack:
                stack[-1]['children'][tag] += 1
            frame = {'tag': tag, 'values': {}, 'children': Counter(),
                     'attrs': len(elem.attrib), 'type': (elem.get(f'{{{XSI}}}type') or elem.get('type') or '').strip(),
                     'part': None, 'depth': len(stack)}
            if tag == 'arkivdel':
                frame['part'] = {'mappe': 0, 'registrering': 0,
                                 'dokumentbeskrivelse': 0, 'doc_medium': Counter()}
            stack.append(frame)
            totals[tag] += 1
            if progress_cb and totals['dokumentobjekt'] and totals['dokumentobjekt'] % report_every == 0 and tag == 'dokumentobjekt':
                progress_cb(totals['dokumentobjekt'])
            # Legacy nested descendant semantics for each archive part.
            part_frame = relevant_ancestor('arkivdel')
            if part_frame and tag in ('mappe', 'registrering', 'dokumentbeskrivelse') and part_frame is not frame:
                part_frame['part'][tag] += 1
            if tag == 'dokumentflyt' and relevant_ancestor('registrering') is not None:
                totals['_documentflow_under_registrering'] += 1
            continue
        frame = stack.pop()
        tag = frame['tag']
        parent = stack[-1] if stack else None
        parent_tag = parent['tag'] if parent else ''
        if parent:
            direct[(parent_tag, tag)] += 1
        # Text is copied into the small parent frame before freeing the element.
        # Itertext on an immediate child matches the original _first_text helper.
        scalar = ''.join(elem.itertext()).strip() if len(elem) == 0 else ''
        if parent and tag not in parent['values']:
            parent['values'][tag] = scalar
        if tag in ('dokumentnummer', 'versjonsnummer', 'filstoerrelse'):
            try:
                number = int(float(scalar))
                if tag != 'filstoerrelse':
                    numbers[tag][number] += 1
                if tag == 'filstoerrelse':
                    if number == 0: bucket = '0'
                    elif number < 10: bucket = '1-9'
                    elif number < 100: bucket = '10-99'
                    elif number < 200: bucket = '100-199'
                    elif number < 500: bucket = '200-499'
                    elif number < 1000: bucket = '500-999'
                    elif number < 2000: bucket = '1000-1999'
                    elif number < 10000: bucket = '2000-9999'
                    elif number < 100000: bucket = '10k-100k'
                    elif number < 1000000: bucket = '100k-1M'
                    elif number < 10000000: bucket = '1M-10M'
                    elif number < 100000000: bucket = '10M-100M'
                    else: bucket = '>=100M'
                    filesize_buckets[bucket] += 1
                    file_sum += number
                    file_count += 1
                    file_max = max(file_max, number)
            except (ValueError, OverflowError):
                pass
        scalar_counter = {
            'tilknyttetRegistreringSom': 'doc_relation', 'dokumenttype': 'doc_type',
            'format': 'format', 'formatDetaljer': 'format_detail',
            'avskrivningsmaate': 'writeoff_method', 'slettingstype': 'sletting_type',
            'konvertertFraFormat': 'convert_from', 'konvertertTilFormat': 'convert_to',
            'konverteringsverktoey': 'convert_tool',
        }.get(tag)
        if scalar_counter and scalar:
            counters[scalar_counter][scalar] += 1
        if tag == 'korrespondansepart':
            counters['correspondence_parent'][parent_tag] += 1
        for field, date_key in date_fields.get(tag, []):
            add_date(date_key, text(frame, field))
        if tag == 'arkiv':
            archive_rows.append({
                'title': text(frame, 'tittel'), 'system_id': text(frame, 'systemID'),
                'description': text(frame, 'beskrivelse'), 'status': text(frame, 'arkivstatus'),
                'document_medium': text(frame, 'dokumentmedium'),
                'created_date': text(frame, 'opprettetDato')[:10],
                'closed_date': text(frame, 'avsluttetDato')[:10],
                'created_by': text(frame, 'opprettetAv'), 'closed_by': text(frame, 'avsluttetAv')})
        if tag == 'arkivskaper':
            creator_rows.append({'name': text(frame, 'arkivskaperNavn'),
                                 'id': text(frame, 'arkivskaperID'),
                                 'description': text(frame, 'beskrivelse')})
        if tag == 'arkivdel':
            part = frame['part']
            part_rows.append({'index': len(part_rows) + 1,
                'title': text(frame, 'tittel'), 'document_medium': text(frame, 'dokumentmedium'),
                'created_date': text(frame, 'opprettetDato')[:10],
                'closed_date': text(frame, 'avsluttetDato')[:10],
                'status': text(frame, 'arkivdelstatus'),
                'mappe_count': part['mappe'],
                'registrering_count': part['registrering'],
                'dokumentbeskrivelse_count': part['dokumentbeskrivelse'],
                'document_medium_counts': _sorted(part['doc_medium'])})
        if tag == 'mappe':
            kinds['mappe'][frame['type']] += 1
            value = text(frame, 'saksstatus')
            if value: counters['folder_status'][value] += 1
            totals['_folder_attr_3'] += frame['attrs'] == 3
            totals['_folder_empty'] += not (frame['children']['mappe'] or frame['children']['registrering'])
            totals['_folder_subclass'] += bool(frame['children']['klasse'])
            totals['_closed_saksmappe'] += frame['type'] == 'saksmappe' and bool(text(frame, 'avsluttetDato'))
            totals['_closed_moetemappe'] += frame['type'] == 'moetemappe' and bool(text(frame, 'avsluttetDato'))
            totals['_case_closed'] += value == 'Avsluttet'
            totals['_case_cancelled'] += value == 'Utgår'
            totals['_case_inprogress'] += text(frame, 'sakstatus') == 'Underbehandling'
            year(frame, 'opprettetDato', 'folder_year')
        if tag == 'klasse':
            totals['_class_with_subclass_folder'] += bool(frame['children']['klasse']) * frame['children']['mappe']
            totals['_class_with_subclass_registration'] += bool(frame['children']['klasse']) * frame['children']['registrering']
        if tag == 'registrering':
            typ = frame['type']
            for key, field in [('journal_type', 'journalposttype'), ('journal_status', 'journalstatus')]:
                value = text(frame, field)
                if value: counters[key][value] += 1
            kinds['registrering'][typ] += 1
            totals['_reg_attr_3'] += frame['attrs'] == 3
            totals['_reg_without_desc'] += frame['children']['dokumentbeskrivelse'] == 0
            totals['_reg_without_desc_id'] += frame['children']['dokumentbeskrivelse'] == 0 and bool(text(frame, 'registreringsID'))
            year(frame, 'opprettetDato', 'registration_year')
            year(frame, 'journaldato', 'journal_year')
            if typ == 'journalpost':
                totals['_journalpost'] += 1
                add_date('journal_date', text(frame, 'journaldato'))
                totals['_jp_with_documentflow'] += bool(frame['children']['dokumentflyt'])
                totals['_jp_with_writeoff_method'] += frame['children']['_avskrivning_with_method']
                totals['_jp_with_writeoff_reference'] += frame['children']['_avskrivning_with_reference']
                totals['_jp_presedens'] += frame['children']['presedens']
            if typ == 'arkivnotat':
                totals['_arkivnotat_documentflow'] += frame['children']['dokumentflyt']
        if tag == 'avskrivning' and parent:
            parent['children']['_avskrivning_with_method'] += bool(text(frame, 'avskrivningsmaate'))
            parent['children']['_avskrivning_with_reference'] += bool(text(frame, 'referanseAvskrivesAvJournalpost'))
        if tag == 'dokumentbeskrivelse':
            relation = text(frame, 'tilknyttetRegistreringSom')
            status = text(frame, 'dokumentstatus')
            medium = text(frame, 'dokumentmedium')
            counters['doc_status'][status] += bool(status)
            counters['doc_medium'][medium] += bool(medium)
            totals['_doc_main'] += relation == 'Hoveddokument'
            totals['_doc_without_object'] += frame['children']['dokumentobjekt'] == 0
            totals['_doc_finished'] += status == 'Dokumentet er ferdigstilt'
            totals['_doc_editing'] += status == 'Dokumentet er under redigering'
            totals['_doc_other'] += status not in ('Dokumentet er ferdigstilt', 'Dokumentet er under redigering')
            part = relevant_ancestor('arkivdel')
            if part is not None and medium:
                part['part']['doc_medium'][medium] += 1
        if tag == 'dokumentobjekt':
            value = text(frame, 'variantformat')
            if value: counters['variant'][value] += 1
            totals['_obj_conversion'] += frame['children']['konvertering']
        if tag == 'journalstatus' and not scalar:
            totals['_empty_journalstatus'] += 1
        if tag == 'kryssreferanse':
            totals['_cross_children'] += sum(frame['children'].values())
            if parent_tag in ('klasse', 'mappe', 'registrering'):
                totals[f'_cross_{parent_tag}'] += sum(frame['children'].values())
        elem.clear()
        while elem.getprevious() is not None:
            del elem.getparent()[0]

    def dr(key):
        low, high = dates[key]
        return {'first': low.isoformat() if low else None, 'last': high.isoformat() if high else None}
    def count(parent, child): return direct[(parent, child)]
    def count_group(tag):
        return {parent: count(parent, tag) for parent in ('arkivdel', 'klasse', 'mappe', 'registrering', 'dokumentbeskrivelse')}
    def num(name): return numbers[name]
    def number_values(name): return sum(num(name).values())
    document_numbers = num('dokumentnummer')
    versions = num('versjonsnummer')
    return {
        'model_format_version': 1, 'definition_id': 'noark5.u1.total.v1',
        'source': str(source), 'scope': 'whole_extraction',
        'archive': {'count': totals['arkiv'], 'items': archive_rows,
                    'creator_count': totals['arkivskaper'], 'creators': creator_rows},
        'dates': {key: dr(key) for key in dates},
        'structure': {'archive_part_count': totals['arkivdel'], 'archive_parts': part_rows,
                      'classification_system_count': totals['klassifikasjonssystem'],
                      'class_count': totals['klasse'],
                      'class_with_subclass_and_folder': totals['_class_with_subclass_folder'],
                      'class_with_subclass_and_registration': totals['_class_with_subclass_registration']},
        'folders': {'count': totals['mappe'], 'type_counts': _sorted(kinds['mappe']),
                    'without_specialization_attribute_model': totals['_folder_attr_3'],
                    'without_subfolder_or_registration': totals['_folder_empty'],
                    'status_counts': _sorted(counters['folder_status']),
                    'case_status_fixed': {'Avsluttet': totals['_case_closed'], 'Utgår': totals['_case_cancelled'],
                                          'Under behandling (source sakstatus=Underbehandling)': totals['_case_inprogress']},
                    'closed_date_by_type': {'saksmappe': totals['_closed_saksmappe'],
                                            'moetemappe': totals['_closed_moetemappe']},
                    'created_per_year': _sorted(counters['folder_year'])},
        'registrations': {'count': totals['registrering'], 'type_counts': _sorted(kinds['registrering']),
                         'without_specialization_attribute_model': totals['_reg_attr_3'],
                         'empty_journalstatus_elements': totals['_empty_journalstatus'],
                         'without_document_description': totals['_reg_without_desc'],
                         'without_document_description_with_id': totals['_reg_without_desc_id'],
                         'created_per_year': _sorted(counters['registration_year']),
                         'journalposts': {'count': totals['_journalpost'],
                                          'type_counts': _sorted(counters['journal_type']),
                                          'status_counts': _sorted(counters['journal_status']),
                                          'journal_date_per_year': _sorted(counters['journal_year']),
                                          'fixed_types': {k: counters['journal_type'][k] for k in (
                                              'Inngående dokument', 'Utgående dokument',
                                              'Organinternt dokument for oppfølging',
                                              'Organinternt dokument uten oppfølging', 'Saksframlegg')},
                                          'fixed_status': {k: counters['journal_status'][k] for k in (
                                              'Arkivert', 'Utgår', 'Journalført', 'Ekspedert')}}},
        'documents': {'description_count': totals['dokumentbeskrivelse'],
                      'main_document_count': totals['_doc_main'],
                      'attachment_or_other_count': totals['dokumentbeskrivelse'] - totals['_doc_main'],
                      'relation_type_counts': _sorted(counters['doc_relation']),
                      'document_number': {'count': number_values('dokumentnummer'),
                                         '1': document_numbers[1], '2': document_numbers[2],
                                         '3': document_numbers[3],
                                         '>=4': sum(v for k, v in document_numbers.items() if k >= 4),
                                         '>=100': sum(v for k, v in document_numbers.items() if k >= 100)},
                      'version_number': {'count': number_values('versjonsnummer'),
                                         **{str(v): versions[v] for v in range(1, 10)},
                                         '>=10': sum(v for k, v in versions.items() if k >= 10)},
                      'without_object': totals['_doc_without_object'],
                      'status': {'Ferdigstilt': totals['_doc_finished'],
                                 'Under redigering': totals['_doc_editing'],
                                 'Annen status': totals['_doc_other'],
                                 'generic': _sorted(counters['doc_status'])},
                      'medium_counts': _sorted(counters['doc_medium']),
                      'object_count': totals['dokumentobjekt'],
                      'variant_format_counts': _sorted(counters['variant']),
                      'document_type_counts': _sorted(counters['doc_type'])},
        'relations': {'correspondence_party_count': totals['korrespondansepart'],
                      'correspondence_party_parent_counts': _sorted(counters['correspondence_parent']),
                      'sakspart_count': totals['sakspart'], 'part_count': totals['part'],
                      'part_direct': {key: count(key, 'part') for key in ('mappe', 'registrering', 'dokumentbeskrivelse')},
                      'merknad': {'count': totals['merknad'], **{key: count(key, 'merknad') for key in ('mappe', 'registrering', 'dokumentbeskrivelse')}},
                      'cross_reference_children': {'count': totals['_cross_children'],
                           **{key: totals[f'_cross_{key}'] for key in ('klasse', 'mappe', 'registrering')}},
                      'precedent': {'count': totals['presedens'], 'mappe': count('mappe', 'presedens'),
                                    'journalpost': totals['_jp_presedens']},
                      'write_off': {'method_count': totals['avskrivningsmaate'],
                                    'method_counts': _sorted(counters['writeoff_method']),
                                    'journalpost_with_method': totals['_jp_with_writeoff_method'],
                                    'reference_to_other_journalpost': totals['_jp_with_writeoff_reference']},
                      'document_flow': {'count': totals['_documentflow_under_registrering'],
                                        'journalpost': totals['_jp_with_documentflow'],
                                        'arkivnotat': totals['_arkivnotat_documentflow']}},
        'preservation': {'screening': {'count': totals['skjerming'], **count_group('skjerming')},
                         'grading_v31_v40': {'count': totals['gradering'], **count_group('gradering')},
                         'grading_v50': {'count': totals['grad'], **count_group('grad')},
                         'disposal_decision': {'count': totals['kassasjon'], **count_group('kassasjon')},
                         'performed_disposal_document_description': count('dokumentbeskrivelse', 'utfoertKassasjon'),
                         'deletion': {'count': totals['sletting'], 'type_counts': _sorted(counters['sletting_type'])},
                         'business_specific_metadata': {'count': totals['virksomhetsspesifikkeMetadata'],
                            **{key: count(key, 'virksomhetsspesifikkeMetadata') for key in ('mappe', 'registrering', 'dokumentbeskrivelse', 'part')}}},
        'files': {'size_count': file_count, 'size_buckets': filesize_buckets,
                  'size_average': round(file_sum / file_count) if file_count else 0,
                  'size_max': file_max, 'size_sum': file_sum,
                  'format_counts': _sorted(counters['format']),
                  'format_details_counts': _sorted(counters['format_detail'])},
        'conversion': {'count': totals['konvertering'],
                       'object_conversion_count': totals['_obj_conversion'],
                       'from_format_counts': _sorted(counters['convert_from']),
                       'to_format_counts': _sorted(counters['convert_to']),
                       'tool_counts': _sorted(counters['convert_tool'])},
        'reserved_cross_file_u1_items': [
            'N5.52 loependeJournal', 'N5.53 loependeJournal per år',
            'N5.55 skjermede journalposter i loependeJournal',
            'N5.56 offentligJournal', 'N5.57 offentligJournal per år',
            'N5.61 endringslogg og per år'],
    }
