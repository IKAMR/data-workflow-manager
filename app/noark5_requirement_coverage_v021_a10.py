"""a10: trace source-bound a9 Noark clauses to *candidate* DWM controls.

No source-text match, XPath path, XSD schema or local requirement registry entry
is proof that the normative requirement is implemented. Read-only static
inventory; no archive extract is read, no XPath is executed, and all normative
and implementation verdicts remain NOT_VERIFIED pending reviewed evidence.
"""
from __future__ import annotations

import argparse
import ast
from collections import Counter
import csv
from hashlib import sha256
import io
import json
from pathlib import Path
import re
from typing import Any

from app.noark5_requirement_registry_v021_a9 import REPORT_TYPE as A9_REPORT_TYPE
from app.noark5_kdrs_semantic_audit_v021_a8 import static_special_dispatch
from app.noark5_xpath_audit_v021_a1 import CATALOG_REL, load_rows
from app.noark5_requirement_review_v021_a8 import _csv_safe

REPORT_TYPE = 'noark5_a10_static_control_candidate_matrix_not_implementation_verification'
VERSIONS = ('3.1', '4.0', '5.0')
REPORT_NAMES = ('noark5-a10-coverage.json', 'noark5-a10-coverage.csv',
                'noark5-a10-controls.csv', 'noark5-a10-unlinked.csv',
                'noark5-a10-summary.md')
MAX_A9_BYTES = 80_000_000
MAX_REPORT_BYTES = 80_000_000
MAX_INPUT_CLAUSES = 16_000
MAX_CONTROLS = 1_000
MAX_LINKS = 40
MAX_CLAUSE_TEXT = 24_000
MAX_REGISTRY_BYTES = 8_000_000
ENGINE_REL = Path('noark5_workflow/analysis/xpath_test_engine.py')
XSD_VALIDATOR_REL = Path('app/noark5_xsd_full_xml_v021_a8.py')
XSD_PINS_REL = Path('config/noark5/standards/noark5_xsd_signatures_v0114_a5.json')
REGISTER_INDEX_REL = Path('config/noark5/standards/requirements/index.json')
IDENTIFIER = re.compile(r'(?<![A-Za-z0-9_])([A-Za-z_][A-Za-z_0-9]*)(?![A-Za-z0-9_])')
METADATA_ID = re.compile(r'\bM\d{3}\b')
SOURCE_SHA = re.compile(r'^[0-9a-f]{64}$')
FULL_COMMIT = re.compile(r'^[0-9a-f]{40}$')
# These are *lexical* indicators, never interpretations of normative rules.
TECHNICAL_XML_SUFFIXES = ('status', 'medium', 'nummer', 'type', 'dato', 'id')
NO_FIELD_TOKENS = frozenset({
    'string', 'count', 'sum', 'number', 'true', 'false', 'not', 'and', 'or',
    'text', 'node', 'name', 'value', 'property', 'contains', 'normalize',
    'normalizeSpace', 'localName', 'position', 'last', 'concat', 'starts',
    'arkiv', 'arkivdel', 'mappe', 'klasse', 'klassifikasjonssystem',
    'registrering', 'journalpost', 'dokumentobjekt', 'dokumentbeskrivelse',
    'arkivskaper', 'saksmappe', 'source', 'id', 'null',
})


def _read_json(path: Path, limit: int) -> dict:
    if not path.is_file() or path.stat().st_size > limit:
        raise ValueError(f'JSON mangler eller er for stor: {path}')
    obj = json.loads(path.read_text(encoding='utf-8-sig'))
    if not isinstance(obj, dict):
        raise ValueError(f'Forventet JSON-objekt: {path}')
    return obj


def _safe_repo_file(root: Path, relative: Path) -> Path:
    if relative.is_absolute() or '..' in relative.parts:
        raise ValueError('Utrygg relativ kildesti')
    path = (root / relative).resolve()
    if not path.is_relative_to(root.resolve()):
        raise ValueError('Kildesti går utenfor DWM-repoet')
    return path


def _sha_file(path: Path) -> str | None:
    if not path.is_file() or path.stat().st_size > MAX_REGISTRY_BYTES:
        return None
    return sha256(path.read_bytes()).hexdigest()


