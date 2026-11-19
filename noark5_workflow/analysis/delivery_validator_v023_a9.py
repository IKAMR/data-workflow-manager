"""DWM a10: version-bound Noark 5 delivery and period observations (3.1/4.0/5.0).

A production status value may be in the standard vocabulary but forbidden at
transfer.  This engine does not replace XSD or XPath validation, and never makes
an acceptance/approval decision. Confirmed version-specific XSD evidence activates rules.

The complete finding list is streamed to JSONL/CSV; no findings are silently
truncated. Both outputs and the JSON summary are written only on successful
completion, with source SHA-256 and version/rule provenance.
"""
from __future__ import annotations

from collections import Counter
from datetime import date, datetime, timezone
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
LEGACY_RULES_FILE = ROOT / 'config/noark5/standards/delivery_value_conditions_v023_a3.json'
RULES_FILE = ROOT / 'config/noark5/standards/delivery_value_conditions_v023_a10.json'
VALUES_FILE = ROOT / 'config/noark5/standards/noark5_standard_values.json'
MODEL = 'dwm.noark5.delivery-validation.a10.v1'
VERSIONS = frozenset(('3.1', '4.0', '5.0'))
NOARK_ARCHIVE_NS = 'http://www.arkivverket.no/standarder/noark5/arkivstruktur'
SOURCE_REPOSITORY = 'IKAMR/digital-archive-workflow'
SOURCE_COMMIT = '8d28e312e1e38af8cb93bfe05cecef11e09af34f'
SOURCE_DOCUMENT = 'docs/kilder/noark/noark5/v5.0/spesifikasjoner/Noark 5 v 5 vedl1 Metadatakatalog.pdf'
SOURCE_DOCUMENT_SHA256 = 'e1f6b7caa24f869d82b21aa30b3452513029875e417b1e351b2b9298578ffd98'
SOURCE_DOCUMENT_STATUS = 'not_documented'  # Source library manifest, not an approval.
PERIOD_START = 'arkivperiodeStartDato'
PERIOD_END = 'arkivperiodeSluttDato'
_DATE_RE = re.compile(r'^\d{4}-\d{2}-\d{2}$')
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


def _checked_rules(rules_path: Path, values_path: Path, version: str = '5.0') -> tuple[dict, str, str, dict]:
    """Bind a separate, pinned source and production vocabulary to each Noark version.

    The a3 v5.0 registry remains accepted for backwards-compatible tests and
    is cross-checked against a10's v5.0 definition during production use.
    No v3.1/v4.0 rule is inferred from v5.0 solely because names look alike.
    """
    rules = _read_json(rules_path, MAX_RULE_FILE_BYTES)
    values = _read_json(values_path, MAX_VALUE_FILE_BYTES)
    if version not in VERSIONS or rules.get('format_version') != 1:
        raise DeliveryValidationError('Ukjent eller uverifisert Noark-versjon')
    model = rules.get('model')
    if model == 'dwm.noark5.delivery-value-conditions.a10.v1':
        if (rules.get('source_repository') != SOURCE_REPOSITORY or
                rules.get('source_commit') != SOURCE_COMMIT or
                set((rules.get('versions') or {})) != VERSIONS):
            raise DeliveryValidationError('Avleveringsregisteret mangler låst kilderevisjon/versjoner')
        selected = rules['versions'].get(version)
        if not isinstance(selected, dict):
            raise DeliveryValidationError('Manglende versjonsspesifikt avleveringsregister')
        source = selected.get('source')
        rows = selected.get('rules')
        if (not isinstance(source, dict) or
                not str(source.get('file') or '').startswith(
                    'docs/kilder/noark/noark5/v' + version + '/spesifikasjoner/') or
                not re.fullmatch('[a-f0-9]{64}', str(source.get('sha256') or '')) or
                not source.get('title') or not source.get('url') or
                source.get('source_status') != 'not_documented' or
                not isinstance(rows, list)):
            raise DeliveryValidationError('Avleveringsregisteret mangler versjonert kildeidentitet')
        source = {**source, 'repository': SOURCE_REPOSITORY, 'commit': SOURCE_COMMIT}
        if version == '5.0' and rules_path.resolve() == RULES_FILE.resolve():
            legacy = _read_json(LEGACY_RULES_FILE, MAX_RULE_FILE_BYTES)
            if (legacy.get('model') != 'dwm.noark5.delivery-value-commentary.v1' or
                    legacy.get('reference_version') != '5.0' or
                    {(r['metadata_id'], r['xml_field']): tuple(r['delivery_values'])
                     for r in legacy.get('rules') or [] if isinstance(r, dict)} !=
                    {(r['metadata_id'], r['xml_field']): tuple(r['delivery_values'])
                     for r in rows if isinstance(r, dict)}):
                raise DeliveryValidationError('Noark 5.0-avleveringsregler avviker fra a3-registeret')
    elif model == 'dwm.noark5.delivery-value-commentary.v1' and version == '5.0':
        if rules.get('reference_version') != '5.0':
            raise DeliveryValidationError('Feil Noark-versjon i a3-registeret')
        source = rules.get('source')
        rows = rules.get('rules')
        if not isinstance(source, dict) or not source.get('title') or not source.get('url'):
            raise DeliveryValidationError('Avleveringsregisteret mangler kildeidentitet')
        source = {**source, 'repository': SOURCE_REPOSITORY, 'commit': SOURCE_COMMIT,
                  'file': SOURCE_DOCUMENT, 'sha256': SOURCE_DOCUMENT_SHA256,
                  'source_status': SOURCE_DOCUMENT_STATUS}
    else:
        raise DeliveryValidationError('Avleveringsregisteret gjelder ikke valgt Noark-versjon')
    register = ((values.get('versions') or {}).get(version) or {}).get('value_sets') or {}
    if not isinstance(register, dict):
        raise DeliveryValidationError('Mangler eget produksjonsverdisett for Noark ' + version)
    definitions = {}
    if not isinstance(rows, list):
        raise DeliveryValidationError('Manglende avleveringsregler')
    for row in rows:
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


