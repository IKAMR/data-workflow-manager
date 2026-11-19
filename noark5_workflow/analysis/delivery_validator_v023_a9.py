"""DWM a9: source-bound Noark 5 delivery-value tests (M051-M054, v5.0).

A production status value may be in the standard vocabulary but forbidden at
transfer.  This engine does not replace XSD or XPath validation, and never makes
an acceptance/approval decision. Only confirmed 5.0 XSD evidence activates rules.

The complete finding list is streamed to JSONL/CSV; no findings are silently
truncated. Both outputs and the JSON summary are written only on successful
completion, with source SHA-256 and version/rule provenance.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
import csv
from hashlib import sha256
from html import escape
import json
import os
from pathlib import Path
import re
import tempfile
from typing import Any, Callable

from lxml import etree

ROOT = Path(__file__).resolve().parents[2]
RULES_FILE = ROOT / 'config/noark5/standards/delivery_value_conditions_v023_a3.json'
VALUES_FILE = ROOT / 'config/noark5/standards/noark5_standard_values.json'
MODEL = 'dwm.noark5.delivery-validation.a9.v1'
NOARK_ARCHIVE_NS = 'http://www.arkivverket.no/standarder/noark5/arkivstruktur'
SOURCE_REPOSITORY = 'IKAMR/digital-archive-workflow'
SOURCE_COMMIT = '8d28e312e1e38af8cb93bfe05cecef11e09af34f'
SOURCE_DOCUMENT = 'docs/kilder/noark/noark5/v5.0/spesifikasjoner/Noark 5 v 5 vedl1 Metadatakatalog.pdf'
SOURCE_DOCUMENT_SHA256 = 'e1f6b7caa24f869d82b21aa30b3452513029875e417b1e351b2b9298578ffd98'
SOURCE_DOCUMENT_STATUS = 'not_documented'  # Source library manifest, not an approval.
MAX_RULE_FILE_BYTES = 1_000_000
MAX_VALUE_FILE_BYTES = 15_000_000
MAX_SINGLE_FIELD_CHARS = 8_000_000  # Reject, never truncate a source status.
MAX_XML_DEPTH = 4096
MAX_DIRECT_STATUS_FIELDS = 1000
PROGRESS_EVERY = 8192
STATUS_PARENTS = {
    'M051': 'arkivdel',
    'M052': 'mappe',
    'M053': 'registrering',
    'M054': 'dokumentbeskrivelse',
}
# Keep journalpost compatibility explicit; never infer other parent/field names.
ADDITIONAL_PARENTS = {'M053': {'journalpost'}}
FINDING_FIELDS = ('finding_uid', 'source', 'test_id', 'metadata_id', 'severity',
                  'message', 'value', 'standard_value', 'delivery_value', 'context',
                  'file', 'lines', 'xpath', 'object_id', 'archive_part_id',
                  'source_ref', 'requires_review')


class DeliveryValidationError(ValueError):
    """Invalid source, rules or processing; never publish incomplete results."""


def _hash(path: Path) -> str:
    digest = sha256()
    with path.open('rb') as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def _read_json(path: Path, max_bytes: int) -> dict:
    if not path.is_file() or path.is_symlink() or path.stat().st_size > max_bytes:
        raise DeliveryValidationError('Kravregister mangler, er en lenke eller overstiger trygg lesestørrelse: ' + str(path))
    try:
        result = json.loads(path.read_text(encoding='utf-8-sig'))
    except (OSError, ValueError, UnicodeError) as exc:
        raise DeliveryValidationError('Kravregisteret er uleselig: ' + str(path)) from exc
    if not isinstance(result, dict):
        raise DeliveryValidationError('Kravregisteret må være et objekt: ' + str(path))
    return result


def _checked_rules(rules_path: Path, values_path: Path) -> tuple[dict, str, str, dict]:
    """Reuse a3's registered delivery restrictions, checked against vocabulary."""
    rules = _read_json(rules_path, MAX_RULE_FILE_BYTES)
    values = _read_json(values_path, MAX_VALUE_FILE_BYTES)
    if (rules.get('format_version') != 1 or rules.get('reference_version') != '5.0'
            or rules.get('model') != 'dwm.noark5.delivery-value-commentary.v1'):
        raise DeliveryValidationError('Ukjent eller feil Noark-versjon i avleveringsregister')
    source = rules.get('source')
    if not isinstance(source, dict) or not source.get('title') or not source.get('url'):
        raise DeliveryValidationError('Avleveringsregisteret mangler kildeidentitet')
    register = ((values.get('versions') or {}).get('5.0') or {}).get('value_sets') or {}
    if not isinstance(register, dict):
        raise DeliveryValidationError('Mangler separate Noark 5.0-produksjonsverdisett')
    definitions = {}
    for row in rules.get('rules') or []:
        if not isinstance(row, dict):
            raise DeliveryValidationError('Ugyldig avleveringsregel')
        mid = row.get('metadata_id')
        name = row.get('xml_field')
        accepted = row.get('delivery_values')
        if (mid not in STATUS_PARENTS or mid in definitions or
                not isinstance(name, str) or not re.fullmatch('[A-Za-z][A-Za-z0-9]*', name) or
                not isinstance(accepted, list) or not accepted or
                any(not isinstance(v, str) or not v for v in accepted) or
                len(set(accepted)) != len(accepted)):
            raise DeliveryValidationError('Ugyldig eller duplisert M051-M054-avleveringsregel')
        standard = register.get(mid + '_' + name)
        if (not isinstance(standard, dict) or standard.get('metadata_id') != mid or
                not isinstance(standard.get('values'), list)):
            raise DeliveryValidationError('Ingen entydig produksjonsverdisettkobling for ' + mid)
        production = standard['values']
        if not set(accepted).issubset(set(production)):
            raise DeliveryValidationError('Avleveringsverdi mangler i standardverdisett for ' + mid)
        definitions[mid] = {
            'metadata_id': mid, 'xml_field': name,
            'parent': STATUS_PARENTS[mid],
            'parents': frozenset({STATUS_PARENTS[mid]} | ADDITIONAL_PARENTS.get(mid, set())),
            'production_values': frozenset(production),
            'delivery_values': frozenset(accepted),
            'ordered_delivery_values': tuple(accepted),
            'page': row.get('page'), 'applies_to': str(row.get('applies_to') or ''),
        }
    if set(definitions) != set(STATUS_PARENTS):
        raise DeliveryValidationError('Avleveringsregisteret mangler M051-M054, avbryter uten delresultat')
    return definitions, _hash(rules_path), _hash(values_path), source