def _source_field_tokens(expressions: tuple[str, ...]) -> tuple[str, ...]:
    """Narrow explicit XML-looking identifiers observed in actual XPath strings.

    Only existing lexical literals, never an inferred XPath/condition, enter
    this list. Generic class names and XPath function names are excluded.
    """
    result = set()
    for expression in expressions:
        # A quoted value or a function argument string is not an XML field.
        outside_string_literals = re.sub(r'''("[^"]*"|\'[^\']*\')''', ' ', expression)
        for token in IDENTIFIER.findall(outside_string_literals):
            lower = token.casefold()
            if token in NO_FIELD_TOKENS or len(token) < 6:
                continue
            if lower in {'xpath', 'xml', 'contains', 'number', 'string', 'boolean'}:
                continue
            camel = bool(re.search(r'[a-z][A-Z]|[A-Z]{2}', token))
            suffixed = lower.endswith(TECHNICAL_XML_SUFFIXES)
            if camel or suffixed:
                result.add(token)
    return tuple(sorted(result))


def _load_xsd_validator(root: Path, issues: list[dict]) -> tuple[dict[str, str | None], str | None, bool]:
    path = _safe_repo_file(root, XSD_VALIDATOR_REL)
    digest = _sha_file(path)
    if not digest:
        issues.append({'severity': 'WARNING', 'kind': 'xsd_validator_source_unavailable',
                       'source': XSD_VALIDATOR_REL.as_posix()})
        return {}, None, False
    try:
        tree = ast.parse(path.read_text(encoding='utf-8-sig'))
        mapping = next((ast.literal_eval(node.value) for node in tree.body
                        if isinstance(node, ast.Assign)
                        and any(isinstance(t, ast.Name) and t.id == 'XML_TO_SCHEMA'
                                for t in node.targets)), None)
        has_function = any(isinstance(node, ast.FunctionDef)
                           and node.name == 'validate_extraction' for node in tree.body)
    except (SyntaxError, UnicodeError, ValueError, TypeError) as exc:
        issues.append({'severity': 'FEIL', 'kind': 'xsd_validator_ast_unreadable',
                       'error_class': type(exc).__name__})
        return {}, digest, False
    if not isinstance(mapping, dict) or not has_function or set(mapping) != {
        'arkivstruktur.xml', 'endringslogg.xml', 'loependeJournal.xml',
        'offentligJournal.xml', 'arkivuttrekk.xml',
    } or any(not isinstance(k, str) or (v is not None and not isinstance(v, str))
             for k, v in mapping.items()):
        issues.append({'severity': 'FEIL', 'kind': 'xsd_validator_contract_changed',
                       'source': XSD_VALIDATOR_REL.as_posix()})
        return {}, digest, False
    return mapping, digest, True


def _load_pins(root: Path, issues: list[dict]) -> tuple[dict[tuple[str, str], str], str | None]:
    path = _safe_repo_file(root, XSD_PINS_REL)
    digest = _sha_file(path)
    if not digest:
        issues.append({'severity': 'WARNING', 'kind': 'xsd_pins_unavailable',
                       'source': XSD_PINS_REL.as_posix()})
        return {}, None
    try:
        obj = _read_json(path, MAX_REGISTRY_BYTES)
        values = obj.get('signatures')
        if not isinstance(values, list):
            raise ValueError('Mangler signatures')
        pins = {}
        for row in values:
            if not isinstance(row, dict):
                raise ValueError('Ugyldig XSD-signatur')
            ver, name, signature = row.get('version'), row.get('filename'), row.get('sha256')
            if not isinstance(ver, str) or not isinstance(name, str) or not isinstance(signature, str) or not SOURCE_SHA.fullmatch(signature):
                raise ValueError('Ugyldig XSD-signatur')
            if (ver, name) in pins:
                raise ValueError('Duplisert XSD-signatur')
            pins[ver, name] = signature
    except (OSError, ValueError, TypeError) as exc:
        issues.append({'severity': 'FEIL', 'kind': 'xsd_pins_invalid', 'error_class': type(exc).__name__})
        return {}, digest
    return pins, digest


