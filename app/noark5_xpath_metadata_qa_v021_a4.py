"""Read-only metadata/requirement crosswalk for Noark 5 XPath (v0.2.1-a4).

Three distinct questions are represented:
(1) Is a metadata property or requirement actually registered for this version?
(2) Does a declared XPath expression mention the XML element or refer to its
    standard-value set? (candidate, NOT proof of a test of that property)
(3) Is a normative requirement actually verified on the extract? (ALWAYS NO here)

No XML is opened, no test is run, no Source/Work is modified. The existing
catalogue, versioned registries, and lxml engine remain authoritative for
*their own stated evidence*, not for overall Noark conformance.
"""
from __future__ import annotations

from collections import Counter
import json
from pathlib import Path
import re
from typing import Any, Iterable

from app.noark5_xpath_audit_v021_a1 import CatalogueRow, VERSIONS, load_rows, repo_root
from app.noark5_xpath_version_qa_v021_a3 import (
    _authoritative_source_matches, _source_version_matches, _source_map, _standard_registry,
    _version_registry,
)

CROSSWALK_FORMAT_VERSION = 1
FILTER_STATES = (
    '', 'xpath_candidate', 'explicit_value_set_reference',
    'no_metadata_candidate', 'requirement_candidate',
    'explicit_requirement_reference',
)
# Matching field names outside literal string constants is a *lexical* lead.
# It is not AST-based XPath verification and never becomes a pass/fail check.
_STRING_LITERAL = re.compile(r"'[^']*'|\"[^\"]*\"")
_FIELD_NAME = re.compile(r'^[A-Za-z_][A-Za-z0-9_.-]*$')


def _xpath_field_mentioned(expression: str, field_name: str) -> bool:
    """Avoid substring and string-literal false hits; mark remainder as hints."""
    if not _FIELD_NAME.fullmatch(field_name):
        return False
    without_literals = _STRING_LITERAL.sub(' ', expression)
    pat = r'(?<![A-Za-z0-9_.:-])' + re.escape(field_name) + r'(?![A-Za-z0-9_.:-])'
    return re.search(pat, without_literals) is not None


def _metric_descriptors(row: CatalogueRow) -> tuple[dict[str, str], ...]:
    """Only inspect declared metric expressions, not undocumented Python handlers."""
    execution = row.definition.get('execution') or {}
    if execution.get('kind') != 'metrics':
        return ()
    candidates = []
    for scope, key in (('whole', 'metrics'), ('archive_part', 'archive_part_metrics')):
        for metric in execution.get(key) or ():
            if not isinstance(metric, dict):
                continue
            metric_id = str(metric.get('id') or '')
            for label in ('expression', 'select', 'value'):
                expr = metric.get(label)
                if isinstance(expr, str) and expr.strip():
                    candidates.append({'metric_id': metric_id, 'scope': scope,
                                       'field': label, 'xpath': expr})
            fields = metric.get('fields') or {}
            if isinstance(fields, dict):
                for name, expr in fields.items():
                    if isinstance(expr, str) and expr.strip():
                        candidates.append({'metric_id': metric_id, 'scope': scope,
                                           'field': 'fields.' + str(name), 'xpath': expr})
    return tuple(candidates)


def _candidates(row: CatalogueRow, field_name: str) -> list[dict[str, str]]:
    return [part for part in _metric_descriptors(row)
            if _xpath_field_mentioned(part['xpath'], field_name)]