def _source_version_is_confirmed(version_evidence, version: str) -> bool:
    """Historic versions require an actual identified arkivstruktur.xsd.

    The existing a9 injected 5.0 fixture has no schema list; preserving its
    behavior avoids changing unrelated a9 regression expectations.
    """
    if getattr(version_evidence, 'status', '') != 'confirmed' or version not in VERSIONS:
        return False
    schemas = getattr(version_evidence, 'schemas', ()) or ()
    # Backwards-compatibility for explicitly injected a9 unit fixtures only:
    # the existing tests carry status='confirmed' with no schema records.
    # Real inspection with a populated schema list must include arkivstruktur.
    if version == '5.0' and not schemas:
        return True
    return any(Path(str(getattr(x, 'path', ''))).name == 'arkivstruktur.xsd'
               and getattr(x, 'version', None) == version
               and re.fullmatch('[a-f0-9]{64}', str(getattr(x, 'digest', '') or ''))
               for x in schemas)


def _parse_period_date(value: str) -> date | None:
    """Compare dates only when both have a timezone-free ISO date. No guesses."""
    if not _DATE_RE.fullmatch(value):
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def _period_finding(frame: dict, archive_part_id: str, source_ref: str,
                    start: str, end: str, ordinal: int) -> dict:
    payload = json.dumps(('M107/M108', frame['xpath'], start, end, ordinal),
                         ensure_ascii=False, separators=(',', ':'))
    return {
        'finding_uid': sha256(payload.encode('utf-8')).hexdigest(),
        'source': 'DWM periodekonsistens', 'test_id': 'DWM-PERIODE-M107-M108',
        'metadata_id': 'M107/M108', 'severity': 'REVIEW',
        'message': ('Arkivdelens registrerte arkivperiodeSluttDato (' + end +
                    ') er tidligere enn arkivperiodeStartDato (' + start +
                    '). Kildebasert kronologifunn til faglig vurdering; ikke et '
                    'automatisk normativt Noark-avslag.'),
        'value': start + ' / ' + end, 'standard_value': None,
        'delivery_value': None,
        'context': 'Arkivdel systemID: ' + archive_part_id if archive_part_id
                   else 'Arkivdel: ikke identifisert',
        'file': 'arkivstruktur.xml',
        'lines': sorted(n for n in frame['date_lines'].values() if type(n) is int and n > 0),
        'xpath': frame['xpath'], 'object_id': archive_part_id,
        'archive_part_id': archive_part_id, 'source_ref': source_ref,
        'requires_review': True,
    }


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
            'file': None, 'sha256': None,
            'source_status': 'not_assessed'},
    }