def _load_local_reference_rules(root: Path, issues: list[dict]) -> tuple[list[dict], dict[str, str]]:
    """Local partial normative registry is a *reference*, not an executed test."""
    src = _safe_repo_file(root, REGISTER_INDEX_REL)
    if not src.is_file():
        issues.append({'severity': 'WARNING', 'kind': 'partial_reference_registry_index_missing'})
        return [], {}
    obj = _read_json(src, MAX_REGISTRY_BYTES)
    versions = obj.get('versions')
    if not isinstance(versions, dict) or set(versions) != set(VERSIONS):
        raise ValueError('Ugyldig kravregister-indeks; må ha tre versjoner')
    result = []
    digests = {REGISTER_INDEX_REL.as_posix(): _sha_file(src)}
    for ver in VERSIONS:
        raw = versions[ver]
        if not isinstance(raw, str) or not raw.startswith('config/noark5/standards/requirements/'):
            raise ValueError('Utrygg lokal kravregistersti')
        path = _safe_repo_file(root, Path(raw))
        digest = _sha_file(path)
        if not digest:
            issues.append({'severity': 'WARNING', 'kind': 'local_reference_registry_missing',
                           'noark_version': ver, 'source': raw})
            continue
        digests[raw] = digest
        doc = _read_json(path, MAX_REGISTRY_BYTES)
        if doc.get('noark_version') != ver or not isinstance(doc.get('requirements'), list):
            raise ValueError('Kravregisterfil har feil Noark-versjon eller format: ' + raw)
        for entry in doc['requirements']:
            if not isinstance(entry, dict) or not isinstance(entry.get('requirement_id'), str):
                raise ValueError('Ugyldig lokalt registrert krav')
            result.append({
                'requirement_id': entry['requirement_id'],
                'noark_version': ver,
                'summary': entry.get('normative_summary') or '',
                'metadata_id': entry.get('related_metadata_id') or '',
                'xml_field_name': entry.get('xml_field_name') or '',
                'directly_testable_from_extract': (entry.get('extract_validation') or {}).get('directly_testable_from_extract'),
                'implemented_as_dwm_control': (entry.get('extract_validation') or {}).get('implemented_as_dwm_control'),
                'reference_only': True,
                'source': raw,
            })
    return result, digests