def _explicit_value_links(row: CatalogueRow, version: str, metadata_id: str,
                          value_set_id: str | None, registry: dict,
                          metadata_record: dict, sources: dict) -> list[dict[str, Any]]:
    """Verify the ID of the *referenced* metric; no implied rule semantics."""
    if not value_set_id:
        return []
    value_sets = (registry.get('versions') or {}).get(version, {}).get('value_sets') or {}
    value_set = value_sets.get(value_set_id)
    if not isinstance(value_set, dict) or value_set.get('metadata_id') != metadata_id:
        return []
    source_confirmed = (
        metadata_record.get('verification_status') in {'verified', 'verified_for_registered_value_set'}
        and metadata_record.get('standard_value_set_id') == value_set_id
        and _source_version_matches(sources, str(metadata_record.get('source_id') or ''), version)
        and _authoritative_source_matches(sources, str(metadata_record.get('source_id') or ''), version)
    )
    metric_ids = {item.get('id') for name in ('metrics', 'archive_part_metrics')
                  for item in (row.definition.get('execution') or {}).get(name) or []
                  if isinstance(item, dict)}
    links = []
    for check in row.definition.get('standard_value_checks') or ():
        if not isinstance(check, dict) or check.get('value_set_id') != value_set_id:
            continue
        versions = check.get('versions')
        if versions is not None and version not in versions:
            continue
        metric_id = check.get('metric_id')
        links.append({
            'check_id': str(check.get('id') or ''), 'metric_id': metric_id,
             'status': ('referenced_metric_not_found' if metric_id not in metric_ids
                       else 'registered_value_set_reference' if source_confirmed
                       else 'value_set_source_not_confirmed'),
            'note': 'Verdi-settreferanse, ikke attestasjon av M-felt eller krav.',
        })
    return links


def _valid_source(item: dict, version: str, source_map: dict) -> bool:
    source_id, location = item.get('source_id'), item.get('source_location')
    return bool(
        isinstance(source_id, str) and isinstance(location, str) and location.strip()
        and item.get('verification_status') in {'verified', 'source_verified'}
        and _authoritative_source_matches(source_map, source_id, version)
    )


def _explicit_requirement_link(row: CatalogueRow, identifier: str) -> bool:
    refs = row.definition.get('normative_requirement_refs') or ()
    return any((r == identifier if isinstance(r, str)
                else isinstance(r, dict) and r.get('requirement_id') == identifier)
               for r in refs)


def _metadata_entries(rows: tuple[CatalogueRow, ...], version: str,
                      registry: dict, standards: dict, source_map: dict) -> list[dict[str, Any]]:
    entries = []
    for item in sorted(registry['entries'], key=lambda it: str(it.get('metadata_id') or '')):
        meta_id = str(item['metadata_id'])
        name = str(item.get('name') or '')
        value_id = item.get('standard_value_set_id')
        # A partial value-set catalogue is not a full source-verified metadata catalogue.
        verification = str(item.get('verification_status') or 'not_verified')
        candidates = []
        explicit_links = []
        for row in rows:
            if version not in row.versions:
                continue
            expressions = _candidates(row, name)
            value_links = _explicit_value_links(row, version, meta_id, value_id, standards, item, source_map)
            if expressions:
                candidates.append({'test_id': row.test_id, 'kdrs_id': row.legacy_id,
                                   'source_xml': row.source_xml, 'metrics': expressions})
            if value_links:
                explicit_links.append({'test_id': row.test_id, 'kdrs_id': row.legacy_id,
                                       'references': value_links})
        if verification == 'verified_for_registered_value_set':
            source_scope = 'verified_registered_value_set_only'
        elif _valid_source(item, version, source_map):
            source_scope = 'selected_properties_source_verified'
        else:
            source_scope = 'properties_not_source_verified'
        entries.append({
            'type': 'metadata', 'metadata_id': meta_id, 'name': name,
            'noark_version': version, 'verification_status': verification,
            'source_scope': source_scope,
            'source_id': item.get('source_id'),
            'source_location': item.get('source_location'),
            'registered_value_set_id': value_id,
            'registered_properties': sorted((item.get('normative_properties') or {}).keys()),
            'xpath_candidates': candidates,
            'explicit_value_set_references': explicit_links,
            'mapping_state': ('explicit_value_set_reference' if explicit_links
                              else 'xpath_candidate' if candidates else 'no_xpath_candidate'),
            'conformance_verified': False,
        })
    return entries


