"""Read-only Noark 5 source/XSD/metadata/requirements/XPath QA matrix.

Versioned first-party reference is the checked-out IKAMR/digital-archive-workflow
collection. This indexes *candidate evidence*, not complete normative clauses
or proven Saxon/lxml semantic parity. Nothing in this module edits sources,
XSDs, original XML, or normative registries.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import csv
from hashlib import sha256
import io
import json
from pathlib import Path
import re
from typing import Any
from zipfile import ZipFile, BadZipFile

from app.noark5_spec_xsd_trace_v021_a6 import build_trace, VERSIONS, XSD_NAMES
from app.noark5_xpath_metadata_qa_v021_a4 import _xpath_field_mentioned
from app.noark5_source_document_reader_v021_a7 import (
    M_ID, REQUIREMENT_ID, read_source_document, manifest_sha_status,
)

SOURCE_SUBTREE = Path('docs/kilder/noark/noark5')
MANIFEST_REL = Path('docs/kilder/noark/SOURCE-MANIFEST.json')
SIGNATURES_REL = Path('config/noark5/standards/noark5_xsd_signatures_v0114_a5.json')
CATALOG_REL = Path('config/noark5/tests/xpath_catalog_2026_05_26.json')
MAX_DOCUMENT_BYTES = 15_000_000
MAX_DOCUMENT_SECTIONS = 250_000
MAX_DOCUMENT_REFERENCES_PER_METADATA = 10
MAX_REQUIREMENT_NUMBER_EXAMPLES = 80
MAX_NUMBERED_TEXT_CANDIDATES_PER_VERSION = 800
MAX_REPORT_BYTES = 20_000_000
REPORT_TYPE = 'noark5_a7_source_xsd_requirement_candidate_matrix_not_conformance'
REPORT_FILES = ('noark5-a7-matrix.json', 'noark5-a7-summary.md',
                'noark5-a7-metadata.csv', 'noark5-a7-requirements.csv')


def _json(path: Path) -> dict:
    data = path.read_bytes()
    if len(data) > MAX_REPORT_BYTES:
        raise ValueError(f'JSON overstiger sikkerhetsgrensen: {path}')
    obj = json.loads(data.decode('utf-8-sig'))
    if not isinstance(obj, dict):
        raise ValueError(f'Ugyldig JSON-objekt: {path}')
    return obj


def _manifest_index(source: Path) -> dict[str, dict]:
    manifest = _json(source / MANIFEST_REL)
    entries = manifest.get('files')
    if not isinstance(entries, list):
        raise ValueError('Ukjent SOURCE-MANIFEST format')
    by_path = {}
    for obj in entries:
        name = obj.get('path')
        if not isinstance(name, str) or not name or name in by_path:
            raise ValueError('Duplisert/ugyldig kilde i SOURCE-MANIFEST')
        by_path[name] = obj
    return by_path


def _schema_identity(source: Path, dwm: Path, manifest: dict[str, dict]) -> tuple[list[dict], list[dict]]:
    known = _json(dwm / SIGNATURES_REL)
    signatures = {(x.get('version'), x.get('filename')): x.get('sha256')
                  for x in known.get('signatures', [])}
    rows = []
    issues = []
    for version in VERSIONS:
        for filename in XSD_NAMES:
            rel = f'noark5/v{version}/schemas/{filename}'
            path = source / 'docs/kilder/noark' / rel
            source_manifest = manifest.get(rel) or {}
            expect = source_manifest.get('sha256')
            raw = path.read_bytes()  # build_trace has already parsed all 15 files
            status = manifest_sha_status(raw, expect)
            signed = signatures.get((version, filename))
            record = {
                'noark_version': version, 'file': rel,
                'raw_sha256': sha256(raw).hexdigest(), 'manifest_sha256': expect,
                'dwm_signature_sha256': signed, 'source_status': source_manifest.get('source_status'),
                'identity': status,
                'dwm_signature_matches_manifest': bool(expect and signed == expect),
                'schema_xsd_parsing_completed': True,
                'noark_normative_conformance_verified': False,
            }
            rows.append(record)
            if status not in ('identical_bytes', 'matches_original_after_restoring_crlf'):
                issues.append({'severity': 'FEIL', 'kind': 'xsd_identity_conflict',
                               'version': version, 'source': rel, 'status': status})
            if not record['dwm_signature_matches_manifest']:
                issues.append({'severity': 'FEIL', 'kind': 'dwm_xsd_signature_manifest_conflict',
                               'version': version, 'source': rel})
    return rows, issues


def _document_index(source: Path, manifest: dict[str, dict], *, scan_text: bool) -> tuple[dict, dict, list]:
    """Index source mentions by exact file/paragraph/page, never invent requirements.

    PDF page numbers are from the PDF text layer. DOCX paragraph numbers and
    XLSX sheet/row coordinates are extraction locations, not printed page nos.
    """
    sources: dict[str, list[dict]] = defaultdict(list)
    numbered: dict[str, list[dict]] = defaultdict(list)
    numbered_counts: Counter = Counter()
    per_document_mid: Counter = Counter()
    inventory: dict[str, list[dict]] = {v: [] for v in VERSIONS}
    issues: list[dict] = []
    for version in VERSIONS:
        prefix = f'noark5/v{version}/spesifikasjoner/'
        expected = [(rel, entry) for rel, entry in manifest.items()
                    if rel.startswith(prefix) and Path(rel).suffix.lower() in ('.pdf', '.docx', '.xlsx')]
        def review_order(item):
            name = Path(item[0]).name.casefold()
            # Metadata catalogue first, then object catalogue, then the main
            # standard. Keep more than one actual document as candidate evidence.
            weight = (0 if 'vedl1' in name or 'vedlegg 1' in name
                      else 1 if 'vedl2' in name or 'vedlegg 2' in name
                      else 2 if 'tabelloversikt' in name else 3)
            return weight, name
        expected.sort(key=review_order)
        for rel, manifest_entry in expected:
            root = (source / 'docs/kilder/noark').resolve()
            path = (root / rel).resolve()
            if not path.is_relative_to(root):
                raise ValueError('Ugyldig kildefilsti i SOURCE-MANIFEST')
            row = {'noark_version': version, 'file': rel,
                   'manifest_sha256': manifest_entry.get('sha256'),
                   'manifest_source_status': manifest_entry.get('source_status'),
                   'text_extractor': 'not_read_requested' if not scan_text else 'pending',
                   'readable_sections': 0, 'metadata_ids_mentioned': 0,
                   'requirement_number_lexical_examples': [], 'normative_review_completed': False}
            if not path.is_file():
                row['text_extractor'] = 'source_file_missing'
                issues.append({'severity': 'FEIL', 'kind': 'specification_file_missing',
                               'version': version, 'source': rel})
                inventory[version].append(row)
                continue
            if path.stat().st_size > MAX_DOCUMENT_BYTES:
                row['text_extractor'] = 'source_file_too_large_to_parse'
                issues.append({'severity': 'WARNING', 'kind': 'specification_extraction_skipped',
                               'version': version, 'source': rel})
                inventory[version].append(row)
                continue
            raw = path.read_bytes()
            row['raw_sha256'] = sha256(raw).hexdigest()
            row['source_hash_verified'] = row['raw_sha256'] == manifest_entry.get('sha256')
            if not row['source_hash_verified']:
                issues.append({'severity': 'FEIL', 'kind': 'specification_hash_conflict',
                               'version': version, 'source': rel})
            if scan_text:
                if path.suffix.lower() in ('.docx', '.xlsx'):
                    try:
                        with ZipFile(path) as archive:
                            if sum(x.file_size for x in archive.infolist()) > 80_000_000:
                                raise ValueError('Utpakket OOXML-innhold er for stort')
                    except (OSError, ValueError, BadZipFile) as exc:
                        row['text_extractor'] = f'OOXML_parse_skipped:{type(exc).__name__}'
                        issues.append({'severity': 'WARNING', 'kind': 'specification_text_unavailable',
                                       'version': version, 'source': rel})
                        inventory[version].append(row)
                        continue
                try:
                    sections, parser = read_source_document(path)
                except (OSError, ValueError, BadZipFile) as exc:
                    sections, parser = [], f'parse_error:{type(exc).__name__}'
                row['text_extractor'] = parser
                if len(sections) > MAX_DOCUMENT_SECTIONS:
                    row['text_extractor'] = 'too_many_sections_for_safe_index'
                    issues.append({'severity': 'WARNING', 'kind': 'specification_extraction_skipped',
                                   'version': version, 'source': rel})
                    sections = []
                elif not sections or not any(content.strip() for _, content in sections):
                    issues.append({'severity': 'WARNING', 'kind': 'specification_text_unavailable',
                                   'version': version, 'source': rel, 'extractor': parser})
                else:
                    lexical_numbers: set[str] = set()
                    seen_ids: set[str] = set()
                    for where, body in sections:
                        if not body or not body.strip():
                            continue
                        row['readable_sections'] += 1
                        found = set(M_ID.findall(body))
                        seen_ids.update(found)
                        lexical_numbers.update(REQUIREMENT_ID.findall(body))
                        # Numbered paragraphs/headings may be ordinary section
                        # numbers. They are candidates ONLY, never new rules.
                        for token in sorted(set(REQUIREMENT_ID.findall(body))):
                            key = f'{version}:{token}'
                            if (numbered_counts[version] >= MAX_NUMBERED_TEXT_CANDIDATES_PER_VERSION
                                    or len(numbered[key]) >= 2):
                                continue
                            compact = re.sub(r'\s+', ' ', body).strip()
                            pos = compact.find(token)
                            start, stop = max(0,pos-60), min(len(compact),pos+180)
                            numbered_counts[version] += 1
                            numbered[key].append({
                                'source': rel, 'location': where,
                                'snippet': ('...' if start else '') + compact[start:stop]
                                           + ('...' if stop < len(compact) else ''),
                                'source_sha256': row['raw_sha256'],
                                'kind': 'numbered_text_candidate_not_verified_requirement',
                            })
                        for mid in sorted(found):
                            key = f'{version}:{mid}'
                            if (len(sources[key]) >= MAX_DOCUMENT_REFERENCES_PER_METADATA
                                    or per_document_mid[(version, mid, rel)] >= 2):
                                continue
                            per_document_mid[(version, mid, rel)] += 1
                            passage = re.sub(r'\s+', ' ', body).strip()
                            position = next((m.start() for m in M_ID.finditer(passage)
                                             if m.group(0) == mid), 0)
                            start = max(0, position - 85)
                            end = min(len(passage), position + 175)
                            snippet = ('...' if start else '') + passage[start:end] + ('...' if end < len(passage) else '')
                            sources[key].append({
                                'file': rel, 'location': where, 'source_sha256': row['raw_sha256'],
                                'excerpt': snippet, 'kind': 'lexical_M_id_mention_not_normative_requirement',
                                'is_pdf_page_reference': where.startswith('page'),
                                'source_hash_verified': row['source_hash_verified'],
                            })
                    row['metadata_ids_mentioned'] = len(seen_ids)
                    row['requirement_number_lexical_examples'] = sorted(lexical_numbers)[:MAX_REQUIREMENT_NUMBER_EXAMPLES]
            inventory[version].append(row)
    return dict(sources), dict(numbered), inventory, issues


def _value_set_index(dwm: Path) -> dict[str, dict[str, dict]]:
    obj = _json(dwm / 'config/noark5/standards/noark5_standard_values.json')
    return {version: {row['metadata_id']: {'id': key, 'values': row.get('values', [])}
                      for key, row in obj['versions'][version]['value_sets'].items()
                      if 'metadata_id' in row}
            for version in VERSIONS}


def _catalogue_connections(dwm: Path) -> dict[str, dict[str, list[dict]]]:
    catalogue = _json(dwm / CATALOG_REL)
    linked: dict[str, dict[str, list[dict]]] = {v: defaultdict(list) for v in VERSIONS}
    for test in catalogue.get('tests', []):
        for check in test.get('standard_value_checks', []) or []:
            set_id = str(check.get('value_set_id') or '')
            mid = re.match(r'^(M\d{3})_', set_id)
            if not mid:
                continue
            for version in VERSIONS:
                if version in test.get('noark_versions', []) and version in check.get('versions', []):
                    linked[version][mid.group(1)].append({
                        'test_id': test.get('test_id'), 'reference_type': 'explicit_value_set_check',
                        'value_set_id': set_id, 'metric_id': check.get('metric_id'),
                        'not_normative_requirement_pass': True,
                    })
    return linked


def _diffs(version_map: dict[str, list[dict]]) -> list[dict]:
    keys = {v: {r['metadata_id']: r for r in version_map[v]} for v in VERSIONS}
    out = []
    fields = ('type_name', 'xsd_declared_kind', 'restriction_base',
              'enumeration_literals', 'min_length', 'patterns')
    for mid in sorted(set().union(*(set(row) for row in keys.values()))):
        for a, b in (('3.1', '4.0'), ('4.0', '5.0')):
            x, y = keys[a].get(mid), keys[b].get(mid)
            if x is None or y is None:
                out.append({'metadata_id': mid, 'from': a, 'to': b,
                            'changed': ['presence'], 'from_present': bool(x), 'to_present': bool(y)})
            else:
                diff = [key for key in fields if x.get(key) != y.get(key)]
                if diff:
                    out.append({'metadata_id': mid, 'from': a, 'to': b,
                                'changed': diff,
                                'from_values': {f: x.get(f) for f in diff},
                                'to_values': {f: y.get(f) for f in diff},
                                'technical_xsd_change_not_normative_interpretation': True})
    return out


def build_matrix(source_root: Path | str, dwm_root: Path | str, *,
                 source_commit: str | None = None, scan_documents: bool = True) -> dict[str, Any]:
    source, dwm = Path(source_root).resolve(), Path(dwm_root).resolve()
    if source == dwm or source in dwm.parents or dwm in source.parents:
        raise ValueError('Kilde- og DWM-repositorium må være adskilt')
    manifest = _manifest_index(source)
    trace = build_trace(source, dwm, source_commit=source_commit)
    schemas, issues = _schema_identity(source, dwm, manifest)
    if not trace['source_checkout_commit_verified']:
        issues.append({'severity': 'WARNING', 'kind': 'source_checkout_revision_unverified',
                       'version': None, 'source': 'IKAMR/digital-archive-workflow'})
    elif not trace['source_commit_matches_registry']:
        issues.append({'severity': 'WARNING', 'kind': 'source_revision_differs_from_pinned',
                       'version': None, 'source': 'IKAMR/digital-archive-workflow'})
    snippets, numbered, files, doc_issues = _document_index(source, manifest, scan_text=scan_documents)
    issues.extend(doc_issues)
    value_sets = _value_set_index(dwm)
    explicit_checks = _catalogue_connections(dwm)
    versions = {}
    raw_rows = {}
    for version in VERSIONS:
        v = trace['versions'][version]
        raw_rows[version] = v['rows']
        rows = []
        for row in v['rows']:
            mid = row['metadata_id']
            standard = value_sets[version].get(mid)
            actual_enumerations = row.get('enumeration_literals', [])
            value_mismatch = bool(actual_enumerations and standard
                                  and actual_enumerations != standard['values'])
            ids = [x['test_id'] for x in row['xpath_lexical_candidates']]
            registered = bool(row['registered_in_dwm_metadata'])
            refs = snippets.get(f'{version}:{mid}', [])
            schema_conflict = any(x['noark_version'] == version and x['identity'] not in
                                  ('identical_bytes', 'matches_original_after_restoring_crlf')
                                  for x in schemas)
            if schema_conflict:
                severity, cause = 'FEIL', 'source_xsd_identity_conflict'
            elif value_mismatch:
                severity, cause = 'WARNING', 'dwm_value_list_differs_from_xsd_qa'
            elif not registered:
                severity, cause = 'WARNING', 'xsd_metadata_not_registered_in_dwm'
            elif not ids:
                severity, cause = 'NOTE', 'no_lexical_xpath_candidate_not_proof_of_missing_control'
            else:
                severity, cause = 'NOTE', 'lexical_xpath_candidate_not_implementation_proof'
            rows.append({**row,
                'noark_version': version,
                'source_file': f'noark5/v{version}/schemas/metadatakatalog.xsd',
                'source_sha256': v['source_xsd_sha256']['metadatakatalog.xsd'],
                'document_references': refs,
                'document_references_are_only_candidates': True,
                'value_set_reference': standard,
                'value_set_mismatch_from_xsd': value_mismatch,
                'explicit_value_set_test_references': explicit_checks[version].get(mid, []),
                'xpath_lexical_test_ids': sorted(set(ids)),
                'qa_severity': severity, 'qa_reason': cause,
                'normative_validation_verified': False,
            })
        requirement_rows = []
        requirement_data = _json(dwm / 'config/noark5/standards/requirements' / f'{version}.json')
        for req in requirement_data.get('requirements', []):
            field = str(req.get('xml_field_name') or '')
            mid = req.get('related_metadata_id') or req.get('metadata_id')
            candidates = []
            if field:
                for x in rows:
                    if x['metadata_id'] == mid:
                        candidates = x['xpath_lexical_test_ids']
                        break
            direct = bool((req.get('extract_validation') or {}).get('directly_testable_from_extract'))
            implemented = (req.get('extract_validation') or {}).get('implemented_as_dwm_control') is True
            if direct and not implemented:
                severity, cause = 'WARNING', 'extract_testable_requirement_without_verified_dwm_control'
            elif not direct:
                severity, cause = 'NOTE', 'functional_requirement_not_verifiable_from_static_extract'
            else:
                severity, cause = 'NOTE', 'implementation_flag_not_independent_conformance_proof'
            requirement_rows.append({**req,
                'noark_version': version,
                'metadata_id': mid,
                'document_references': snippets.get(f'{version}:{mid}', []) if mid else [],
                'xpath_lexical_test_ids': candidates,
                'qa_severity': severity, 'qa_reason': cause,
                'normative_validation_verified': False,
                'source_document_text_reviewed_for_rule': False,
            })
        counts = Counter(r['qa_severity'] for r in rows)
        rc = Counter(r['qa_severity'] for r in requirement_rows)
        versions[version] = {
            'xsd_metadata_types': v['xsd_metadata_type_definitions'],
            'registered_metadata': v['dwm_registered_metadata_ids'],
            'registered_requirements': len(requirement_rows),
            'metadata_rows': rows, 'requirement_rows': requirement_rows,
            'metadata_qa_counts': dict(counts), 'requirements_qa_counts': dict(rc),
            'documents': files[version],
            'documents_text_indexed': sum(bool(f['readable_sections']) for f in files[version]),
            'documents_not_read_or_unavailable': [f['file'] for f in files[version]
                if not f['readable_sections']],
            'note': 'XSD, dokument-M-ID-omtale og XPath-leksikk er kandidat-evidens, ikke normativ dekning.',
        }
    report = {
        'report_format_version': 1, 'report_type': REPORT_TYPE,
        'source_repository': 'IKAMR/digital-archive-workflow',
        'source_checkout_commit': trace.get('source_checkout_commit'),
        'source_checkout_commit_verified': trace.get('source_checkout_commit_verified'),
        'source_commit_matches_semantic_registry': trace.get('source_commit_matches_registry'),
        'dwm_repository': 'IKAMR/data-workflow-manager',
        'source_manifest': str(MANIFEST_REL).replace('\\', '/'),
        'source_xsd': schemas,
        'document_text_scanned': scan_documents,
        'numbered_document_text_candidates': numbered,
        'numbered_document_text_candidates_are_not_normative_requirements': True,
        'registered_normative_requirements_only': True,
        'normative_requirements_all_read': False,
        'saxon_lxml_expression_parity_verified': False,
        'noark_conformance_verified': False,
        'diagnostic_xsd_overrides_applied': False,
        'source_files_modified': False,
        'xpath_catalog_tests': trace['xpath_catalog_tests'],
        'xpath_special_handlers_not_semantically_audited':trace['xpath_special_handlers_not_semantically_audited'],
        'versions': versions,
        'technical_xsd_version_differences': _diffs(raw_rows),
        'qa_issues': issues,
        'open_source_qa': ['QA-N5-001: M300 Fysisk medium / Fysisk arkiv',
                           'QA-N5-003: fem XML-typer ikke fullstendig skjemavalidert',
                           'QA-N5-004: full KDRS-Saxon/lxml-paritet ikke verifisert',
                           'QA-N5-005: komplette normative dokumentkrav ikke punktvis verifisert'],
    }
    for version in VERSIONS:
        mismatch = [x for x in versions[version]['metadata_rows'] if x['value_set_mismatch_from_xsd']]
        for row in mismatch:
            report['qa_issues'].append({'severity': 'WARNING', 'kind': 'dwm_value_set_xsd_literal_difference',
                                        'version': version, 'metadata_id': row['metadata_id'],
                                        'source': row['source_file']})
    return report


def filter_matrix_rows(report: dict[str, Any], *, version: str = '',
                       severity: str = '', query: str = '') -> list[dict]:
    """UI-independent FEIL/WARNING/NOTE QA filter, not archive result severity."""
    if report.get('report_type') != REPORT_TYPE:
        raise ValueError('Ukjent Noark 5 dekningsmatrise')
    if version not in ('', *VERSIONS) or severity not in ('','FEIL','WARNING','NOTE'):
        raise ValueError('Ukjent versjon eller QA-status')
    out: list[dict] = []
    for v in ((version,) if version else VERSIONS):
        record = report['versions'][v]
        for row in record.get('metadata_rows', ()):
            out.append({'kind': 'Metadata', 'version': v,
                        'id': row.get('metadata_id'), 'name': row.get('type_name'),
                        'severity': row.get('qa_severity'),
                        'candidate_count': len(row.get('xpath_lexical_test_ids') or ()),
                        'detail': row})
        for row in record.get('requirement_rows', ()):
            out.append({'kind': 'Krav', 'version': v,
                        'id': row.get('requirement_id'), 'name': row.get('normative_summary'),
                        'severity': row.get('qa_severity'),
                        'candidate_count': len(row.get('xpath_lexical_test_ids') or ()),
                        'detail': row})
    for issue in report.get('qa_issues', ()):
        if not isinstance(issue, dict):
            continue
        v = str(issue.get('version') or '')
        if version and v != version:
            continue
        out.append({'kind': 'Kildeavvik', 'version': v,
                    'id': issue.get('metadata_id') or issue.get('source') or '',
                    'name': issue.get('kind'), 'severity': issue.get('severity'),
                    'candidate_count': 0, 'detail': issue})
    if severity:
        out = [row for row in out if row['severity'] == severity]
    if query.strip():
        value = query.strip().casefold()
        out = [row for row in out if value in ' '.join(
            str(row.get(key) or '') for key in ('id','name','version','kind')).casefold()]
    return out


def _csv_text(rows: list[dict], fieldnames: list[str]) -> str:
    handle = io.StringIO(newline='')
    writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator='\n')
    writer.writeheader()
    for row in rows:
        writer.writerow({key: row.get(key, '') for key in fieldnames})
    return handle.getvalue()


def markdown_summary(report: dict) -> str:
    lines = [
        '# Noark 5: teknisk XSD- og kravmatrise (a7)', '',
        '**Kilde:** `IKAMR/digital-archive-workflow` først; kilde-commit: `'
            + str(report.get('source_checkout_commit') or 'ikke bekreftet') + '`.',
        '**Avgrensning:** Dette er teknisk deknings- og QA-kartlegging, ikke ferdig normativ kravkontroll.',
        '', '| Noark 5 | XSD-M-typer | DWM M-ID | DWM-krav | Dokumenter lest |',
        '| --- | ---: | ---: | ---: | ---: |',
    ]
    for version in VERSIONS:
        entry = report['versions'][version]
        lines.append(f"| {version} | {entry['xsd_metadata_types']} | "
                     f"{entry['registered_metadata']} | {entry['registered_requirements']} | "
                     f"{entry['documents_text_indexed']} / {len(entry['documents'])} |")
    lines += ['', f"XSD-filer med identitets-evidens: {len(report['source_xsd'])}.",
              f"Katalogtester: {report['xpath_catalog_tests']} (inkludert spesialtestene som ikke er semantisk verifisert).",
              '', '## Prioriterte QA-funn', '']
    for issue in report['qa_issues']:
        if isinstance(issue, dict):
            lines.append('- ' + str(issue['severity']) + ': ' + str(issue['kind'])
                         + ' – ' + str(issue.get('source') or issue.get('metadata_id') or '')
                         + ' v' + str(issue.get('version') or '?'))
    lines += ['', '## Ikke verifisert', '',
              '- Full krav- og metadataordlyd i hovedspesifikasjonene og vedleggene.',
              '- Full KDRS Standard/U1/U2-semantikk sammenholdt med identiske uttrekk.',
              '- XSD-validering av alle relevante XML-filene i en faktisk avlevering.',
              '- Om egendefinerte verdier er normativt tillatt for hvert metadatafelt.',
              '- Om en semantisk menings-ID er normativt gyldig (den sier bare noe om betydning).',
              '', 'Ingen normative kildefiler, registrerte krav eller original-XML er endret.', '']
    return '\n'.join(lines)


def write_reports(report: dict, source_root: Path | str, dwm_root: Path | str,
                  output_dir: Path | str) -> list[Path]:
    source, dwm, output = (Path(p).resolve() for p in (source_root, dwm_root, output_dir))
    if any(output == parent or parent in output.parents for parent in (source, dwm)):
        raise ValueError('Resultatene må ligge utenfor DWM og kildebiblioteket')
    if source == dwm or source in dwm.parents or dwm in source.parents:
        raise ValueError('DWM og kilderepo må være separate')
    paths = [output / n for n in REPORT_FILES]
    if any(path.exists() for path in paths):
        raise FileExistsError('Rapportene finnes allerede; overskriving er sperret')
    meta = []
    reqs = []
    for v in VERSIONS:
        for row in report['versions'][v]['metadata_rows']:
            meta.append({'version':v, 'metadata_id':row['metadata_id'],
                'xsd_type_name':row['type_name'], 'source_xsd_line':row['xsd_type_definition_line'],
                'registered_in_dwm':row['registered_in_dwm_metadata'],
                'xpath_candidate_count':len(row['xpath_lexical_candidates']),
                'document_reference_count':len(row['document_references']),
                'qa_severity':row['qa_severity'], 'qa_reason':row['qa_reason']})
        for row in report['versions'][v]['requirement_rows']:
            reqs.append({'version':v, 'requirement_id':row['requirement_id'],
                'source_id':row.get('source_id'), 'source_location':row.get('source_location'),
                'metadata_id':row.get('metadata_id'),
                'xpath_candidate_count':len(row['xpath_lexical_test_ids']),
                'qa_severity':row['qa_severity'], 'qa_reason':row['qa_reason']})
    contents = [json.dumps(report, ensure_ascii=False, indent=2) + '\n',
                markdown_summary(report),
                _csv_text(meta, ['version','metadata_id','xsd_type_name','source_xsd_line',
                                 'registered_in_dwm','xpath_candidate_count',
                                 'document_reference_count','qa_severity','qa_reason']),
                _csv_text(reqs, ['version','requirement_id','source_id','source_location',
                                 'metadata_id','xpath_candidate_count','qa_severity','qa_reason'])]
    if len(contents[0].encode('utf-8')) > MAX_REPORT_BYTES:
        raise ValueError('Rapporten overstiger størrelsesgrensen')
    output.mkdir(parents=True, exist_ok=True)
    for path, content in zip(paths, contents):
        with path.open('x', encoding='utf-8', newline='') as handle:
            handle.write(content)
    return paths


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-root', type=Path, required=True,
                        help='Lokal utsjekking av IKAMR/digital-archive-workflow')
    parser.add_argument('--dwm-root', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--source-commit', default=None,
                        help='Hvis oppgitt og Git HEAD er tilgjengelig: krev eksakt commit')
    parser.add_argument('--output-dir', type=Path, required=True,
                        help='Separat QA/Work-mappe utenfor begge Git-repositorier')
    parser.add_argument('--skip-document-text', action='store_true',
                        help='Bare XSD og registre; ikke les PDF/DOCX/XLSX-tekst')
    args = parser.parse_args(argv)
    try:
        report = build_matrix(args.source_root,args.dwm_root,
                              source_commit=args.source_commit,
                              scan_documents=not args.skip_document_text)
        files = write_reports(report,args.source_root,args.dwm_root,args.output_dir)
    except (OSError, ValueError, FileExistsError) as exc:
        parser.error(str(exc))
    for path in files:
        print(path)
    for v, entry in report['versions'].items():
        print(f"Noark {v}: {entry['xsd_metadata_types']} XSD-M-typer, "
              f"{entry['registered_requirements']} registrerte DWM-krav, "
              f"{entry['documents_text_indexed']} leste dokumentfiler")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