def inventory_controls(dwm_root: Path | str) -> tuple[list[dict], list[dict], list[dict], dict]:
    """Actual DWM definitions by file/sha; no runtime or normative assertion."""
    root = Path(dwm_root).resolve()
    if not root.is_dir():
        raise ValueError('DWM-rot finnes ikke')
    path = _safe_repo_file(root, CATALOG_REL)
    catalog_sha = _sha_file(path)
    if not catalog_sha:
        raise ValueError('DWM XPath-katalogen mangler eller er for stor: ' + CATALOG_REL.as_posix())
    entries = load_rows(root)  # validates unique IDs using existing DWM reader
    if not entries or len(entries) > MAX_CONTROLS:
        raise ValueError('DWM XPath-katalogen har ugyldig antall kontroller')
    issues = []
    engine = _safe_repo_file(root, ENGINE_REL)
    engine_sha = _sha_file(engine)
    dispatch: set[str] | None = None
    if engine_sha:
        try:
            dispatch = static_special_dispatch(engine.read_text(encoding='utf-8-sig'))
        except (OSError, UnicodeError, SyntaxError, ValueError) as exc:
            issues.append({'severity': 'FEIL', 'kind': 'xpath_engine_source_unreadable',
                           'error_class': type(exc).__name__})
    else:
        issues.append({'severity': 'WARNING', 'kind': 'xpath_engine_source_unavailable',
                       'source': ENGINE_REL.as_posix()})
    controls = []
    for item in entries:
        unknown = set(item.versions) - set(VERSIONS)
        if unknown or not item.versions:
            issues.append({'severity': 'FEIL', 'kind': 'xpath_unknown_or_missing_versions',
                           'control_id': item.test_id, 'versions': list(item.versions)})
        execution_kind = str((item.definition.get('execution') or {}).get('kind') or '')
        if not execution_kind:
            issues.append({'severity': 'FEIL', 'kind': 'xpath_execution_kind_missing',
                           'control_id': item.test_id})
        has_dispatch = None if dispatch is None else (execution_kind == 'metrics' or execution_kind in dispatch)
        if has_dispatch is False:
            issues.append({'severity': 'FEIL', 'kind': 'xpath_dispatch_not_located',
                           'control_id': item.test_id, 'execution_kind': execution_kind})
        standard_checks = item.definition.get('standard_value_checks') or []
        versioned_checks = []
        for check in standard_checks:
            if not isinstance(check, dict):
                continue
            value_set_id = str(check.get('value_set_id') or '')
            match = re.match(r'M\d{3}(?=_)', value_set_id)
            if not match:
                continue
            versions = check.get('versions')
            if not isinstance(versions, list) or any(v not in VERSIONS for v in versions):
                issues.append({'severity': 'WARNING', 'kind': 'value_set_check_version_unverified',
                               'control_id': item.test_id, 'value_set_id': value_set_id})
                versions = []
            versioned_checks.append({
                'metadata_id': match.group(0), 'value_set_id': value_set_id,
                'versions': sorted(set(versions).intersection(item.versions)),
                'application_is_version_declaration_only': True,
            })
        mids = sorted({x['metadata_id'] for x in versioned_checks})
        controls.append({
            'control_id': item.test_id, 'control_type': 'xpath_catalog_test',
            'name': item.name, 'noark_versions_declared': list(item.versions),
            'source_xml': item.source_xml, 'legacy_job_id': item.legacy_id,
            'execution_kind': execution_kind,
            'xpath_expressions_count': len(item.paths),
            'xml_field_name_candidates': list(_source_field_tokens(item.paths)),
            'metadata_ids_explicit_value_checks': mids,
            'value_set_checks_by_declared_version': versioned_checks,
            'standard_value_set_ids': list(item.standard_checks),
            'source_file': CATALOG_REL.as_posix(), 'source_sha256': catalog_sha,
            'engine_file': ENGINE_REL.as_posix(), 'engine_sha256': engine_sha,
            'dispatch_identified_by_ast': has_dispatch,
            'executed_in_a_real_extract_verified': False,
            'runtime_semantics_verified': False, 'saxon_lxml_parity_verified': False,
            'normative_requirement_coverage_verified': False,
        })
    mappings, validator_sha, exists = _load_xsd_validator(root, issues)
    pins, pins_sha = _load_pins(root, issues)
    if exists:
        for ver in VERSIONS:
            for xml_file, schema in mappings.items():
                is_pinned = bool(schema and (ver, schema) in pins and
                                 (ver, 'metadatakatalog.xsd') in pins)
                if schema and not is_pinned:
                    issues.append({'severity': 'WARNING', 'kind': 'xsd_version_pin_missing',
                                   'noark_version': ver, 'source': schema})
                controls.append({
                    'control_id': f'xsd.v{ver}.{xml_file}', 'control_type': 'technical_xsd_validator',
                    'name': f'Teknisk XSD-kontroll: {xml_file}',
                    'noark_versions_declared': [ver], 'source_xml': xml_file,
                    'schema_file': schema,
                    'addml_supplied_by_extract_not_pinned': schema is None,
                    'xsd_signature_pinned': is_pinned,
                    'source_file': XSD_VALIDATOR_REL.as_posix(),
                    'source_sha256': validator_sha,
                    'xsd_pin_registry_sha256': pins_sha,
                    'executed_in_a_real_extract_verified': False,
                    'runtime_semantics_verified': False, 'saxon_lxml_parity_verified': False,
                    'normative_requirement_coverage_verified': False,
                })
    references, references_sha = _load_local_reference_rules(root, issues)
    if len(controls) > MAX_CONTROLS or len({r['control_id'] for r in controls}) != len(controls):
        raise ValueError('Kontrollinventaret er for stort eller har duplikat-ID')
    files = {CATALOG_REL.as_posix(): catalog_sha,
             ENGINE_REL.as_posix(): engine_sha,
             XSD_VALIDATOR_REL.as_posix(): validator_sha,
             XSD_PINS_REL.as_posix(): pins_sha, **references_sha}
    return controls, references, issues, files