def _local(tag: str) -> str:
    return tag.rsplit('}', 1)[-1]


class _HashingReader:
    """Hash bytes in the same single pass used by the XML stream parser."""
    def __init__(self, file):
        self.file = file
        self.sha = sha256()
        self.bytes_read = 0

    def read(self, size=-1):
        block = self.file.read(size)
        if block:
            self.sha.update(block)
            self.bytes_read += len(block)
        return block



def _frame_path(parent: dict | None, tag: str, nth: int) -> str:
    # Namespace-agnostic and sibling-indexed; never infer a missing systemID.
    step = "/*[local-name()='" + tag + "'][" + str(nth) + ']'
    return (parent['xpath'] if parent else '') + step


def _finding(item: dict, status: dict, archive_part_id: str, source_ref: str,
             ordinal: int) -> dict:
    value = status['value']
    std = value in item['production_values']
    test_id = 'DWM-AVLEVERING-' + item['metadata_id']
    msg = (f"{item['metadata_id']} ({item['xml_field']}): verdien {value!r} "
           'er registrert i produksjonsverdisettet, men ikke som tillatt ved avlevering.'
           if std else
           f"{item['metadata_id']} ({item['xml_field']}): verdien {value!r} "
           'finnes verken i registrert produksjonsverdisett eller som tillatt ved avlevering.')
    stable = json.dumps((item['metadata_id'], status['xpath'], status['line'],
                         value, ordinal), ensure_ascii=False, separators=(',', ':'))
    return {
        'finding_uid': sha256(stable.encode('utf-8')).hexdigest(),
        'source': 'DWM avleveringskontroll', 'test_id': test_id,
        'metadata_id': item['metadata_id'], 'severity': 'ERROR',
        'message': msg, 'value': value, 'standard_value': std,
        'delivery_value': False,
        'context': ('Arkivdel systemID: ' + archive_part_id) if archive_part_id else 'Arkivdel: ikke identifisert',
        'file': 'arkivstruktur.xml', 'lines': [status['line']] if status['line'] else [],
        'xpath': status['xpath'], 'object_id': status['object_id'],
        'archive_part_id': archive_part_id,
        'source_ref': source_ref, 'requires_review': True,
    }


