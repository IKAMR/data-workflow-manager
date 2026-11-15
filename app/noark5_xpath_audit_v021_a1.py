"""Read-only Noark 5 / KDRS XPath catalogue audit and Work-result projection.

Separate four claims: reference-job identity, executable DWM definition,
recorded execution, and source-verified normative requirement.  Never infer
conformance from a successful XPath metric or from missing metadata.
"""
from __future__ import annotations

from collections import Counter
import hashlib
from dataclasses import dataclass
import json
from pathlib import Path
import re
from typing import Any, Iterable
import xml.etree.ElementTree as ET


VERSIONS = ('3.1', '4.0', '5.0')
CATALOG_REL = Path('config/noark5/tests/xpath_catalog_2026_05_26.json')
SOURCES = {
    'Standard': 'docs/reference/kdrs-query/xml-queries_noark5_2026-05-26.txt',
    'U1': 'docs/reference/kdrs-query/xml-queries_noark5_2026-05-26_U1.txt',
    'U2': 'docs/reference/kdrs-query/xml-queries_noark5_2026-05-26_U2.txt',
}
SCHEMAS = ('arkivstruktur.xsd', 'endringslogg.xsd', 'loependeJournal.xsd',
           'metadatakatalog.xsd', 'offentligJournal.xsd')
XSD = '{http://www.w3.org/2001/XMLSchema}'
MAX_JSON_BYTES = 12_000_000
STATUS_ORDER = ('FEIL', 'WARNING', 'NOTE', 'MANGLER', 'UKJENT',
                'UTFORT', 'IKKE_KJORT', 'REGRESJON')
JOB_LINE = re.compile(r'^\s*job_id\s*=\s*([A-Za-z0-9_.-]+)\s*$', re.M)
XPATH_TOKENS = re.compile(r'[A-Za-z_][A-Za-z_0-9]*')


@dataclass(frozen=True)
class CatalogueRow:
    test_id: str
    legacy_id: str
    name: str
    source_xml: str
    scope: str
    versions: tuple[str, ...]
    version_basis: str
    definition_status: str
    lifecycle_role: str
    test_point: str
    paths: tuple[str, ...]
    standard_checks: tuple[str, ...]
    definition: dict[str, Any]


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _read_json(path: Path, *, within: Path | None = None,
               limit: int = MAX_JSON_BYTES) -> dict[str, Any] | None:
    """Reject paths outside the trusted root, symlink escapes, and huge files."""
    try:
        source = path.resolve(strict=True)
        if within is not None and not source.is_relative_to(within.resolve(strict=True)):
            return None
        if not source.is_file() or source.stat().st_size > limit:
            return None
        value = json.loads(source.read_text(encoding='utf-8-sig'))
        return value if isinstance(value, dict) else None
    except (OSError, ValueError, TypeError, RuntimeError, UnicodeError):
        return None


def _all_paths(execution: dict[str, Any]) -> tuple[str, ...]:
    """List explicit XPath strings; special-handler XPath is not in the JSON."""
    paths = []

    def visit(node: Any, *, parent: str = '') -> None:
        if isinstance(node, dict):
            for key, value in node.items():
                if isinstance(value, str) and (key in ('expression', 'select', 'where')
                                               or parent == 'fields'):
                    if value not in paths:
                        paths.append(value)
                else:
                    visit(value, parent=key)
        elif isinstance(node, list):
            for value in node:
                visit(value, parent=parent)

    visit(execution)
    return tuple(paths)