def _validate_a9(a9: dict) -> list[dict]:
    if a9.get('report_type') != A9_REPORT_TYPE:
        raise ValueError('Forventet en ekte a9 kravregisterrapport')
    if a9.get('source_repository') != 'IKAMR/digital-archive-workflow':
        raise ValueError('a9 har feil kildebibliotek')
    if not FULL_COMMIT.fullmatch(str(a9.get('source_checkout_commit_current') or '')):
        raise ValueError('a9 mangler kildecommit i full lengde')
    for flag in ('normative_requirements_approved', 'full_normative_coverage_verified',
                 'dwm_implementation_coverage_verified', 'saxon_lxml_semantic_parity_verified',
                 'source_files_modified'):
        if a9.get(flag) is not False:
            raise ValueError('a9 har ukjent eller ikke-tillatt godkjenningsstatus: ' + flag)
    if not isinstance(a9.get('versions'), dict) or set(a9['versions']) != set(VERSIONS):
        raise ValueError('a9 må ha nøyaktig tre Noark 5-versjoner')
    rows = a9.get('candidate_rows')
    if not isinstance(rows, list) or len(rows) > MAX_INPUT_CLAUSES:
        raise ValueError('a9 har ugyldige kravkandidater')
    if not isinstance(a9.get('qa_issues'), list):
        raise ValueError('a9 mangler kilde-QA')
    ids = set()
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError('Ugyldig kravrad i a9')
        ident, ver = row.get('candidate_id'), row.get('noark_version')
        if not isinstance(ident, str) or not ident or ident in ids:
            raise ValueError('a9 har duplisert/manglende kandidat-ID')
        ids.add(ident)
        if ver not in VERSIONS or not ident.startswith(f'{ver}:'):
            raise ValueError('Kravkandidat har feil Noark-versjon i ID')
        if not isinstance(row.get('number'), str) or not isinstance(row.get('text'), str) or len(row['text']) > MAX_CLAUSE_TEXT:
            raise ValueError('a9 har ugyldig kravtekst eller Noark-versjon')
        if not isinstance(row.get('source'), str) or not isinstance(row.get('location'), str):
            raise ValueError('a9 krav mangler kilde eller posisjon')
        if not SOURCE_SHA.fullmatch(str(row.get('source_sha256') or '')):
            raise ValueError('a9 krav mangler SHA-256 for kilden')
    for ver in VERSIONS:
        count = sum(row['noark_version'] == ver for row in rows)
        if (a9['versions'][ver].get('requirements_indexed') != count):
            raise ValueError('a9 kravtall stemmer ikke med antall kravrader: ' + ver)
    return rows


def _phrase_present(text: str, token: str) -> bool:
    return bool(re.search(r'(?<![A-Za-z0-9_])' + re.escape(token)
                          + r'(?![A-Za-z0-9_])', text, flags=re.I))


def _links_for_clause(clause: dict, controls: list[dict], refs: list[dict]) -> tuple[list[dict], list[dict], int]:
    ver, text = clause['noark_version'], clause['text']
    mids = set(METADATA_ID.findall(text)) | {
        value for value in clause.get('metadata_ids_mentioned', [])
        if isinstance(value, str) and METADATA_ID.fullmatch(value)
    }
    found = []
    for control in controls:
        if ver not in control['noark_versions_declared']:
            continue
        reason = None
        witness = None
        if control['control_type'] == 'technical_xsd_validator':
            filename = control['source_xml']
            if _phrase_present(text, filename):
                reason, witness = 'literal_xml_filename', filename
        else:
            applicable = {check['metadata_id']
                          for check in control.get('value_set_checks_by_declared_version', [])
                          if ver in check['versions']}
            intersection = mids.intersection(applicable)
            if intersection:
                reason, witness = 'explicit_metadata_id_vs_value_set', sorted(intersection)[0]
            else:
                fields = control.get('xml_field_name_candidates') or []
                match = next((field for field in fields if _phrase_present(text, field)), None)
                if match:
                    reason, witness = 'xml_field_lexical_cooccurrence', match
        if reason:
            found.append({'control_id': control['control_id'],
                          'control_type': control['control_type'],
                          'evidence_type': reason, 'literal_witness': witness,
                          'mapping_reviewed': False, 'implementation_verified': False,
                          'normative_equivalence_verified': False})
    references = []
    for ref in refs:
        if ref['noark_version'] != ver:
            continue
        matched = (ref['metadata_id'] in mids if ref['metadata_id'] else False)
        if not matched and ref['xml_field_name']:
            matched = _phrase_present(text, ref['xml_field_name'])
        if matched:
            references.append({'requirement_id': ref['requirement_id'],
                               'reference_only': True,
                               'implemented_as_dwm_control': ref['implemented_as_dwm_control'],
                               'mapping_reviewed': False})
    found.sort(key=lambda x:(x['control_type'], x['control_id']))
    references.sort(key=lambda x:x['requirement_id'])
    return found[:MAX_LINKS], references[:MAX_LINKS], max(0, len(found)-MAX_LINKS)