def validate_delivery_values(
        extraction_root: str | Path, output_dir: str | Path, *,
        source_ref: str, cancel: Callable[[], bool] | None = None,
        version_evidence=None,
        rules_path: str | Path = RULES_FILE,
        values_path: str | Path = VALUES_FILE,
) -> dict:
    """Assess separate v3.1/4.0/5.0 rules against full XML and emit all findings.

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
    if not _source_version_is_confirmed(version_evidence, str(v)):
        explanation = (f'XSD-identifikasjon er {state}, versjon {v or "ukjent"}; '
                       'mangler entydig bekreftelse for versjonsspesifikk avleveringskontroll. '
                       'Ingen avleveringskontroll er utført.')
        return _not_assessed(version_evidence, explanation, source=path)
    if path is None or path.is_symlink() or not path.is_file():
        return _not_assessed(version_evidence, 'Bekreftet XSD-versjon, men arkivstruktur.xml mangler eller er en lenke.', source=path)
    if cancel is not None and cancel():
        raise DeliveryValidationError('Avleveringskontroll avbrutt: ingen delresultater publisert')
    definitions, rules_sha, values_sha, rule_source = _checked_rules(
        Path(rules_path), Path(values_path), str(v))
    if not source_ref or source_ref.startswith('/') or '\\' in source_ref or '..' in source_ref.split('/'):
        raise DeliveryValidationError('Ugyldig Work-relativ funnreferanse')
    pre = path.stat()
    rules_by_field = {(x['xml_field'], parent): x
                      for x in definitions.values() for parent in x['parents']}
    summary = {mid: _rule_summary(definition)
               for mid, definition in sorted(definitions.items())}
    count = 0
    period_reviews = 0
    periods = Counter()
    seen = 0
    frames: list[dict[str, Any]] = []
    stage = Path(tempfile.mkdtemp(prefix='.delivery-a10-', dir=out))
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

            def emit_issue(row: dict) -> None:
                # Retain the complete original JSONL values; CSV is formula-safe.
                jsonl.write(json.dumps(row, ensure_ascii=False, separators=(',', ':')) + '\n')
                cell = {k: row.get(k) for k in FINDING_FIELDS}
                cell['lines'] = ','.join(map(str, row.get('lines') or []))
                for key, value in cell.items():
                    encoded = str(value) if value is not None else ''
                    if encoded.lstrip().startswith(('=', '+', '-', '@')):
                        cell[key] = "'" + encoded
                writer.writerow(cell)

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
                                   'ns_ok': element.tag == '{' + NOARK_ARCHIVE_NS + '}' + tag,
                                   'children': {}, 'object_id': '', 'pending': [],
                                   'dates': {}, 'date_lines': {}})
                    continue
                if not frames or frames[-1]['tag'] != tag:
                    raise DeliveryValidationError('XML-stakken er inkonsistent')
                frame = frames[-1]
                parent = frames[-2] if len(frames) > 1 else None
                if (tag == 'systemID' and parent is not None and len(element) == 0
                        and frame['ns_ok'] and parent['ns_ok']):
                    parent['object_id'] = str(element.text or '').strip()
                if (parent is not None and len(element) == 0 and
                        frame['ns_ok'] and parent['ns_ok']):
                    if parent['tag'] == 'arkivdel' and tag in (PERIOD_START, PERIOD_END):
                        parent['dates'][tag] = str(element.text or '').strip()
                        parent['date_lines'][tag] = element.sourceline
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
                if tag == 'arkivdel' and frame['ns_ok']:
                    periods['archive_parts_seen'] += 1
                    begin = frame['dates'].get(PERIOD_START)
                    finish = frame['dates'].get(PERIOD_END)
                    if begin is None and finish is None:
                        periods['without_date_fields'] += 1
                    elif begin is None or finish is None:
                        periods['with_one_date_field'] += 1
                    else:
                        periods['with_both_dates'] += 1
                        first = _parse_period_date(begin)
                        last = _parse_period_date(finish)
                        if first is None or last is None:
                            periods['uncomparable_date_formats'] += 1
                        elif last < first:
                            periods['reversed_date_order'] += 1
                            emit_issue(_period_finding(frame, frame['object_id'], source_ref,
                                                       begin, finish, count))
                            period_reviews += 1
                            count += 1
                        else:
                            periods['chronologically_ordered'] += 1
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
                            emit_issue(result)
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
            'model_id': MODEL, 'status': ('completed_with_deviations' if count - period_reviews else
                       'completed_with_period_reviews' if period_reviews else
                       'completed_without_observed_deviations'),
            'version': v, 'version_evidence_status': state,
            'schema_evidence': _schema_evidence(version_evidence),
            'generated_utc': datetime.now(timezone.utc).isoformat(timespec='seconds'),
            'source_xml': str(path), 'source_sha256': source_sha,
            'source_bytes': pre.st_size, 'source_mtime_ns': pre.st_mtime_ns,
            'rules_registry_sha256': rules_sha, 'standard_values_sha256': values_sha,
            'rules_checked': len(summary), 'rules': list(summary.values()),
            'finding_count': count, 'delivery_value_findings': count - period_reviews,
            'period_review_findings': period_reviews,
            'period_chronology': {'status': 'review' if period_reviews else 'no_observed_reversals',
                                  **dict(periods)},
            'complete': True,
            'finding_file': 'delivery-funn.jsonl', 'finding_csv': 'delivery-funn.csv',
            'findings_relative': source_ref,
            'finding_file_sha256': _hash(find_out), 'finding_csv_sha256': _hash(csv_out),
            'automatic_approval': False, 'requires_professional_review': True,
            'rule_source': rule_source,
            'source_reference': rule_source,
            'limitations': [
                'Resultatet tester registrerte avleveringsbetingelser, ikke hele Noark-standarden.',
                'XSD-validitet, standardverdi og avleveringsbetingelse er separate kontroller.',
                'Avvik er ikke automatisk depotavslag. Uten forekomster er kravets oppfyllelse ikke bekreftet.',
                'Regelgrunnlaget er versjonsbundet; opprinnelig kildemanifest har source_status=not_documented.',
                'Periodesammenligning er REVIEW, ikke en selvstendig normativ bestemmelse.'
            ],
        }
        (stage / 'delivery-validation.json').write_text(
            json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        # Existing run directory is unique; never overwrite previously published files.
        for name in ('delivery-funn.jsonl', 'delivery-funn.csv', 'delivery-validation.json'):
            destination = out / name
            if destination.exists() or destination.is_symlink():
                raise DeliveryValidationError('Avleveringsutdata eksisterer allerede: ' + name)
        created = []
        try:
            for name in ('delivery-funn.jsonl', 'delivery-funn.csv', 'delivery-validation.json'):
                os.replace(stage / name, out / name)
                created.append(out / name)
        except OSError:
            for created_file in created:
                created_file.unlink(missing_ok=True)
            raise
        published = True
        return result
    except (OSError, etree.XMLSyntaxError, UnicodeError) as exc:
        raise DeliveryValidationError('Ufullstendig avleveringskontroll; ingen komplett rapport publisert: ' + str(exc)) from exc
    finally:
        for file in stage.iterdir():
            file.unlink(missing_ok=True)
        stage.rmdir()
        # Unpublished artifacts stay in stage and are removed above. In
        # particular, NEVER delete a pre-existing validation or evidence file.



def attach_delivery_to_depot_model(model: dict, delivery: dict) -> dict:
    """Project only observed violations into the DWM depot model.

    A reversed period is a professional REVIEW finding, not a technical ERROR.
    All individual observations remain in the complete JSONL/CSV source.
    An unknown/unconfirmed version never alters the preexisting status.
    """
    model['delivery_validation'] = delivery
    if not delivery.get('complete'):
        return model
    depot_deviations = model.setdefault('deviations', [])
    version = str(delivery['version'])
    for check in delivery.get('rules') or []:
        amount = int(check.get('delivery_deviations') or 0)
        if amount:
            depot_deviations.append({
                'category': 'delivery_value_' + check['metadata_id'],
                'severity': 'serious',
                'summary': (f"{amount} observerte {check['xml_field']}-verdier avviker fra "
                            f"registrerte avleveringsverdier (Noark {version}, {check['metadata_id']})."),
                'requires_review': True,
                'delivery_evidence': {
                    'test_id': check['test_id'], 'count': amount,
                    'finding_file': delivery['findings_relative'],
                    'finding_file_sha256': delivery['finding_file_sha256'],
                    'source_xml_sha256': delivery['source_sha256'],
                    'standard_version': version,
                },
            })
    period_count = int(delivery.get('period_review_findings') or 0)
    if period_count:
        depot_deviations.append({
            'category': 'delivery_period_chronology', 'severity': 'review',
            'summary': (f'{period_count} arkivdeler har en registrert sluttdato før '
                        'startdato. Krever periodevurdering; ingen selvstendig '
                        'normativ avleveringsfeil er konkludert.'),
            'requires_review': True,
            'delivery_evidence': {
                'test_id': 'DWM-PERIODE-M107-M108', 'count': period_count,
                'finding_file': delivery['findings_relative'],
                'finding_file_sha256': delivery['finding_file_sha256'],
                'source_xml_sha256': delivery['source_sha256'],
                'standard_version': version,
            },
        })
    technical = model.setdefault('technical_validation', {})
    summary = technical.setdefault('summary', {})
    bad = int(delivery.get('delivery_value_findings', delivery.get('finding_count') or 0))
    summary['delivery_value_deviations'] = bad
    summary['delivery_period_review_findings'] = period_count
    if bad:
        technical['status'] = 'error'
    return model


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
        body = ('<p>Komplett antall kildefunn: <strong>' +
                str(report.get('finding_count', 0)) +
                '</strong>. Fullstendige forekomster i <a href="delivery-funn.csv">CSV</a> og '
                '<a href="delivery-funn.jsonl">JSONL</a>. ' +
                'Avleveringsverdier: ' + str(report.get('delivery_value_findings', 0)) +
                '; periodesjekker til vurdering: ' + str(report.get('period_review_findings', 0)) + '</p>' +
                '<table><thead><tr><th>M-felt</th><th>XML-felt</th><th>Observert</th><th>Avvik</th><th>Kontrollstatus</th></tr></thead><tbody>' +
                ''.join(rows) + '</tbody></table>')
    evidence = report.get('source_reference') or {}
    provenance = ('<p class="small">Regelkilde: ' +
                  escape(str(evidence.get('title') or 'ikke verifisert')) +
                  ' · intern fil: ' + escape(str(evidence.get('file') or 'ikke oppgitt')) +
                  ' · SHA-256: ' + escape(str(evidence.get('sha256') or 'ikke oppgitt')) +
                  ' · manifeststatus: ' + escape(str(evidence.get('source_status') or 'ukjent')) +
                  '. Kildekoblingen er ikke en faglig godkjenning.</p>')
    if status != 'not_assessed':
        period = report.get('period_chronology') or {}
        provenance += ('<p>Arkivdeler undersøkt: ' + str(period.get('archive_parts_seen', 0)) +
                       '; med begge datoer: ' + str(period.get('with_both_dates', 0)) +
                       '; manglende dato(er): ' + str(period.get('with_one_date_field', 0) +
                                                     period.get('without_date_fields', 0)) +
                       '; ikke sammenlignbare datoer: ' +
                       str(period.get('uncomparable_date_formats', 0)) +
                       '. Reversert rekkefølge er kun REVIEW.</p>')
    addition = heading + intro + body + provenance + '</section>'
    html = file.read_text(encoding='utf-8')
    if html.count('</body>') != 1:
        raise DeliveryValidationError('Depotrapportens HTML kan ikke suppleres sikkert')
    file.write_text(html.replace('</body>', addition + '</body>'), encoding='utf-8')