def load_rows(project: Path | None = None) -> tuple[CatalogueRow, ...]:
    root = Path(project) if project is not None else repo_root()
    doc = _read_json(root / CATALOG_REL, within=root)
    if not doc or not isinstance(doc.get('tests'), list):
        raise ValueError('XPath-katalogen mangler eller kan ikke leses.')
    rows = []
    seen = set()
    for t in doc['tests']:
        if not isinstance(t, dict) or not isinstance(t.get('legacy'), dict):
            raise ValueError('Ugyldig testdefinisjon i XPath-katalogen.')
        ident = str(t.get('test_id') or '')
        if not ident or ident in seen:
            raise ValueError('Mangler test-ID eller duplikat i XPath-katalogen: ' + ident)
        seen.add(ident)
        rows.append(CatalogueRow(
            test_id=ident, legacy_id=str(t['legacy'].get('job_id') or ''),
            name=str(t.get('name') or ''), source_xml=str(t.get('source_xml') or ''),
            scope=str(t.get('scope') or ''),
            versions=tuple(str(v) for v in t.get('noark_versions') or ()),
            version_basis=str(t.get('version_basis') or ''),
            definition_status=str(t.get('status') or ''),
            lifecycle_role=str((t.get('lifecycle') or {}).get('role') or ''),
            test_point=str(t.get('normalized_test_point') or
                           t['legacy'].get('test_point') or ''),
            paths=_all_paths(t.get('execution') or {}),
            standard_checks=tuple(str(c.get('value_set_id') or '')
                                  for c in t.get('standard_value_checks') or ()
                                  if isinstance(c, dict)),
            definition=t,
        ))
    return tuple(rows)


def legacy_job_audit(project: Path | None = None) -> dict[str, Any]:
    root = Path(project) if project is not None else repo_root()
    catalog = load_rows(root)
    all_ids: list[str] = []
    source_counts = {}
    unavailable = []
    for label, rel in SOURCES.items():
        source = root / rel
        try:
            ids = JOB_LINE.findall(source.read_text(encoding='utf-8-sig'))
        except (OSError, UnicodeError):
            unavailable.append(rel)
            continue
        all_ids.extend(ids)
        source_counts[label] = len(ids)
    unique_source = set(all_ids)
    defined = {entry.legacy_id for entry in catalog}
    counts = Counter(all_ids)
    return {
        'source_job_occurrences': len(all_ids),
        'source_unique_job_ids': len(unique_source),
        'catalog_tests': len(catalog),
        'source_counts': source_counts,
        'duplicate_source_ids': sorted(key for key, value in counts.items() if value > 1),
        'not_in_dwm_catalog': sorted(unique_source - defined),
        'dwm_only_ids': sorted(defined - unique_source),
        'source_files_missing': unavailable,
        'verified_id_parity': not unavailable and not (unique_source - defined),
        'expression_parity_verified': False,
        'note': 'Jobb-ID-dekning beviser ikke semantisk likhet mellom KDRS XPath 2/3 og lxml-beregningene.',
    }


def legacy_source_expression(row: CatalogueRow, project: Path | None = None) -> str:
    """Read the original, bounded Saxon query block by its KDRS job ID.

    Original expression and DWM's lxml/Python implementation are kept side
    by side; neither is claimed equivalent. DWM native extensions have no
    original KDRS expression.
    """
    if row.legacy_id == 'DWM-AU01':
        return 'DWM-tillegg; finnes ikke som egen KDRS Query-jobb.'
    source_id = 'U1' if row.legacy_id == 'U01' else 'U2' if row.legacy_id == 'U02' else 'Standard'
    project = Path(project) if project is not None else repo_root()
    source = project / SOURCES[source_id]
    try:
        if source.stat().st_size > 180_000:
            return 'KDRS-kildefilen er for stor til visningen.'
        content = source.read_text(encoding='utf-8-sig')
    except (OSError, UnicodeError):
        return 'Original KDRS-definisjon er ikke tilgjengelig lokalt.'
    for block in content.split('[XML_QUERY]')[1:]:
        found = JOB_LINE.search(block)
        if not found or found.group(1) != row.legacy_id:
            continue
        start = block.find('#START#')
        end = block.find('#STOP#', start + 7)
        if start == -1 or end == -1:
            return 'Fant KDRS-jobben, men ikke et komplett #START#/#STOP#-uttrykk.'
        return block[start + len('#START#'):end].strip()
    return 'Fant ikke opprinnelig KDRS-uttrykk for jobb-ID ' + row.legacy_id + '.'