def build_coverage(a9: dict, dwm_root: Path | str, *, a9_sha256: str | None = None) -> dict:
    clauses = _validate_a9(a9)
    controls, refs, issues, file_shas = inventory_controls(dwm_root)
    counts = Counter()
    links_by_control = Counter()
    matrix = []
    for entry in clauses:
        matches, references, truncated = _links_for_clause(entry, controls, refs)
        for match in matches:
            links_by_control[match['control_id']] += 1
        coverage_state = 'IKKE_VERIFISERT'
        evidence = 'TEKNISKE_KANDIDATER' if matches else 'INGEN_DOKUMENTERT_KOBLING'
        counts[entry['noark_version']] += 1
        matrix.append({
            'candidate_id': entry['candidate_id'],
            'noark_version': entry['noark_version'],
            'number': entry['number'],
            'requirement_class': entry.get('requirement_class') or '',
            'requirement_text': entry['text'],
            'remarks_or_conditions': entry.get('remarks_or_conditions') or '',
            'source': entry['source'], 'source_location': entry['location'],
            'source_sha256': entry.get('source_sha256'),
            'source_qa_severity': entry.get('qa_severity') or 'WARNING',
            'source_qa_reasons': list(entry.get('qa_reasons') or []),
            'source_review_state': entry.get('review_state') or 'PENDING_MANUAL_QA',
            'retired_text': entry.get('retired_text') is True,
            'coverage_state': coverage_state,
            'evidence_state': evidence,
            'technical_candidate_count': len(matches),
            'technical_candidates_truncated_count': truncated,
            'technical_control_candidates': matches,
            'local_requirement_registry_references': references,
            'static_extract_testability': 'IKKE_FAGLIG_VURDERT',
            'normative_requirement_approved': False,
            'implementation_verified': False,
            'saxon_lxml_semantic_parity_verified': False,
        })
    for control in controls:
        control['a9_clause_candidate_count'] = links_by_control[control['control_id']]
        control['not_linked_does_not_mean_unimplemented'] = True
    source_counts = Counter(i.get('severity') for i in a9['qa_issues'] if isinstance(i, dict))
    inventory_counts = Counter(i.get('severity') for i in issues if isinstance(i, dict))
    linked = sum(bool(r['technical_control_candidates']) for r in matrix)
    return {
        'report_format_version': 1, 'report_type': REPORT_TYPE,
        'source_repository': a9['source_repository'],
        'source_checkout_commit_current': a9['source_checkout_commit_current'],
        'source_manifest_sha256': a9.get('source_manifest_sha256'),
        'a9_report_sha256': a9_sha256,
        'dwm_control_source_sha256': file_shas,
        'versions': {v: {'clauses': counts[v],
                         'with_technical_candidates': sum(bool(r['technical_control_candidates'])
                             for r in matrix if r['noark_version'] == v),
                         'implementation_verified': 0,
                         'coverage_not_verified': counts[v]}
                     for v in VERSIONS},
        'summary': {'clauses': len(matrix), 'xpath_catalog_controls': sum(
                         c['control_type'] == 'xpath_catalog_test' for c in controls),
                     'xsd_technical_controls': sum(c['control_type'] == 'technical_xsd_validator'
                         for c in controls),
                     'local_requirement_registry_references': len(refs),
                     'clauses_with_technical_candidates': linked,
                     'clauses_without_technical_candidates': len(matrix)-linked,
                     'implementation_verified': 0,
                     'source_qa_issue_counts': dict(source_counts),
                     'control_inventory_issue_counts': dict(inventory_counts)},
        'control_inventory': controls,
        'local_requirement_registry': refs,
        'coverage_matrix': matrix,
        'control_inventory_issues': issues,
        'a9_source_qa_issues': a9['qa_issues'],
        'all_normative_claims_unapproved': True,
        'normative_requirements_approved': False,
        'dwm_implementation_coverage_verified': False,
        'saxon_lxml_semantic_parity_verified': False,
        'archive_extract_conformance_verified': False,
        'source_files_modified': False,
        'note': ('Kandidatkoblinger er kun leksikalske/tekniske indikasjoner. '
                 'Ingen krav er erklært implementert, manglende eller ikke relevant '
                 'uten konkret faglig gjennomgang og kjøring på testuttrekk.'),
    }