def _rule_summary(definition: dict) -> dict:
    return {
        'test_id': 'DWM-AVLEVERING-' + definition['metadata_id'],
        'metadata_id': definition['metadata_id'],
        'xml_field': definition['xml_field'],
        'expected_parent': definition['parent'],
        'applies_to': definition['applies_to'],
        'source_page': definition['page'],
        'allowed_at_delivery': list(definition['ordered_delivery_values']),
        'standard_value_counts': {v: 0 for v in sorted(definition['production_values'])},
        'observed_count': 0, 'in_production_set': 0,
        'outside_production_set': 0,
        'permitted_at_delivery': 0, 'delivery_deviations': 0,
        'status': 'not_observed',
    }


def _source_name(source: Path) -> Path | None:
    if source.is_file() and source.name.lower() == 'arkivstruktur.xml':
        return source
    candidate = source / 'arkivstruktur.xml'
    return candidate if candidate.is_file() else None


def _schema_evidence(version) -> list[dict]:
    return [{'name': str(getattr(item, 'path', '')).replace('\\', '/').rsplit('/', 1)[-1],
             'sha256': str(getattr(item, 'digest', '') or ''),
             'version': getattr(item, 'version', None),
             'status': str(getattr(item, 'status', '') or '')}
            for item in (getattr(version, 'schemas', ()) or ())]


def _not_assessed(version, reason: str, *, source: Path | None = None) -> dict:
    return {
        'model_id': MODEL, 'status': 'not_assessed', 'reason': reason,
        'version': getattr(version, 'version', None),
        'version_evidence_status': getattr(version, 'status', 'unknown'),
        'schema_evidence': _schema_evidence(version),
        'source_xml': str(source) if source else None,
        'finding_count': None, 'rules_checked': 0, 'complete': False,
        'automatic_approval': False, 'requires_professional_review': True,
        'source_reference': {
            'repository': SOURCE_REPOSITORY, 'commit': SOURCE_COMMIT,
            'file': SOURCE_DOCUMENT, 'sha256': SOURCE_DOCUMENT_SHA256,
            'source_status': SOURCE_DOCUMENT_STATUS},
    }