def _latest_index(snapshot) -> tuple[Path | None, dict[str, Any] | None, str]:
    """Only use indexed Work artifacts already discovered by the result center."""
    try:
        work = Path(snapshot.job.work).resolve(strict=True)
    except (OSError, ValueError, RuntimeError, AttributeError):
        return None, None, 'Work er ikke tilgjengelig.'
    candidates = []
    for artifact in getattr(snapshot.results, 'artifacts', ()):
        if (getattr(artifact, 'category', '') != 'XPath / Noark 5'
                or getattr(artifact, 'title', '') != 'index.json'):
            continue
        relative = Path(str(getattr(artifact, 'relative_path', '')).replace('\\', '/'))
        if len(relative.parts) != 4 or relative.parts[:2] != ('noark5_tests', 'xpath'):
            continue
        if relative.parts[-1] != 'index.json':
            continue
        candidates.append((float(getattr(artifact, 'modified_at', 0)), work / relative))
    for _modified, path in sorted(candidates, key=lambda item: item[0], reverse=True):
        index = _read_json(path, within=work, limit=3_000_000)
        if index is not None and isinstance(index.get('tests'), list):
            return path, index, ''
    return None, None, 'Ingen lagret XPath-indeks i valgt Work.'


def _result_for(index_path: Path, index_entry: dict, work: Path,
                test_id: str) -> dict[str, Any] | None:
    name = str(index_entry.get('file') or '').replace('\\', '/')
    rel = Path(name)
    if (rel.is_absolute() or len(rel.parts) != 2 or rel.parts[0] != 'results'
            or rel.suffix != '.json' or '..' in rel.parts):
        return None
    result = _read_json(index_path.parent / rel, within=work, limit=3_000_000)
    if not result or str(result.get('test_id')) != test_id:
        return None
    return result


def classify_execution(row: CatalogueRow, index_entry: dict | None,
                       result: dict | None, *, version: str = '') -> tuple[str, tuple[str, ...]]:
    """Never translate a successful metric into normative Noark compliance."""
    if index_entry is None:
        if row.lifecycle_role == 'development_regression_reference':
            return 'REGRESJON', ('U1/U2 er referanse for utvikling og regresjon, ikke ordin\u00e6r kj\u00f8ring.',)
        return 'IKKE_KJORT', ('Ingen lagret kj\u00f8ring for denne testen.',)
    state = str(index_entry.get('status') or '')
    if state == 'error':
        return 'FEIL', (str((result or {}).get('error') or 'Testkj\u00f8ring feilet.'),)
    if state == 'source_missing':
        missing = ', '.join((result or {}).get('missing_sources') or ())
        return 'MANGLER', ('Kilde-XML mangler' + (': ' + missing if missing else '.'),)
    if state in ('disabled_by_legacy_source', 'not_run'):
        return 'IKKE_KJORT', ('Testen ble ikke kj\u00f8rt.',)
    if state != 'ok':
        return 'UKJENT', ('Ukjent lagret teststatus: ' + state,)
    if result is None:
        return 'UKJENT', ('Resultatfil kan ikke leses eller identitet stemmer ikke.',)
    values = result.get('values') or {}
    if not isinstance(values, dict):
        return 'UKJENT', ('Testresultatet har ukjent format.',)
    reasons = []
    comparison = values.get('_reconciliation_summary') or {}
    if isinstance(comparison, dict) and int(comparison.get('mismatches') or 0) > 0:
        reasons.append('Avstemming mellom uttrekk og arkivdeler gir avvik som m\u00e5 unders\u00f8kes.')
    if version in VERSIONS:
        standard_checks = values.get('_standard_values') or {}
        for key, check in standard_checks.items():
            if not isinstance(check, dict):
                continue
            item = (check.get('versions') or {}).get(version) or {}
            if item.get('status') == 'additional_observed_values':
                reasons.append('Ekstra observerte verdier for ' + str(key) +
                               ' mot v' + version + ' (krever faglig vurdering).')
    if reasons:
        return 'WARNING', tuple(reasons)
    if version in VERSIONS:
        standard_checks = values.get('_standard_values') or {}
        if any(((check.get('versions') or {}).get(version) or {}).get('status') in
               ('no_observed_values', 'reference_missing')
               for check in standard_checks.values() if isinstance(check, dict)):
            return 'NOTE', ('Ingen observerte verdier eller manglende versjonsreferanse; ikke automatisk feil.',)
    return 'UTFORT', ('Teknisk kj\u00f8rt. Inneb\u00e6rer ikke godkjent arkivuttrekk.',)