def filter_coverage_rows(report: dict, *, version: str = '', source_qa: str = '',
                         evidence: str = '', coverage: str = '', query: str = '') -> list[dict]:
    if report.get('report_type') != REPORT_TYPE:
        raise ValueError('Ukjent a10 dekningsrapport')
    if version not in ('', *VERSIONS) or source_qa not in ('', 'FEIL', 'WARNING', 'NOTE'):
        raise ValueError('Ukjent Noark-versjon eller kilde-QA')
    if evidence not in ('', 'TEKNISKE_KANDIDATER', 'INGEN_DOKUMENTERT_KOBLING'):
        raise ValueError('Ukjent evidenstype')
    if coverage not in ('', 'IKKE_VERIFISERT', 'IMPLEMENTERT_VERIFISERT',
                        'MANGLER_VURDERT', 'IKKE_RELEVANT_VURDERT'):
        raise ValueError('Ukjent dekningsstatus')
    needle = query.strip().casefold()
    result = []
    for r in report.get('coverage_matrix', []):
        if version and r['noark_version'] != version:
            continue
        if source_qa and r['source_qa_severity'] != source_qa:
            continue
        if evidence and r['evidence_state'] != evidence:
            continue
        if coverage and r['coverage_state'] != coverage:
            continue
        if needle and needle not in ' '.join(str(r.get(k) or '') for k in (
                'candidate_id', 'number', 'requirement_text', 'source', 'remarks_or_conditions',
                'source_qa_reasons')).casefold() and needle not in ' '.join(
                x['control_id'] for x in r['technical_control_candidates']).casefold():
            continue
        result.append(r)
    return result


def _csv_text(rows: list[dict], fields: tuple[str, ...]) -> str:
    output = io.StringIO(newline='')
    writer = csv.DictWriter(output, fieldnames=fields, lineterminator='\n')
    writer.writeheader()
    for row in rows:
        writer.writerow({field: _csv_safe(str(row.get(field, ''))) if row.get(field) is not None else ''
                         for field in fields})
    return output.getvalue()


def markdown_summary(report: dict) -> str:
    summary = report['summary']
    lines = [
        '# Noark 5 a10 – kandidatkobling mellom kildekrav og DWM-kontroller', '',
        '**Ingen verifisert normativ eller implementasjonsmessig dekning.**',
        f"Kildecommit: `{report['source_checkout_commit_current']}`; "
        f"a9 rapport SHA-256: `{report.get('a9_report_sha256') or 'ikke levert'}`.", '',
        '| Versjon | Kravkandidater | Med tekniske koblingskandidater | Uten koblingsbevis | Verifisert implementert |',
        '| --- | ---: | ---: | ---: | ---: |',
    ]
    for ver in VERSIONS:
        v = report['versions'][ver]
        lines.append(f"| {ver} | {v['clauses']} | {v['with_technical_candidates']} | "
                     f"{v['clauses'] - v['with_technical_candidates']} | 0 |")
    lines += ['', f"Kontrollinventar: {summary['xpath_catalog_controls']} XPath-katalogtester, "
              f"{summary['xsd_technical_controls']} versjonerte tekniske XSD-kontroller; "
              f"{summary['local_requirement_registry_references']} lokale kravbeskrivelser "
              '(ikke kjørbare kontroller).',
              '', f"a9 kilde-QA: {summary['source_qa_issue_counts']}; "
              f"inventar-QA: {summary['control_inventory_issue_counts']}.", '',
              '## Tolkning', '',
              '- Teknisk kandidat betyr nøyaktig strengtreff for metadata-ID, XML-feltnavn '
              'eller eksplisitt XML-filnavn, med korrekt deklarert versjon. '
              'Dette er verken kravoppfyllelse eller verifisert testimplementasjon.',
              '- Ingen kobling betyr **ingen dokumentert kobling i a10**, ikke at kontrollen '
              'mangler i DWM. Ikke-verifisert er en reell status, ikke feil eller bestått.',
              '- XSD-kontroller er teknisk validering; ADDML behandles separat og er '
              'ikke en av Noark 5 sine fem XSD-filer per versjon.',
              '- KDRS-katalogens versjonsdeklarasjoner er ikke godkjent normativ '
              'versjonsanvendelse. Saxon/lxml-paritet er ikke kontrollert.',
              '- Original kilde-QA fra a9 videreføres uendret og må behandles separat.',
              '- Alle kilde- og DWM-filer behandles som skrivebeskyttet. Utdata '
              'skrives i en egen mappe utenfor repositoriet.', '',
              '## Videre vurdering', '',
              'Krav for krav: gjennomgå kildetekst, fastslå om kravet kan prøves '
              'fra et statisk arkivuttrekk, identifiser faktisk DWM-test og '
              'observerte resultater, og dokumenter normativ beslutning. '
              'Sammenlign deretter Saxon og lxml for samme testgrunnlag (a11).', '']
    return '\n'.join(lines)