def validate_delivery_values(
        extraction_root: str | Path, output_dir: str | Path, *,
        source_ref: str, cancel: Callable[[], bool] | None = None,
        version_evidence=None,
        rules_path: str | Path = RULES_FILE,
        values_path: str | Path = VALUES_FILE,
) -> dict:
    """Assess v5.0 M051-M054 against full XML and emit all deviations.

    `version_evidence` exists for deterministic unit tests; production callers
    always omit it, so a stored XSD result determines whether rules apply.
    No reviewed decision or source XML is modified.
    """
    root = Path(extraction_root)
    out = Path(output_dir)
    if not out.is_dir() or out.is_symlink():
        raise DeliveryValidationError('Sikker Work-rapportmappe mangler')
    if version_evidence is None:
        from app.noark_xsd_version_v0114_a5 import inspect_source_version
        version_evidence = inspect_source_version(root)
    path = _source_name(root)
    state = getattr(version_evidence, 'status', 'unknown')
    v = getattr(version_evidence, 'version', None)
    if state != 'confirmed' or v != '5.0':
        explanation = (f'XSD-identifikasjon er {state}, versjon {v or "ukjent"}; '
                       'kun kilderegistrerte 5.0-regler finnes i a9. '
                       'Ingen avleveringskontroll er utført.')
        return _not_assessed(version_evidence, explanation, source=path)
    if path is None or path.is_symlink() or not path.is_file():
        return _not_assessed(version_evidence, 'Bekreftet 5.0, men arkivstruktur.xml mangler eller er en lenke.', source=path)
    if cancel is not None and cancel():
        raise DeliveryValidationError('Avleveringskontroll avbrutt: ingen delresultater publisert')
    definitions, rules_sha, values_sha, rule_source = _checked_rules(
        Path(rules_path), Path(values_path))
    if not source_ref or source_ref.startswith('/') or '\\' in source_ref or '..' in source_ref.split('/'):
        raise DeliveryValidationError('Ugyldig Work-relativ funnreferanse')
    pre = path.stat()
    rules_by_field = {(x['xml_field'], parent): x
                      for x in definitions.values() for parent in x['parents']}
    summary = {mid: _rule_summary(definition)
               for mid, definition in sorted(definitions.items())}
    count = 0
    seen = 0
    frames: list[dict[str, Any]] = []
    stage = Path(tempfile.mkdtemp(prefix='.delivery-a9-', dir=out))
    find_out = stage / 'delivery-funn.jsonl'
    csv_out = stage / 'delivery-funn.csv'
    published = False
    try:
        with (path.open('rb') as source,
              find_out.open('w', encoding='utf-8', newline='\n') as jsonl,
              csv_out.open('w', encoding='utf-8', newline='') as csvfile):
            reader = _HashingReader(source)
            writer = csv.DictWriter(csvfile, fieldnames=FINDING_FIELDS,
                                    delimiter=';', lineterminator='\r\n')
            writer.writeheader()
            parser = etree.iterparse(reader, events=('start', 'end'),
                                     resolve_entities=False, load_dtd=False,
                                     no_network=True, huge_tree=False, recover=False)
            for event, element in parser:
                seen += 1
                if seen % PROGRESS_EVERY == 0:
                    if cancel is not None and cancel():
                        raise DeliveryValidationError('Avleveringskontroll avbrutt: ingen delresultater publisert')
                if not isinstance(element.tag, str):
                    continue
                tag = _local(element.tag)
                if event == 'start':
                    if not frames and element.tag != '{' + NOARK_ARCHIVE_NS + '}arkiv':
                        raise DeliveryValidationError('Source XML har ikke Noark 5 arkiv-rotnode med riktig namespace')
                    if len(frames) >= MAX_XML_DEPTH:
                        raise DeliveryValidationError('XML er dypere enn kontrollens parsergrense')
                    parent = frames[-1] if frames else None
                    children = parent['children'] if parent else {}
                    nth = children.get(tag, 0) + 1
                    children[tag] = nth
                    frames.append({'tag': tag, 'xpath': _frame_path(parent, tag, nth),
                                   'children': {}, 'object_id': '', 'pending': []})
                    continue
                if not frames or frames[-1]['tag'] != tag:
                    raise DeliveryValidationError('XML-stakken er inkonsistent')
                frame = frames[-1]
                parent = frames[-2] if len(frames) > 1 else None
                if tag == 'systemID' and parent is not None and len(element) == 0:
                    parent['object_id'] = str(element.text or '').strip()
                if parent is not None and len(element) == 0:
                    definition = rules_by_field.get((tag, parent['tag']))
                    if definition is not None:
                        value = str(element.text or '').strip()
                        if len(value) > MAX_SINGLE_FIELD_CHARS:
                            raise DeliveryValidationError('Feltverdi over sikker parsergrense; ingen avkorting')
                        if len(parent['pending']) >= MAX_DIRECT_STATUS_FIELDS:
                            raise DeliveryValidationError('Uvanlig mange direkte statusfelt i ett XML-objekt')
                        parent['pending'].append({'definition': definition,
                                                  'value': value,
                                                  'line': element.sourceline,
                                                  'xpath': frame['xpath'],
                                                  'object_id': ''})
                # Flush only when the containing archive object ends, so that
                # object systemID is known even if it occurs after the status.
                if frame['pending']:
                    part_id = frame['object_id'] if tag == 'arkivdel' else ''
                    if not part_id:
                        for ancestor in reversed(frames[:-1]):
                            if ancestor['tag'] == 'arkivdel':
                                part_id = ancestor['object_id']
                                break
                    for status in frame['pending']:
                        item = status['definition']
                        cell = summary[item['metadata_id']]
                        value = status['value']
                        cell['observed_count'] += 1
                        inside = value in item['production_values']
                        permitted = value in item['delivery_values']
                        cell['in_production_set' if inside else 'outside_production_set'] += 1
                        if inside:
                            cell['standard_value_counts'][value] += 1
                        cell['permitted_at_delivery' if permitted else 'delivery_deviations'] += 1
                        if not permitted:
                            status['object_id'] = frame['object_id']
                            result = _finding(item, status, part_id, source_ref, count)
                            jsonl.write(json.dumps(result, ensure_ascii=False, separators=(',', ':')) + '\n')
                            # Spreadsheet formula protection only for CSV export.
                            csv_row = {k: result.get(k) for k in FINDING_FIELDS}
                            csv_row['lines'] = ','.join(map(str, result['lines']))
                            for k, value_cell in csv_row.items():
                                value_text = str(value_cell) if value_cell is not None else ''
                                if value_text.lstrip().startswith(('=', '+', '-', '@')):
                                    csv_row[k] = "'" + value_text
                            writer.writerow(csv_row)
                            count += 1
                    frame['pending'].clear()
                frames.pop()
                element.clear()
                parent_element = element.getparent()
                if parent_element is not None:
                    while element.getprevious() is not None:
                        del parent_element[0]
            if frames:
                raise DeliveryValidationError('Ufullstendig XML: kontrollen er ikke komplett')
            source_sha = reader.sha.hexdigest()
            if reader.bytes_read != pre.st_size:
                raise DeliveryValidationError('Kilden har endret størrelse under kontrollen')
        if cancel is not None and cancel():
            raise DeliveryValidationError('Avleveringskontroll avbrutt: ingen delresultater publisert')
        post = path.stat()
        if post.st_size != pre.st_size or post.st_mtime_ns != pre.st_mtime_ns:
            raise DeliveryValidationError('Source er endret under avleveringskontroll')
        for mid, row in summary.items():
            row['status'] = ('not_observed' if row['observed_count'] == 0 else
                             'delivery_deviation' if row['delivery_deviations'] else
                             'no_observed_delivery_deviation')
        result = {
            'model_id': MODEL, 'status': 'completed_with_deviations' if count else 'completed_without_observed_deviations',
            'version': '5.0', 'version_evidence_status': state,
            'schema_evidence': _schema_evidence(version_evidence),
            'generated_utc': datetime.now(timezone.utc).isoformat(timespec='seconds'),
            'source_xml': str(path), 'source_sha256': source_sha,
            'source_bytes': pre.st_size, 'source_mtime_ns': pre.st_mtime_ns,
            'rules_registry_sha256': rules_sha, 'standard_values_sha256': values_sha,
            'rules_checked': len(summary), 'rules': list(summary.values()),
            'finding_count': count, 'complete': True,
            'finding_file': 'delivery-funn.jsonl', 'finding_csv': 'delivery-funn.csv',
            'findings_relative': source_ref,
            'finding_file_sha256': _hash(find_out), 'finding_csv_sha256': _hash(csv_out),
            'automatic_approval': False, 'requires_professional_review': True,
            'rule_source': rule_source,
            'source_reference': {
                'repository': SOURCE_REPOSITORY, 'commit': SOURCE_COMMIT,
                'file': SOURCE_DOCUMENT, 'sha256': SOURCE_DOCUMENT_SHA256,
                'source_status': SOURCE_DOCUMENT_STATUS},
            'limitations': [
                'Resultatet tester registrerte avleveringsbetingelser, ikke hele Noark-standarden.',
                'XSD-validitet, standardverdi og avleveringsbetingelse er separate kontroller.',
                'Avvik er ikke automatisk depotavslag. Uten forekomster er kravets oppfyllelse ikke bekreftet.',
                'Regelgrunnlaget er avledet fra a3 og krever kilde-/faglig QA av kildeordlyd.'
            ],
        }
        (stage / 'delivery-validation.json').write_text(
            json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        # Existing run directory is unique; never overwrite previously published files.
        for name in ('delivery-funn.jsonl', 'delivery-funn.csv', 'delivery-validation.json'):
            destination = out / name
            if destination.exists() or destination.is_symlink():
                raise DeliveryValidationError('Avleveringsutdata eksisterer allerede: ' + name)
        os.replace(find_out, out / 'delivery-funn.jsonl')
        os.replace(csv_out, out / 'delivery-funn.csv')
        os.replace(stage / 'delivery-validation.json', out / 'delivery-validation.json')
        published = True
        return result
    except (OSError, etree.XMLSyntaxError, UnicodeError) as exc:
        raise DeliveryValidationError('Ufullstendig avleveringskontroll; ingen komplett rapport publisert: ' + str(exc)) from exc
    finally:
        for file in stage.iterdir():
            file.unlink(missing_ok=True)
        stage.rmdir()
        if not published:
            # A failed publication never claims to be a complete DWM test.
            (out / 'delivery-validation.json').unlink(missing_ok=True)


def inject_delivery_html(path: str | Path, report: dict) -> None:
    """Append readable, escaped status to the existing depot HTML report."""
    file = Path(path)
    status = report.get('status', 'not_assessed')
    rows = []
    for rule in report.get('rules') or []:
        rows.append('<tr><td>' + escape(rule['metadata_id']) + '</td><td>' +
                    escape(rule['xml_field']) + '</td><td>' +
                    str(rule['observed_count']) + '</td><td>' +
                    str(rule['delivery_deviations']) + '</td><td>' +
                    escape(rule['status']) + '</td></tr>')
    heading = '<section class="section"><h2>DWM – kontroll av avleveringsverdier</h2>'
    intro = ('<p>Noark v' + escape(str(report.get('version') or 'ukjent')) +
             ' · ' + escape(status) + ' · ' +
             'Ingen automatisk godkjenning. Produksjonsverdi er ikke nødvendigvis avleveringsverdi.</p>')
    if status == 'not_assessed':
        body = '<p><strong>Ikke vurdert:</strong> ' + escape(str(report.get('reason') or 'ukjent')) + '</p>'
    else:
        body = ('<p>Komplett antall avleveringsfunn: <strong>' +
                str(report.get('finding_count', 0)) +
                '</strong>. Fullstendige forekomster i <a href="delivery-funn.csv">CSV</a> og '
                '<a href="delivery-funn.jsonl">JSONL</a>.</p>' +
                '<table><thead><tr><th>M-felt</th><th>XML-felt</th><th>Observert</th><th>Avvik</th><th>Kontrollstatus</th></tr></thead><tbody>' +
                ''.join(rows) + '</tbody></table>')
    addition = heading + intro + body + '</section>'
    html = file.read_text(encoding='utf-8')
    if html.count('</body>') != 1:
        raise DeliveryValidationError('Depotrapportens HTML kan ikke suppleres sikkert')
    file.write_text(html.replace('</body>', addition + '</body>'), encoding='utf-8')