def project_work_rows(rows: Iterable[CatalogueRow], snapshot=None,
                      *, version: str = '') -> tuple[dict[str, Any], ...]:
    if version and version not in VERSIONS:
        raise ValueError('Ukjent Noark-versjon: ' + version)
    index_path, index, note = _latest_index(snapshot) if snapshot else (None, None, 'Ingen jobb valgt.')
    by_id = {str(item.get('test_id')): item for item in (index or {}).get('tests', ())
             if isinstance(item, dict)}
    work = Path(snapshot.job.work) if snapshot and index else None
    projected = []
    for row in rows:
        entry = by_id.get(row.test_id)
        detail = (_result_for(index_path, entry, work, row.test_id)
                  if index_path is not None and entry is not None and work is not None else None)
        severity, reasons = classify_execution(row, entry, detail, version=version)
        projected.append({
            'row': row, 'severity': severity, 'reasons': reasons,
            'index_entry': entry, 'result': detail,
            'index_path': str(index_path) if index_path else '',
            'run_note': note,
        })
    return tuple(projected)


def filter_work_rows(rows: Iterable[dict[str, Any]], *, version: str = '',
                     severity: str = '', source: str = '', query: str = '') -> tuple[dict[str, Any], ...]:
    needle = query.strip().casefold()
    out = []
    for item in rows:
        row: CatalogueRow = item['row']
        if version and version not in row.versions:
            continue
        if severity and item['severity'] != severity:
            continue
        if source == 'U1/U2' and row.legacy_id not in ('U01', 'U02'):
            continue
        if source == 'Standard' and row.legacy_id in ('U01', 'U02', 'DWM-AU01'):
            continue
        if source == 'DWM' and row.legacy_id != 'DWM-AU01':
            continue
        haystack = ' '.join((row.test_id, row.legacy_id, row.name, row.source_xml,
                             row.test_point, row.scope, ' '.join(row.paths),
                             ' '.join(row.standard_checks))).casefold()
        if needle and needle not in haystack:
            continue
        out.append(item)
    return tuple(sorted(out, key=lambda value:
                 (STATUS_ORDER.index(value['severity']) if value['severity'] in STATUS_ORDER
                  else len(STATUS_ORDER), value['row'].test_id)))


def candidate_schema_root(project: Path | None = None) -> Path | None:
    """Only look at the explicitly known sibling source repository, no download."""
    root = Path(project) if project else repo_root()
    sibling = root.parent / 'digital-archive-workflow' / 'docs' / 'kilder' / 'noark' / 'noark5'
    return sibling if (sibling / 'v3.1' / 'schemas').is_dir() else None


def schema_inventory(source_root: str | Path) -> dict[str, Any]:
    """Inventory XSD declarations, not a claim of complete Noark requirements."""
    root = Path(source_root)
    if (root / 'docs' / 'kilder' / 'noark' / 'noark5').is_dir():
        root = root / 'docs' / 'kilder' / 'noark' / 'noark5'
    result = {'root': str(root), 'versions': {}, 'missing': [], 'errors': []}
    if not root.is_dir():
        return {**result, 'missing': [f'v{v}/schemas/{name}' for v in VERSIONS
                                      for name in SCHEMAS]}
    for version in VERSIONS:
        part = {}
        for name in SCHEMAS:
            path = root / ('v' + version) / 'schemas' / name
            rel = 'v' + version + '/schemas/' + name
            if not path.is_file():
                result['missing'].append(rel)
                continue
            try:
                if path.stat().st_size > 2_000_000:
                    raise ValueError('XSD er over st\u00f8rrelsesgrensen.')
                # Standard-library ElementTree does not load network entities.
                xml = ET.parse(path).getroot()
                if xml.tag != XSD + 'schema':
                    raise ValueError('Ikke et XSD-skjema.')
                elements = [node.attrib['name'] for node in xml.iter(XSD + 'element')
                            if 'name' in node.attrib]
                part[name] = {
                    'elements': len(elements), 'distinct_elements': tuple(sorted(set(elements))),
                    'declared_schema_version': xml.attrib.get('version', ''),
                    'target_namespace': xml.attrib.get('targetNamespace', ''),
                    'source': str(path),
                    'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
                }
            except (OSError, ET.ParseError, ValueError) as exc:
                result['errors'].append(rel + ': ' + str(exc))
        result['versions'][version] = part
    return result


