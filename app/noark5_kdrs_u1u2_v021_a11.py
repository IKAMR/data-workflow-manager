"""a11.4: bounded source-witnessed U01 / U02 count comparisons.

These are observations parsed from KDRS Query text, NOT re-executed Saxon
results. Only literal counts that can be paired to an existing DWM field are
admitted. In particular, U02 archive-part labels are checked against the DWM
result identities before any archive-part metric enters the mapping.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
from typing import Any, Callable

from app.noark5_kdrs_parity_v021_a11 import read_json, safe_result_file


@dataclass(frozen=True)
class U1Count:
    metric: str
    label: str
    xpath: str
    dwm_path: str


# Original 2026-05-26 U01 text and the existing DWM u1_total.py model.
# Do not include date extrema, attribute-specialization or cardinality rules:
# some historical calculations differ from current DWM implementation.
U1_COUNTS: tuple[U1Count, ...] = (
    U1Count('archive_count', 'N5.04 Arkiv:', 'count(//arkiv)', 'archive.count'),
    U1Count('archive_creator_count', 'Arkivstrukturen inneholder', 'count(//arkivskaper)', 'archive.creator_count'),
    U1Count('archive_part_count', 'N5.05/06 Arkivdeler:', 'count(//arkivdel)', 'structure.archive_part_count'),
    U1Count('classification_system_count', 'N5.07 Klassifikasjonssystemer:', 'count(//klassifikasjonssystem)', 'structure.classification_system_count'),
    U1Count('class_count', 'N5.08 Klasser:', 'count(//klasse)', 'structure.class_count'),
    U1Count('class_with_subclass_and_folder', 'N5.12 Klasser med både mappe og underklasse (>0 er avvik):',
            'count(//klasse[klasse]/mappe)', 'structure.class_with_subclass_and_folder'),
    U1Count('class_with_subclass_and_registration', 'N5.19.01 Antall klasser med både registrering og underklasse (>0 er avvik):',
            'count(//klasse[klasse]/registrering)', 'structure.class_with_subclass_and_registration'),
    U1Count('folder_count', 'N5.10/12/14 Mapper:', 'count(//mappe)', 'folders.count'),
    U1Count('registration_count', 'N5.16 Registreringer:', 'count(//registrering)', 'registrations.count'),
    U1Count('document_description_count', 'N5.23 Dokumentbeskrivelse:', 'count(//dokumentbeskrivelse)', 'documents.description_count'),
    U1Count('without_object_count', 'N5.24 Dokumentbeskrivelser uten dokumentobjekt:',
            'count(//dokumentbeskrivelse[not(dokumentobjekt)])', 'documents.without_object'),
    U1Count('document_object_count', 'N5.26.01 Dokumentobjekt:', 'count(//dokumentobjekt)', 'documents.object_count'),
    U1Count('correspondence_party_count', 'N5.39 Korrespondanseparter:', 'count(//korrespondansepart)', 'relations.correspondence_party_count'),
    U1Count('note_count', 'N5.36 Merknader:', 'count(//merknad)', 'relations.merknad.count'),
    U1Count('cross_reference_children', 'N5.37 Kryssreferanser:', 'count(//kryssreferanse/*)', 'relations.cross_reference_children.count'),
    U1Count('precedent_count', 'N5.38 Presedenser:', 'count(//presedens)', 'relations.precedent.count'),
    U1Count('screening_count', 'N5.42 Skjerminger:', 'count(//skjerming)', 'preservation.screening.count'),
    U1Count('disposal_count', 'N5.44 Kassasjonsvedtak:', 'count(//kassasjon)', 'preservation.disposal_decision.count'),
    U1Count('performed_disposal_count', 'N5.45 Utførte kassasjoner:',
            'count(//dokumentbeskrivelse/utfoertKassasjon)', 'preservation.performed_disposal_document_description'),
    U1Count('deletion_count', 'N5.47 Sletting utenom kassasjon:', 'count(//sletting)', 'preservation.deletion.count'),
    U1Count('conversion_count', 'N5.46 Konverterte dokumenter:', 'count(descendant::konvertering)', 'conversion.count'),
)


@dataclass(frozen=True)
class U2Count:
    metric: str
    label: str
    xpath: str
    source_label: str


# Source expressions use descendant:: relative to each //arkivdel context;
# DWM u2_archive_parts runs equivalent .// metrics in the same part context.
# Equality is provisional: a literal source witness is not semantic proof.
U2_COUNTS: tuple[U2Count, ...] = (
    U2Count('classification_system_count', 'Klassifikasjonssystemer:', 'count(descendant::klassifikasjonssystem)', 'Klassifikasjonssystemer:'),
    U2Count('class_count', 'Klasser:', 'count(descendant::klasse)', 'Klasser:'),
    U2Count('folder_count', '[.2] Mappe typer: @@, Alle:', 'count(descendant::mappe)', '[.2] Mappe typer: @@'),
    U2Count('registration_count', '[.3] Registreringer; Alle:', 'count(descendant::registrering)', '[.3] Registreringer; Alle:'),
    U2Count('document_description_count', '[.4] Dokumentbeskrivelse; Alle:', 'count(descendant::dokumentbeskrivelse)', '[.4] Dokumentbeskrivelse; Alle:'),
    U2Count('document_object_count', 'Dokumentobjekt; Alle:', 'count(descendant::dokumentobjekt)', 'Dokumentobjekt; Alle:'),
    U2Count('correspondence_party_count', '[.5] Korrespondansepart:', 'count(descendant::korrespondansepart)', '[.5] Korrespondansepart:'),
    U2Count('sakspart_count', 'Sakspart:', 'count(descendant::sakspart)', 'Sakspart:'),
    U2Count('part_count', 'Part:', 'count(descendant::part)', 'Part:'),
    U2Count('writeoff_count', 'Avskrivning:', 'count(descendant::avskrivningsmaate)', 'Avskrivning:'),
    U2Count('screening_count', 'Skjerming:', 'count(descendant::skjerming)', 'Skjerming:'),
    U2Count('disposal_count', 'Kassasjonsvedtak:', 'count(descendant::kassasjon)', 'Kassasjonsvedtak:'),
    U2Count('performed_disposal_count', 'Utført kassasjon:', 'count(descendant::utfoertKassasjon)', 'Utført kassasjon:'),
    U2Count('deletion_count', 'Sletting:', 'count(descendant::sletting)', 'Sletting:'),
)


def _flatten(expression: str) -> str:
    # Quote differences and layout whitespace are not XPath equivalence proof,
    # but are sufficient to locate the literal labelled count witness.
    return re.sub(r'\s+', '', expression).replace('"', "'")


def _witness(source_body: str, label: str, xpath: str, *, max_gap: int = 180) -> bool:
    source = _flatten(source_body)
    l = _flatten(label)
    e = _flatten(xpath)
    start = 0
    while True:
        pos = source.find(l, start)
        if pos < 0:
            return False
        xp = source.find(e, pos + len(l))
        if xp >= 0 and xp - (pos + len(l)) <= max_gap:
            return True
        start = pos + len(l)


def map_u1(raw: str, source_body: str, test: dict[str, Any],
           parse_count: Callable[[str, str], tuple[int | None, str]]) -> tuple[dict, list[dict], list[dict]]:
    """Return parsed metric values, explicit comparison rows, and QA issues."""
    if test.get('execution', {}).get('kind') != 'u1_total' or test.get('test_id') != 'kdrs.u01':
        return {}, [], [{'kind': 'u1_engine_definition_not_recognized'}]
    values: dict[str, int] = {}
    rows: list[dict] = []
    problems: list[dict] = []
    for s in U1_COUNTS:
        if not _witness(source_body, s.label, s.xpath):
            problems.append({'kind':'u1_xpath_label_witness_missing', 'metric_id':s.metric})
            continue
        value, reason = parse_count(raw, s.label)
        if value is None:
            # Historical output may be incomplete/ambiguous. Never guess zero.
            if reason != 'label_missing_or_ambiguous' or s.metric == 'archive_count':
                problems.append({'kind':'u1_count_not_mappable', 'metric_id':s.metric, 'reason':reason})
            continue
        values[s.metric] = value
        rows.append({'profile':'U1', 'job_id':'U01', 'test_id':'kdrs.u01',
                     'kdrs_path':f'metrics.{s.metric}', 'dwm_path':s.dwm_path,
                     'source_xpath_witness':s.xpath})
    return values, rows, problems


ARCHIVE_MARKER = re.compile(r'(?<![A-Za-z0-9])Arkivdel\s+(\d+):\s*')


def _read_u2_identity(index_path: Path) -> tuple[list[dict] | None, str]:
    """Read only an existing DWM U02 result. Never run XML processing here."""
    try:
        index = read_json(index_path)
        if index.get('result_set_format_version') != 2 or not isinstance(index.get('tests'), list):
            return None, 'dwm_index_not_v2'
        matches = [item for item in index['tests'] if isinstance(item, dict)
                   and item.get('test_id') == 'kdrs.u02']
        if len(matches) != 1 or matches[0].get('status') != 'ok':
            return None, 'dwm_u02_result_missing_or_not_ok'
        path = safe_result_file(index_path.parent, str(matches[0].get('file','')))
        result = read_json(path)
        if (result.get('test_id') != 'kdrs.u02' or result.get('status') != 'ok' or
                result.get('source_xml') != 'arkivstruktur.xml'):
            return None, 'dwm_u02_result_invalid'
        parts = result.get('values',{}).get('archive_parts')
        if not isinstance(parts, list) or not parts or len(parts) > 10000:
            return None, 'dwm_u02_part_list_missing_or_too_large'
        out = []
        for n, item in enumerate(parts,1):
            identity = item.get('archive_part') if isinstance(item,dict) else None
            if not isinstance(identity,dict) or identity.get('index') != n or not isinstance(identity.get('title'),str) or not identity['title'].strip():
                return None, 'dwm_u02_archive_part_identity_invalid'
            if not isinstance(item.get('values'), dict):
                return None, 'dwm_u02_archive_part_values_invalid'
            out.append({'index':n, 'title':identity['title'], 'system_id':identity.get('system_id')})
        return out, ''
    except (ValueError, OSError, KeyError, TypeError, AttributeError):
        return None, 'dwm_u02_result_unreadable'


def _split_u2(raw: str, dwm_parts: list[dict]) -> tuple[list[str] | None, str]:
    """Map exact ordered 'Arkivdel N: title' markers to existing DWM parts.

    Do not infer identity from a title alone or from coincidentally equal counts.
    A false-positive marker in a description makes the entire result ambiguous.
    """
    matches = list(ARCHIVE_MARKER.finditer(raw))
    if len(matches) != len(dwm_parts):
        return None, 'u2_archive_part_marker_count_mismatch'
    sections = []
    for index, (m, part) in enumerate(zip(matches, dwm_parts)):
        if len(m.group(1)) > 9 or int(m.group(1)) != part['index']:
            return None, 'u2_archive_part_index_mismatch'
        remaining = raw[m.end():]
        title = part['title']
        if not remaining.startswith(title):
            return None, 'u2_archive_part_title_mismatch'
        after = remaining[len(title):]
        if not after or not re.match(r'^\s*[,\n\r]', after):
            return None, 'u2_archive_part_title_boundary_ambiguous'
        end = matches[index+1].start() if index+1 < len(matches) else len(raw)
        sections.append(raw[m.start():end])
    return sections, ''


def map_u2(raw: str, source_body: str, test: dict[str, Any],
           dwm_index_path: Path | None,
           parse_count: Callable[[str, str], tuple[int | None, str]]) -> tuple[dict, list[dict], list[dict]]:
    if test.get('execution', {}).get('kind') != 'u2_archive_parts' or test.get('test_id') != 'kdrs.u02':
        return {}, [], [{'kind':'u2_engine_definition_not_recognized'}]
    if dwm_index_path is None:
        return {}, [], []  # a11.3 import-only workflow remains valid.
    parts, reason = _read_u2_identity(dwm_index_path)
    if parts is None:
        return {}, [], [{'kind':reason}]
    # Bound work before allocating potentially hundreds of thousands of rows.
    if len(parts) * len(U2_COUNTS) > 20000:
        return {}, [], [{'kind':'u2_archive_part_metric_limit_exceeded'}]
    sections, reason = _split_u2(raw,parts)
    if sections is None:
        return {}, [], [{'kind':reason}]
    values = []
    rows = []
    problems = []
    for i, (part, chunk) in enumerate(zip(parts,sections)):
        observed = {}
        for spec in U2_COUNTS:
            if not _witness(source_body, spec.source_label, spec.xpath):
                problems.append({'kind':'u2_xpath_label_witness_missing', 'metric_id':spec.metric})
                continue
            count, why = parse_count(chunk, spec.label)
            if count is None:
                if why != 'label_missing_or_ambiguous':
                    problems.append({'kind':'u2_count_not_mappable', 'part_index':part['index'],
                                     'metric_id':spec.metric, 'reason':why})
                continue
            observed[spec.metric] = count
            rows.append({'profile':'U2','job_id':'U02','test_id':'kdrs.u02',
                         'archive_part':dict(part),
                         'kdrs_path':f'metrics.archive_parts.{i}.values.{spec.metric}',
                         'dwm_path':f'archive_parts.{i}.values.{spec.metric}',
                         'source_xpath_witness':spec.xpath})
        values.append({'archive_part':dict(part), 'values':observed})
    return {'archive_parts':values}, rows, problems