def _requirement_entries(rows: tuple[CatalogueRow, ...], version: str,
                         registry: dict, metadata: dict, source_map: dict) -> list[dict[str, Any]]:
    entries = []
    for item in sorted(registry['entries'], key=lambda it: str(it.get('requirement_id') or '')):
        identifier = str(item['requirement_id'])
        related_meta = str(item.get('related_metadata_id') or '')
        named_meta = metadata.get('records', {}).get(related_meta, {})
        field = item.get('xml_field_name') or named_meta.get('name') or ''
        field = field if isinstance(field, str) and _FIELD_NAME.fullmatch(field) else ''
        source_ok = _valid_source(item, version, source_map) and item.get('noark_version') == version
        candidates = []
        declared_refs = []
        for row in rows:
            if version not in row.versions:
                continue
            if field:
                expressions = _candidates(row, field)
                if expressions:
                    candidates.append({'test_id': row.test_id, 'kdrs_id': row.legacy_id,
                                       'source_xml': row.source_xml, 'metrics': expressions})
            if _explicit_requirement_link(row, identifier):
                declared_refs.append({'test_id': row.test_id, 'kdrs_id': row.legacy_id})
        testable = (item.get('extract_validation') or {}).get('directly_testable_from_extract') is True
        if not source_ok:
            status = 'normative_source_not_verified'
        elif not testable:
            status = 'not_directly_testable_from_extract'
        elif declared_refs:
            status = 'explicit_catalogue_reference_not_executed_as_rule'
        elif candidates:
            status = 'xpath_candidate_no_rule_check'
        else:
            status = 'no_xpath_rule_check'
        entries.append({
            'type': 'requirement', 'requirement_id': identifier, 'noark_version': version,
            'summary': str(item.get('normative_summary') or ''),
            'source_id': item.get('source_id'), 'source_location': item.get('source_location'),
            'source_verified': source_ok, 'source_status': status,
            'xml_field_name': field or None, 'related_metadata_id': related_meta or None,
            'directly_testable_from_extract': testable,
            'xpath_candidates': candidates, 'explicit_catalogue_references': declared_refs,
            'conformance_verified': False,
        })
    return entries


def build_metadata_qa(project: Path | str | None = None, *,
                      rows: Iterable[CatalogueRow] | None = None) -> dict[str, Any]:
    """Return source-scoped inventory and *possible* XPath links, never results."""
    project = Path(project) if project is not None else repo_root()
    definitions = tuple(rows) if rows is not None else load_rows(project)
    sources = _source_map(project)
    standard_values = _standard_registry(project)
    per_version = {}
    per_test = {row.test_id: {'test_id': row.test_id, 'by_version': {}}
                for row in definitions}
    for version in VERSIONS:
        metadata = _version_registry(project, 'metadata', version)
        requirements = _version_registry(project, 'requirements', version)
        ready = (metadata['status'] == 'loaded' and requirements['status'] == 'loaded'
                 and sources['status'] == 'loaded' and standard_values['status'] == 'loaded')
        meta_entries = (_metadata_entries(definitions, version, metadata,
                                          standard_values, sources['sources'])
                        if metadata['status'] == 'loaded' else [])
        req_entries = (_requirement_entries(definitions, version, requirements,
                                            metadata, sources['sources'])
                       if requirements['status'] == 'loaded' else [])
        for row in definitions:
            meta_links = []
            req_links = []
            for meta in meta_entries:
                candidate = next((c for c in meta['xpath_candidates'] if c['test_id'] == row.test_id), None)
                value = next((c for c in meta['explicit_value_set_references']
                              if c['test_id'] == row.test_id), None)
                if candidate or value:
                    meta_links.append({'metadata_id': meta['metadata_id'], 'name': meta['name'],
                                       'xpath_mentioned': bool(candidate),
                                       'explicit_value_set_reference': bool(value),
                                       'value_reference_statuses': [r['status'] for r in value['references']]
                                           if value else []})
            for req in req_entries:
                candidate = any(c['test_id'] == row.test_id for c in req['xpath_candidates'])
                explicit = any(c['test_id'] == row.test_id
                               for c in req['explicit_catalogue_references'])
                if candidate or explicit:
                    req_links.append({'requirement_id': req['requirement_id'],
                                      'xpath_mentioned': candidate, 'explicit_reference': explicit,
                                      'source_verified': req['source_verified']})
            per_test[row.test_id]['by_version'][version] = {
                'declared_for_version': version in row.versions,
                'metadata_links': meta_links, 'requirement_links': req_links,
                'metadata_ids': sorted(x['metadata_id'] for x in meta_links),
                'normative_requirement_fulfilled': False,
            }
        per_version[version] = {
            'state': 'loaded' if ready else 'incomplete_registries',
            'metadata_registry_status': metadata['status'],
            'requirement_registry_status': requirements['status'],
            'metadata_registry_sha256': metadata['sha256'],
            'requirement_registry_sha256': requirements['sha256'],
            'metadata': meta_entries, 'requirements': req_entries,
            'summary': {
                'registered_metadata': len(meta_entries),
                'registered_requirements': len(req_entries),
                'metadata_with_xpath_candidate': sum(bool(x['xpath_candidates']) for x in meta_entries),
                'metadata_with_explicit_value_set_link': sum(bool(x['explicit_value_set_references'])
                                                             for x in meta_entries),
                'requirements_not_directly_testable': sum(not x['directly_testable_from_extract']
                                                          for x in req_entries),
                'requirements_with_xpath_candidate': sum(bool(x['xpath_candidates']) for x in req_entries),
                'requirements_verified_on_extract': 0,
            },
        }
    return {
        'metadata_audit_format_version': CROSSWALK_FORMAT_VERSION,
        'purpose': 'source_registered_metadata_and_requirement_xpath_candidate_crosswalk',
        'versions': per_version, 'tests': per_test,
        'source_registry_status': sources['status'],
        'source_registry_sha256': sources['sha256'],
        'standard_values_registry_status': standard_values['status'],
        'standard_values_registry_sha256': standard_values['sha256'],
        'noark_conformance_verified': False,
        'note': ('Eksakt XML-navntreff og registrerte verdi-settreferanser er kandidatbevis. '
                 'De beviser verken full feltkontroll eller at et normativt krav er oppfylt. '
                 'Krav uten registeroppforing er ikke inkludert i opptellingen.'),
    }