def declarative_xpath_names(rows: Iterable[CatalogueRow]) -> set[str]:
    """Only lexical tokens from JSON XPath paths; special Python handlers excluded."""
    return {token for row in rows for path in row.paths for token in XPATH_TOKENS.findall(path)}


def schema_lexical_coverage(schema: dict[str, Any], rows: Iterable[CatalogueRow]) -> dict:
    entries = tuple(rows)
    result = {}
    for v, files in schema.get('versions', {}).items():
        referenced = declarative_xpath_names(row for row in entries if v in row.versions)
        result[v] = {}
        for name, doc in files.items():
            elements = set(doc.get('distinct_elements') or ())
            result[v][name] = {
                'declared_elements': len(elements),
                'mentioned_in_declarative_xpaths': len(elements & referenced),
                'not_mentioned_in_declarative_xpaths': tuple(sorted(elements - referenced)),
                'note': 'Tekstlig navnetreff er ikke lik full XPath-/kravdekning; XSD-validering er separat.',
            }
    return result



def xpath_syntax_audit(rows: Iterable[CatalogueRow]) -> dict[str, Any]:
    """Compile declared XPath 1.0 selectors, never execute against Source XML.

    Hand-written Python special handlers and XPath 2/3 legacy originals are
    outside this contract. A successful compile is NOT semantic equivalence.
    """
    try:
        from lxml import etree
    except ImportError:
        return {'status': 'lxml_missing', 'compiled': 0, 'invalid': []}
    attempted = 0
    invalid = []
    for row in rows:
        for expression in row.paths:
            attempted += 1
            try:
                etree.XPath(expression)
            except etree.XPathSyntaxError as exc:
                invalid.append({'test_id': row.test_id, 'expression': expression,
                                'error': str(exc)})
    return {'status': 'checked', 'compiled': attempted - len(invalid),
            'attempted': attempted, 'invalid': invalid,
            'note': 'Kompilering beviser ikke likhet med opprinnelig KDRS Saxon XPath.'}


def catalogue_summary(rows: Iterable[CatalogueRow]) -> dict:
    entries = tuple(rows)
    return {
        'tests': len(entries),
        'active': sum(x.definition_status == 'active' for x in entries),
        'regression_reference': sum(x.lifecycle_role == 'development_regression_reference'
                                    for x in entries),
        'explicit_xpaths': sum(len(x.paths) for x in entries),
        'version_unverified': sum(x.version_basis == 'master_query_subtype_needs_qa'
                                  for x in entries),
        'source_xml': dict(Counter(x.source_xml for x in entries)),
        'standard_value_checks': sum(len(x.standard_checks) for x in entries),
    }


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='Read-only DWM Noark 5 XPath source audit')
    parser.add_argument('--project', type=Path, default=repo_root())
    parser.add_argument('--schema-root', type=Path, default=None)
    parser.add_argument('--output', type=Path, default=None)
    parser.add_argument('--compile-xpath', action='store_true')
    opts = parser.parse_args()
    data = {'catalogue': catalogue_summary(load_rows(opts.project)),
            'legacy': legacy_job_audit(opts.project)}
    if opts.compile_xpath:
        data['xpath_syntax'] = xpath_syntax_audit(load_rows(opts.project))
    library = opts.schema_root or candidate_schema_root(opts.project)
    if library:
        schemas = schema_inventory(library)
        data['schemas'] = {
            'available_files': sum(map(len, schemas['versions'].values())),
            'missing': schemas['missing'], 'errors': schemas['errors'],
            'lexical_coverage': schema_lexical_coverage(schemas, load_rows(opts.project)),
        }
    body = json.dumps(data, ensure_ascii=False, indent=2) + '\n'
    if opts.output:
        opts.output.write_text(body, encoding='utf-8')
    else:
        print(body)