def write_reports(report: dict, output_dir: Path | str, *, dwm_root: Path | str,
                  a9_report_path: Path | str | None = None) -> list[Path]:
    root = Path(dwm_root).resolve()
    out = Path(output_dir).resolve()
    if out == root or out.is_relative_to(root) or root.is_relative_to(out):
        raise ValueError('a10-utdata må ligge utenfor DWM-repoet')
    if a9_report_path is not None:
        parent = Path(a9_report_path).resolve().parent
        if out == parent or out.is_relative_to(parent) or parent.is_relative_to(out):
            raise ValueError('a10 må ha egen resultatmappe, adskilt fra a9')
    targets = [out / name for name in REPORT_NAMES]
    if any(target.exists() for target in targets):
        raise FileExistsError('a10-rapporter finnes allerede; overskriving sperret')
    matrix_fields = ('noark_version', 'number', 'candidate_id', 'requirement_class',
                     'requirement_text', 'remarks_or_conditions', 'source', 'source_location',
                     'source_qa_severity', 'coverage_state', 'evidence_state',
                     'technical_candidate_count', 'technical_control_ids',
                     'local_reference_ids')
    flattened = [{**r,
                  'technical_control_ids': '; '.join(
                      e['control_id'] for e in r['technical_control_candidates']),
                  'local_reference_ids': '; '.join(
                      e['requirement_id'] for e in r['local_requirement_registry_references'])}
                 for r in report['coverage_matrix']]
    controls = [{**c, 'noark_versions_declared': ', '.join(c['noark_versions_declared']),
                 'xml_field_name_candidates': ', '.join(c.get('xml_field_name_candidates', [])),
                 'metadata_ids_explicit_value_checks': ', '.join(c.get('metadata_ids_explicit_value_checks', []))}
                for c in report['control_inventory']]
    control_fields = ('control_id', 'control_type', 'name', 'noark_versions_declared',
                      'source_xml', 'schema_file', 'execution_kind', 'source_file',
                      'source_sha256', 'a9_clause_candidate_count', 'dispatch_identified_by_ast',
                      'xml_field_name_candidates', 'metadata_ids_explicit_value_checks')
    unlinked = [r for r in flattened if not r['technical_candidate_count']]
    content = [json.dumps(report, ensure_ascii=False, indent=2) + '\n',
               _csv_text(flattened, matrix_fields), _csv_text(controls, control_fields),
               _csv_text(unlinked, matrix_fields), markdown_summary(report)]
    if max(len(s.encode('utf-8')) for s in content) > MAX_REPORT_BYTES:
        raise ValueError('a10-rapport overskrider størrelsesgrensen')
    out.mkdir(parents=True, exist_ok=True)
    for target, value in zip(targets, content):
        with target.open('x', encoding='utf-8', newline='') as handle:
            handle.write(value)
    return targets


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--a9-report', type=Path, required=True,
                        help='noark5-a9-requirements.json fra kjøring av a9.2')
    parser.add_argument('--dwm-root', type=Path,
                        default=Path(__file__).resolve().parents[1],
                        help='Rot i lokalt DWM-repo (standard: dette repoet)')
    parser.add_argument('--output-dir', type=Path, required=True,
                        help='Ny resultatmappe utenfor repo og a9-resultatmappen')
    args = parser.parse_args(argv)
    try:
        source = args.a9_report.resolve()
        a9 = _read_json(source, MAX_A9_BYTES)
        report = build_coverage(a9, args.dwm_root, a9_sha256=sha256(source.read_bytes()).hexdigest())
        files = write_reports(report, args.output_dir, dwm_root=args.dwm_root,
                              a9_report_path=args.a9_report)
    except (OSError, ValueError, TypeError, KeyError, UnicodeError) as exc:
        parser.error(str(exc))
    for file in files:
        print(file)
    summary = report['summary']
    for ver, info in report['versions'].items():
        print(f"Noark 5 v{ver}: {info['clauses']} kravkandidater, "
              f"{info['with_technical_candidates']} teknisk koblet som kandidater, "
              f"{info['clauses'] - info['with_technical_candidates']} uten koblingsbevis")
    print(f"DWM-inventar: {summary['xpath_catalog_controls']} XPath-tester, "
          f"{summary['xsd_technical_controls']} XSD/ADDML-kjøringspunkter")
    print('Normativ dekning: IKKE VERIFISERT. Implementert: 0 VERIFISERT (ikke 0 faktiske).')
    print('Arkivuttrekksamsvar og Saxon/lxml-paritet: IKKE VERIFISERT.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