def filter_metadata_rows(rows: Iterable[dict[str, Any]], report: dict[str, Any], *,
                         version: str = '', state: str = '') -> tuple[dict[str, Any], ...]:
    """Filter existing XPath result rows by *mapping*, without re-reading Work."""
    if version and version not in VERSIONS:
        raise ValueError('Ukjent Noark-versjon: ' + version)
    if state not in FILTER_STATES:
        raise ValueError('Ukjent metadatafilter: ' + state)
    selected = []
    for item in rows:
        identifier = item['row'].test_id
        by_version = (report.get('tests') or {}).get(identifier, {}).get('by_version') or {}
        entries = [by_version.get(version)] if version else [by_version.get(v) for v in VERSIONS]
        entries = [r for r in entries if isinstance(r, dict) and r.get('declared_for_version')]
        meta = [link for entry in entries for link in entry.get('metadata_links') or ()]
        req = [link for entry in entries for link in entry.get('requirement_links') or ()]
        keep = {
            '': True,
            'xpath_candidate': any(x.get('xpath_mentioned') for x in meta),
            'explicit_value_set_reference': any(x.get('explicit_value_set_reference') for x in meta),
            'no_metadata_candidate': bool(entries) and not meta,
            'requirement_candidate': any(x.get('xpath_mentioned') for x in req),
            'explicit_requirement_reference': any(x.get('explicit_reference') for x in req),
        }[state]
        if keep:
            selected.append(item)
    return tuple(selected)


def main(argv: list[str] | None = None) -> int:
    import argparse
    parser = argparse.ArgumentParser(description='DWM Noark 5 metadata- og kravkoblinger (a4, skrivebeskyttet)')
    parser.add_argument('--project', type=Path, default=repo_root())
    parser.add_argument('--version', choices=VERSIONS, default='')
    parser.add_argument('--summary', action='store_true', help='Vis bare sammendrag og datagrunnlag')
    args = parser.parse_args(argv)
    report = build_metadata_qa(args.project)
    if args.version:
        report['versions'] = {args.version: report['versions'][args.version]}
        report['tests'] = {
            key: {**entry, 'by_version': {args.version: entry['by_version'][args.version]}}
            for key, entry in report['tests'].items()
        }
    if args.summary:
        report['versions'] = {v: {k: entry[k] for k in
                                   ('state', 'metadata_registry_status',
                                    'requirement_registry_status', 'summary')}
                              for v, entry in report['versions'].items()}
        report.pop('tests')
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
