"""Version-scoped, read-only evidence audit of Noark 5 XPath definitions.

This module verifies *links to already registered evidence*, not the correctness
of the Norwegian Noark specifications and not extract conformance. It deliberately
keeps KDRS query_subtype, XSD hashes, metadata value sets and normative tests
as independent claims.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
from typing import Any, Iterable

from app.noark5_xpath_audit_v021_a1 import (
    CATALOG_REL, SCHEMAS, VERSIONS, CatalogueRow, candidate_schema_root,
    load_rows, repo_root,
)

FORMAT_VERSION = 1
REGISTRY_ROOT = Path('config/noark5/standards')
MAX_REGISTRY_BYTES = 8_000_000
SHA256 = re.compile(r'^[a-f0-9]{64}$')
VERIFIED = {'verified', 'source_verified'}
VERSION_STATUSES = (
    'needs_version_qa', 'source_verified_version_link',
    'registry_unavailable', 'reference_conflict', 'not_declared',
)


def _safe_file(project: Path, relative: Path, *, limit: int = MAX_REGISTRY_BYTES) -> Path | None:
    """Only read files within the project; reject traversal and symlink escape."""
    if relative.is_absolute() or '..' in relative.parts:
        return None
    try:
        base = project.resolve(strict=True)
        path = (base / relative).resolve(strict=True)
        if not path.is_relative_to(base) or not path.is_file() or path.stat().st_size > limit:
            return None
        return path
    except (OSError, ValueError, RuntimeError):
        return None


def _json_reference(project: Path, relative: Path) -> tuple[dict[str, Any] | None, str | None, str]:
    file = _safe_file(project, relative)
    if file is None:
        return None, None, 'unavailable'
    try:
        content = file.read_bytes()
        doc = json.loads(content.decode('utf-8-sig'))
        if not isinstance(doc, dict):
            return None, hashlib.sha256(content).hexdigest(), 'invalid_document'
        return doc, hashlib.sha256(content).hexdigest(), 'loaded'
    except (OSError, UnicodeError, ValueError):
        return None, None, 'invalid_document'


def _version_registry(project: Path, area: str, version: str) -> dict[str, Any]:
    """Read an explicitly indexed per-version registry; never infer other versions."""
    index, index_sha, status = _json_reference(project, REGISTRY_ROOT / area / 'index.json')
    if status != 'loaded' or not isinstance(index.get('versions'), dict):
        return {'status': 'index_' + status, 'sha256': index_sha, 'records': {}, 'entries': []}
    rel = index['versions'].get(version)
    if not isinstance(rel, str):
        return {'status': 'not_indexed', 'sha256': index_sha, 'records': {}, 'entries': []}
    relative = Path(rel)
    # Index is in a versioned repository, but it must never point elsewhere.
    if relative.parts[:4] != ('config', 'noark5', 'standards', area) or relative.suffix != '.json':
        return {'status': 'invalid_registry_path', 'sha256': index_sha, 'records': {}, 'entries': []}
    doc, sha, file_status = _json_reference(project, relative)
    if file_status != 'loaded':
        return {'status': file_status, 'sha256': sha, 'records': {}, 'entries': []}
    if doc.get('noark_version') != version:
        return {'status': 'version_conflict', 'sha256': sha, 'records': {}, 'entries': []}
    key = 'metadata' if area == 'metadata' else 'requirements'
    entries = doc.get(key)
    if not isinstance(entries, list):
        return {'status': 'invalid_entries', 'sha256': sha, 'records': {}, 'entries': []}
    identifier = 'metadata_id' if area == 'metadata' else 'requirement_id'
    records = {}
    duplicates = []
    for item in entries:
        if not isinstance(item, dict) or not isinstance(item.get(identifier), str):
            return {'status': 'invalid_entries', 'sha256': sha, 'records': {}, 'entries': []}
        rid = item[identifier]
        if rid in records:
            duplicates.append(rid)
        records[rid] = item
    return {
        'status': 'loaded' if not duplicates else 'duplicate_records',
        'sha256': sha, 'records': records, 'entries': entries,
        'registry_status': doc.get('status', ''), 'duplicate_ids': sorted(set(duplicates)),
        'source': relative.as_posix(),
    }


def _source_map(project: Path) -> dict[str, Any]:
    doc, sha, state = _json_reference(project, REGISTRY_ROOT / 'sources.json')
    sources = {}
    if state == 'loaded' and not isinstance(doc.get('sources'), list):
        state = 'invalid_structure'
    if doc and isinstance(doc.get('sources'), list):
        for item in doc['sources']:
            if isinstance(item, dict) and isinstance(item.get('source_id'), str):
                sources[item['source_id']] = item
    return {'status': state, 'sha256': sha, 'sources': sources}


def _source_version_matches(sources: dict, source_id: str, version: str) -> bool:
    item = sources.get(source_id)
    if not isinstance(item, dict):
        return False
    return item.get('version') == version or version in (item.get('versions') or [])


_AUTHORITATIVE_ROLES = frozenset({
    'authoritative_requirements', 'authoritative_structure',
    'authoritative_metadata', 'authoritative_standard_values',
})


def _authoritative_source_matches(sources: dict, source_id: str, version: str) -> bool:
    if not _source_version_matches(sources, source_id, version):
        return False
    role = sources[source_id].get('role') or ()
    roles = {role} if isinstance(role, str) else set(role)
    return bool(roles & _AUTHORITATIVE_ROLES)


def _standard_registry(project: Path) -> dict[str, Any]:
    doc, sha, status = _json_reference(project, REGISTRY_ROOT / 'noark5_standard_values.json')
    versions = (doc or {}).get('versions', {})
    if not isinstance(versions, dict):
        status, versions = 'invalid_structure', {}
    return {'status': status, 'sha256': sha, 'versions': versions}


def _signature_registry(project: Path) -> dict[str, Any]:
    doc, sha, status = _json_reference(project, REGISTRY_ROOT / 'noark5_xsd_signatures_v0114_a5.json')
    signatures = {}
    for item in ((doc or {}).get('signatures') or []):
        if not isinstance(item, dict):
            continue
        v, name, digest = item.get('version'), item.get('filename'), item.get('sha256')
        if v in VERSIONS and name in SCHEMAS and isinstance(digest, str) and SHA256.fullmatch(digest):
            signatures[(v, name)] = digest
    return {'status': status, 'sha256': sha, 'hashes': signatures,
            'source_status': (doc or {}).get('source_status', 'unknown')}


def _schema_root(path: Path | str | None, project: Path) -> Path | None:
    if path is None:
        path = candidate_schema_root(project)
    if path is None:
        return None
    root = Path(path)
    nested = root / 'docs/kilder/noark/noark5'
    if nested.is_dir():
        root = nested
    return root if root.is_dir() else None


def xsd_version_fingerprints(project: Path | str, schema_root: Path | str | None = None) -> dict[str, Any]:
    """Check local XSD bytes against repo manifest; no network and no XSD validation."""
    project = Path(project)
    registered = _signature_registry(project)
    local = _schema_root(schema_root, project)
    results = {}
    for version in VERSIONS:
        entries = {}
        for filename in SCHEMAS:
            expected = registered['hashes'].get((version, filename))
            path = local / ('v' + version) / 'schemas' / filename if local else None
            status, actual = 'local_schema_not_connected', None
            if local and path:
                try:
                    resolved = path.resolve(strict=True)
                    if not resolved.is_relative_to(local.resolve(strict=True)):
                        status = 'unsafe_schema_path'
                    elif not resolved.is_file() or resolved.stat().st_size > 2_000_000:
                        status = 'schema_unavailable_or_too_large'
                    else:
                        actual = hashlib.sha256(resolved.read_bytes()).hexdigest()
                        status = ('registered_hash_matches' if expected == actual
                                  else 'registered_hash_missing' if not expected else 'hash_mismatch')
                except (OSError, ValueError, RuntimeError):
                    status = 'schema_missing'
            entries[filename] = {
                'status': status, 'expected_sha256': expected, 'actual_sha256': actual,
            }
        results[version] = entries
    return {'schema_root': str(local) if local else None,
            'signature_registry_status': registered['status'],
            'signature_registry_sha256': registered['sha256'],
            'signature_provenance_status': registered['source_status'],
            'versions': results,
            'note': ('Hashlikhet betyr samsvar med lagret DWM-manifest, ikke at manifestet er '\
                     'sammenlignet med offisiell original eller at uttrekket er XSD-validert.')}


def _refs_for_row(row: CatalogueRow, version: str, metadata: dict,
                  standards: dict, requirements: dict, sources: dict,
                  sources_available: bool = True) -> tuple[list[dict], list[dict], list[str]]:
    """Explicit references only; never map N5-testpoint to an official requirement."""
    references: list[dict] = []
    req_refs: list[dict] = []
    issues: list[str] = []
    if metadata['status'] != 'loaded' or standards['status'] != 'loaded':
        if row.definition.get('standard_value_checks'):
            issues.append('metadata_or_value_registry_unavailable')
    checks = row.definition.get('standard_value_checks') or []
    seen = set()
    for check in checks:
        if not isinstance(check, dict) or (check.get('versions') and version not in check['versions']):
            continue
        name = check.get('value_set_id')
        if not isinstance(name, str):
            issues.append('invalid_value_set_reference')
            continue
        key = (str(check.get('id') or ''), name)
        if key in seen:
            issues.append('duplicate_value_set_reference:' + name)
            continue
        seen.add(key)
        vsets = (standards.get('versions') or {}).get(version, {}).get('value_sets', {})
        value_set = vsets.get(name) if isinstance(vsets, dict) else None
        metadata_id = value_set.get('metadata_id') if isinstance(value_set, dict) else None
        record = metadata.get('records', {}).get(metadata_id)
        link = {
            'check_id': str(check.get('id') or ''), 'value_set_id': name,
            'metadata_id': metadata_id, 'metric_id': str(check.get('metric_id') or ''),
            'status': 'not_registered',
            'scope': 'registered_value_set_only_not_test_validation',
        }
        if metadata['status'] == 'loaded' and standards['status'] == 'loaded':
            if not sources_available:
                link['status'] = 'source_registry_unavailable'
                issues.append('source_registry_unavailable')
            elif value_set is None or record is None:
                link['status'] = 'reference_not_yet_registered'
                issues.append('reference_not_yet_registered:' + name)
            elif (record.get('standard_value_set_id') != name
                  or record.get('source_id') is None
                  or not _source_version_matches(sources, str(record['source_id']), version)):
                link['status'] = 'reference_conflict'
                issues.append('reference_conflict:' + name)
            elif (record.get('verification_status') not in {'verified', 'verified_for_registered_value_set'}):
                link['status'] = 'verification_unconfirmed'
                issues.append('verification_unconfirmed:' + name)
            else:
                link['status'] = 'registered_value_set_link'
                link['registered_value_count'] = len(value_set.get('values') or [])
                link['source_id'] = record['source_id']
                link['source_provenance_valid'] = True
        references.append(link)
    for reference in row.definition.get('normative_requirement_refs') or []:
        identifier = (reference if isinstance(reference, str)
                      else reference.get('requirement_id') if isinstance(reference, dict) else None)
        if not isinstance(identifier, str):
            issues.append('invalid_requirement_ref')
            continue
        record = requirements.get('records', {}).get(identifier)
        if record is None:
            req_refs.append({'requirement_id': identifier, 'status': 'not_registered_for_version'})
            issues.append('requirement_not_registered:' + identifier)
        elif (record.get('verification_status') not in VERIFIED
              or record.get('noark_version') != version
              or not _source_version_matches(sources, str(record.get('source_id') or ''), version)):
            req_refs.append({'requirement_id': identifier, 'status': 'reference_conflict'})
            issues.append('requirement_reference_conflict:' + identifier)
        else:
            req_refs.append({'requirement_id': identifier, 'status': 'source_verified_requirement_reference',
                             'directly_testable_from_extract': bool(
                                 (record.get('extract_validation') or {}).get('directly_testable_from_extract')),
                             'source_id': record.get('source_id'),
                             'source_location': record.get('source_location'),
                             'note': 'Dette er en kildereferanse, ikke attestert kontrolloppfyllelse.'})
    return references, req_refs, issues


def version_record(row: CatalogueRow, version: str, *, metadata: dict,
                   standards: dict, requirements: dict, sources: dict,
                   sources_available: bool = True) -> dict[str, Any]:
    if version not in VERSIONS:
        raise ValueError('Ukjent Noark-versjon: ' + str(version))
    declared = version in row.versions
    if not declared:
        return {'version': version, 'status': 'not_declared', 'declared': False,
                'version_basis': row.version_basis, 'value_set_references': [],
                'normative_requirement_references': [], 'issues': [],
                'source_verified_applicability': False}
    links, requirement_links, issues = _refs_for_row(row, version, metadata, standards,
                                                     requirements, sources, sources_available)
    evidence = (row.definition.get('version_evidence') or {}).get(version, {})
    # A broad KDRS query_subtype list or a version_basis string alone is NEVER
    # a source verification. An explicit, version-scoped, located source is needed.
    src_id = evidence.get('source_id') if isinstance(evidence, dict) else None
    verified = bool(isinstance(evidence, dict) and evidence.get('verification_status') in VERIFIED
                    and isinstance(src_id, str) and isinstance(evidence.get('source_location'), str)
                    and evidence['source_location'].strip()
                    and _authoritative_source_matches(sources, src_id, version))
    if evidence and not verified:
        issues.append('version_evidence_incomplete_or_conflicting')
    if any(item.startswith(('reference_conflict:', 'requirement_reference_conflict:'))
           or item == 'invalid_value_set_reference' for item in issues):
        state = 'reference_conflict'
    elif (metadata['status'] != 'loaded' or requirements['status'] != 'loaded'
          or standards['status'] != 'loaded' or not sources_available):
        state = 'registry_unavailable'
    else:
        state = 'source_verified_version_link' if verified else 'needs_version_qa'
    return {
        'version': version, 'status': state, 'declared': True,
        'version_basis': row.version_basis, 'source_verified_applicability': verified,
        'source_id': src_id if verified else None,
        'source_location': evidence.get('source_location') if verified else None,
        'value_set_references': links,
        'normative_requirement_references': requirement_links,
        'issues': sorted(set(issues)),
        'note': ('Katalogdekning, kildelenke og verdi-sett er ikke bevis for korrekt '
                 'Noark-kontroll eller bestått uttrekk.'),
    }


def build_version_audit(project: Path | str | None = None, *,
                        rows: Iterable[CatalogueRow] | None = None,
                        schema_root: Path | str | None = None) -> dict[str, Any]:
    """Build read-only, deterministic version QA from registered DWM sources."""
    project = Path(project) if project is not None else repo_root()
    entries = tuple(rows) if rows is not None else load_rows(project)
    catalogue = _json_reference(project, CATALOG_REL)
    sources = _source_map(project)
    standards = _standard_registry(project)
    metadata = {v: _version_registry(project, 'metadata', v) for v in VERSIONS}
    requirements = {v: _version_registry(project, 'requirements', v) for v in VERSIONS}
    schemas = xsd_version_fingerprints(project, schema_root=schema_root)
    test_records = {}
    for row in entries:
        test_records[row.test_id] = {
            'test_id': row.test_id, 'legacy_id': row.legacy_id,
            'name': row.name, 'source_xml': row.source_xml,
            'declared_versions': list(row.versions), 'version_basis': row.version_basis,
            'by_version': {
                v: version_record(row, v, metadata=metadata[v], standards=standards,
                                  requirements=requirements[v], sources=sources['sources'],
                                  sources_available=(sources['status'] == 'loaded'))
                for v in VERSIONS
            },
        }
    summary = {}
    for v in VERSIONS:
        records = [r['by_version'][v] for r in test_records.values()]
        statuses = Counter(r['status'] for r in records)
        value_statuses = Counter(x['status'] for row in records for x in row['value_set_references'])
        requirement_statuses = Counter(x['status'] for row in records
                                        for x in row['normative_requirement_references'])
        xsd_statuses = Counter(x['status'] for x in schemas['versions'][v].values())
        summary[v] = {
            'catalogue_tests': len(entries), 'declared_for_version': sum(x['declared'] for x in records),
            'statuses': dict(sorted(statuses.items())),
            'source_verified_version_links': sum(x['source_verified_applicability'] for x in records),
            'registered_metadata_records': len(metadata[v]['records']),
            'verified_requirement_registry_entries': sum(
                x.get('verification_status') in VERIFIED for x in requirements[v]['entries']),
            'metadata_registry_state': metadata[v]['status'],
            'requirements_registry_state': requirements[v]['status'],
            'value_set_link_statuses': dict(sorted(value_statuses.items())),
            'requirement_link_statuses': dict(sorted(requirement_statuses.items())),
            'xsd_statuses': dict(sorted(xsd_statuses.items())),
        }
    return {
        'audit_format_version': FORMAT_VERSION,
        'purpose': 'version_scoped_declarative_evidence_qa',
        'catalogue_sha256': catalogue[1], 'source_registry_sha256': sources['sha256'],
        'source_registry_status': sources['status'],
        'standard_values_sha256': standards['sha256'],
        'registries': {
            v: {'metadata_path': metadata[v].get('source'), 'metadata_sha256': metadata[v]['sha256'],
                'metadata_status': metadata[v]['status'],
                'requirements_path': requirements[v].get('source'),
                'requirements_sha256': requirements[v]['sha256'],
                'requirements_status': requirements[v]['status']}
            for v in VERSIONS
        },
        'summary': summary, 'tests': test_records, 'xsd': schemas,
        'noark_conformance_verified': False,
        'saxon_semantic_equivalence_verified': False,
        'note': ('Ingen kryssversjon-arv. KDRS query_subtype er ikke et normativt bevis. '
                 'Ingen uverifiserte XSD-, metadata- eller kravlenker oppgraderes automatisk.'),
    }


def filter_version_rows(rows: Iterable[dict[str, Any]], report: dict[str, Any],
                        *, version: str = '', state: str = '') -> tuple[dict[str, Any], ...]:
    """Filter existing a1 Work rows without touching the stored Work result."""
    if version and version not in VERSIONS:
        raise ValueError('Ukjent Noark-versjon: ' + version)
    if state not in ('', 'has_value_set_link', 'has_requirement_reference', *VERSION_STATUSES):
        raise ValueError('Ukjent versjonsfilter: ' + state)
    out = []
    for item in rows:
        row = item['row']
        summary = (report.get('tests') or {}).get(row.test_id, {}).get('by_version', {})
        selected = [summary.get(version)] if version else [summary.get(v) for v in VERSIONS]
        selected = [r for r in selected if isinstance(r, dict)]
        if state == 'has_value_set_link':
            accepted = any(any(x.get('status') == 'registered_value_set_link'
                               for x in r.get('value_set_references', ())) for r in selected)
        elif state == 'has_requirement_reference':
            accepted = any(any(x.get('status') == 'source_verified_requirement_reference'
                               for x in r.get('normative_requirement_references', ())) for r in selected)
        else:
            accepted = not state or any(r.get('status') == state for r in selected)
        if accepted:
            out.append(item)
    return tuple(out)


def main(argv: list[str] | None = None) -> int:
    import argparse
    parser = argparse.ArgumentParser(description='Noark 5 v3.1 / 4.0 / 5.0: kildebasert versjonsaudit (a3)')
    parser.add_argument('--project', type=Path, default=repo_root())
    parser.add_argument('--version', choices=VERSIONS, default='')
    parser.add_argument('--schema-root', type=Path, default=None,
                        help='Valgfritt lokalt XSD-bibliotek. Ingen automatisk nedlasting.')
    parser.add_argument('--output', type=Path, default=None,
                        help='Eksplisitt rapportsti; ingen skriveoperasjoner i Source/Work.')
    opts = parser.parse_args(argv)
    try:
        report = build_version_audit(opts.project, schema_root=opts.schema_root)
        if opts.version:
            report['selected_version'] = opts.version
            report['tests'] = {
                key: {**item, 'by_version': {opts.version: item['by_version'][opts.version]}}
                for key, item in report['tests'].items()
            }
            report['summary'] = {opts.version: report['summary'][opts.version]}
        content = json.dumps(report, ensure_ascii=False, indent=2) + '\n'
        if opts.output:
            path = opts.output.expanduser().resolve()
            if path.is_dir() or (opts.project.resolve() == path or path.is_relative_to(opts.project.resolve())):
                raise ValueError('Rapport kan ikke skrives i DWM-repoet.')
            if opts.schema_root and path.is_relative_to(opts.schema_root.resolve()):
                raise ValueError('Rapport kan ikke skrives i XSD-kilden.')
            if path.exists():
                raise ValueError('Rapportfilen finnes allerede; overskriving er sperret.')
            path.write_text(content, encoding='utf-8')
        else:
            print(content)
        return 0
    except (ValueError, OSError, RuntimeError) as exc:
        parser.exit(2, 'FEIL: ' + str(exc) + '\n')


if __name__ == '__main__':
    raise SystemExit(main())
