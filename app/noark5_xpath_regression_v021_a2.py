"""v0.2.1-a2: read-only KDRS expression crosswalk and DWM XPath regression.

Three separate kinds of evidence, never merged into a conformance verdict:
* static source fragments in the original KDRS Query / Saxon definitions;
* DWM original lxml/Python engine versus DWM's accelerated engine on the same XML;
* saved U1/U2-vs-individual comparisons from an explicitly selected Work run.

No automatic test runs or writes in Source/Work. Engine comparison is an explicit
CLI operation and writes intermediate output only into a temporary directory.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import tempfile
from typing import Any, Iterable

from version import VERSION

from app.noark5_xpath_audit_v021_a1 import (
    CatalogueRow, JOB_LINE, MAX_JSON_BYTES, SOURCES, load_rows, repo_root, _read_json,
)

FORMAT_VERSION = 1
SOURCE_MAX_BYTES = 512_000
VALID_COMPARISON = frozenset({'match', 'mismatch', 'not_comparable'})
REGRESSION_DIR = Path('noark5_tests/xpath_regression')


def _digest(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':'),
                      default=str, allow_nan=True)


def _source_blocks(project: Path) -> dict[str, dict[str, Any]]:
    """Read the three committed reference texts and retain source provenance.

    U1/U2 are intentionally read from their own files, even when copies also
    exist in Standard. Never silently substitute one source for another.
    """
    out: dict[str, dict[str, Any]] = {}
    for label, relative in SOURCES.items():
        path = project / relative
        meta: dict[str, Any] = {'source': relative, 'group': label, 'jobs': {}}
        try:
            real = path.resolve(strict=True)
            if not real.is_relative_to(project.resolve(strict=True)):
                raise ValueError('Kildestien peker utenfor prosjektet.')
            if not real.is_file() or real.stat().st_size > SOURCE_MAX_BYTES:
                raise ValueError('Kildeteksten mangler eller er for stor.')
            content = real.read_bytes()
            source = content.decode('utf-8-sig')
            meta['sha256'] = _digest(content)
        except (OSError, ValueError, UnicodeError, RuntimeError) as exc:
            meta['error'] = f'{type(exc).__name__}: {exc}'
            out[label] = meta
            continue
        for block in source.split('[XML_QUERY]')[1:]:
            job = JOB_LINE.search(block)
            if job is None:
                continue
            identity = job.group(1)
            begin = block.find('#START#')
            end = block.find('#STOP#', begin + len('#START#')) if begin >= 0 else -1
            source_match = re.search(r'^\s*source\s*=\s*([^\r\n]*)', block, re.M)
            expr = (block[begin + len('#START#'):end].strip()
                    if begin >= 0 and end > begin else None)
            if identity in meta['jobs']:
                meta.setdefault('duplicate_job_ids', []).append(identity)
            else:
                meta['jobs'][identity] = {
                    'expression': expr,
                    'original_source_xml': source_match.group(1).strip() if source_match else '',
                    'expression_sha256': _digest(expr.encode('utf-8')) if expr else None,
                }
        out[label] = meta
    return out


def _code_compact(expression: str) -> tuple[str, list[bool]]:
    """Remove whitespace outside strings and track whether each char is code.

    Unlike whitespace-only matching, this keeps literal contents, so
    @type='sak' cannot match @type='reg' or a similarly sized string.
    """
    chars: list[str] = []
    code: list[bool] = []
    quote: str | None = None
    i = 0
    while i < len(expression):
        c = expression[i]
        is_code = quote is None
        if quote is not None:
            chars.append(c)
            code.append(False)
            if c == quote:
                if i + 1 < len(expression) and expression[i + 1] == quote:
                    chars.append(expression[i + 1])
                    code.append(False)
                    i += 1
                else:
                    quote = None
        elif c in ('"', "'"):
            quote = c
            chars.append(c)
            code.append(True)
        elif not c.isspace():
            chars.append(c)
            code.append(True)
        i += 1
    return ''.join(chars), code


def _fragment_occurs(expression: str, original: str) -> bool:
    expr, _ = _code_compact(expression)
    source, code = _code_compact(original)
    if not expr:
        return False
    start = 0
    while True:
        at = source.find(expr, start)
        if at < 0:
            return False
        if code[at] and (at == 0 or not re.match(r'[A-Za-z0-9_.-]', source[at - 1])):
            return True
        start = at + 1


def _dwm_paths(row: CatalogueRow) -> tuple[dict[str, str], ...]:
    execution = row.definition.get('execution') or {}
    result = []
    for name in ('metrics', 'archive_part_metrics'):
        for item in execution.get(name) or []:
            if not isinstance(item, dict):
                continue
            if item.get('type', 'xpath') == 'xpath' and isinstance(item.get('expression'), str):
                result.append({'scope': name, 'id': str(item.get('id') or ''),
                               'expression': item['expression']})
    return tuple(result)


def _fragment_status(expression: str, original: str) -> str:
    if not expression or not original:
        return 'not_found'
    if _fragment_occurs(expression, original):
        return 'literal_fragment_present'
    # DWM strips namespace prefixes from xsi:type in an isolated in-memory
    # copy. This is a traceability hint, not proof of XPath equivalence.
    if '@type' in expression:
        if _fragment_occurs(expression.replace('@type', '@xsi:type'), original):
            return 'namespace_rewrite_candidate'
    return 'not_found'


def source_crosswalk(rows: Iterable[CatalogueRow],
                     project: Path | None = None) -> dict[str, Any]:
    root = (Path(project) if project is not None else repo_root()).resolve()
    sources = _source_blocks(root)
    by_test = {}
    for row in rows:
        if row.legacy_id == 'DWM-AU01':
            by_test[row.test_id] = {
                'test_id': row.test_id, 'legacy_id': row.legacy_id,
                'source_group': 'DWM', 'status': 'dwm_extension',
                'note': 'DWM-egen test uten KDRS-original.', 'metrics': [],
            }
            continue
        group = 'U1' if row.legacy_id == 'U01' else 'U2' if row.legacy_id == 'U02' else 'Standard'
        bundle = sources[group]
        source = bundle['jobs'].get(row.legacy_id)
        status = 'source_unavailable' if 'error' in bundle else 'source_not_found'
        result = {
            'test_id': row.test_id, 'legacy_id': row.legacy_id,
            'source_group': group, 'reference_file': bundle['source'],
            'reference_sha256': bundle.get('sha256'), 'source_xml': row.source_xml,
            'catalog_execution_sha256': _digest(_canonical_json(row.definition.get('execution') or {}).encode('utf-8')),
            'status': status, 'metrics': [],
            'noark_versions_declared': list(row.versions),
            'version_basis': row.version_basis,
        }
        if source is None:
            by_test[row.test_id] = result
            continue
        original = source.get('expression')
        result['original_source_xml'] = source['original_source_xml']
        result['original_expression_sha256'] = source['expression_sha256']
        result['original_expression_available'] = original is not None
        if original is None:
            result['status'] = 'expression_incomplete'
            by_test[row.test_id] = result
            continue
        entries = _dwm_paths(row)
        result['metrics'] = [{**item,
                              'fragment_status': _fragment_status(item['expression'], original)}
                             for item in entries]
        direct = sum(x['fragment_status'] == 'literal_fragment_present' for x in result['metrics'])
        normalized = sum(x['fragment_status'] == 'namespace_rewrite_candidate' for x in result['metrics'])
        result['xpath_metric_count'] = len(entries)
        result['literal_fragments'] = direct
        result['namespace_candidates'] = normalized
        result['without_literal_match'] = len(entries) - direct
        result['source_xml_match'] = row.source_xml == source['original_source_xml']
        if not result['source_xml_match']:
            result['status'] = 'source_xml_conflict'
        elif not entries:
            result['status'] = 'special_or_composite_review'
        elif direct == len(entries):
            result['status'] = 'all_literal_fragments_found'
        elif direct or normalized:
            result['status'] = 'partial_fragments_found'
        else:
            result['status'] = 'manual_semantics_review'
        result['note'] = ('Kun leksikalsk sporbarhet. KDRS er Saxon/XPath 2/3, '
                          'DWM er lxml/XPath 1.0 og Python; ingen semantisk ekvivalens attestert.')
        by_test[row.test_id] = result
    counts = Counter(v['status'] for v in by_test.values())
    return {
        'audit_format_version': FORMAT_VERSION,
        'purpose': 'static_kdrs_to_dwm_expression_traceability',
        'provenance': {k: {'file': v['source'], 'sha256': v.get('sha256'),
                           'error': v.get('error'), 'duplicate_job_ids': v.get('duplicate_job_ids', [])}
                       for k, v in sources.items()},
        'summary': {'tests': len(by_test), 'statuses': dict(sorted(counts.items())),
                    'literal_fragments': sum(x.get('literal_fragments', 0) for x in by_test.values()),
                    'namespace_candidates': sum(x.get('namespace_candidates', 0) for x in by_test.values()),
                    'semantic_equivalence_verified': 0},
        'tests': by_test,
    }


def _safe_work_index(work: Path, index: str | Path) -> Path | None:
    """Permit only a direct regression-run index under this Work, no symlink escape."""
    try:
        root = work.resolve(strict=True)
        candidate = Path(index)
        if candidate.is_absolute():
            candidate = candidate.resolve(strict=True)
        else:
            # Reject traversal rather than resolving and re-accepting it.
            if '..' in candidate.parts or candidate.drive:
                return None
            candidate = (root / candidate).resolve(strict=True)
        if not candidate.is_relative_to(root) or not candidate.is_file():
            return None
        relative = candidate.relative_to(root)
        if len(relative.parts) != 4 or relative.parts[:2] != REGRESSION_DIR.parts or relative.name != 'index.json':
            return None
        return candidate
    except (OSError, ValueError, RuntimeError):
        return None


def discover_saved_regressions(work: Path | str) -> list[dict[str, Any]]:
    """Do not select among historical runs; list only named index candidates."""
    root = Path(work)
    folder = root / REGRESSION_DIR
    if not folder.is_dir():
        return []
    output = []
    try:
        candidates = list(folder.glob('*/index.json'))
    except OSError:
        return []
    for candidate in candidates:
        safe = _safe_work_index(root, candidate)
        if safe is None:
            continue
        doc = _read_json(safe, within=root, limit=3_000_000)
        if not doc or doc.get('execution_profile') != 'regression':
            continue
        output.append({
            'relative_index': safe.relative_to(root.resolve(strict=True)).as_posix(),
            'test_count': len(doc.get('tests') or []),
            'has_legacy_comparison': isinstance(doc.get('legacy_regression_comparison'), dict),
            'modified_ns': safe.stat().st_mtime_ns,
        })
    return sorted(output, key=lambda item: item['relative_index'])


def inspect_saved_regression(work: Path | str, index: Path | str) -> dict[str, Any]:
    """Recompute counts rather than trust stored summary or classify missing as OK."""
    root = Path(work)
    selected = _safe_work_index(root, index)
    if selected is None:
        raise ValueError('Velg index.json under Work/noark5_tests/xpath_regression/<run>.')
    doc = _read_json(selected, within=root, limit=3_000_000)
    if doc is None or doc.get('execution_profile') != 'regression':
        raise ValueError('Ugyldig regresjonsindeks eller feil kjøreprofil.')
    link = doc.get('legacy_regression_comparison')
    reference = link.get('file') if isinstance(link, dict) else None
    if not isinstance(reference, str) or Path(reference).name != reference or not reference.endswith('.json'):
        return {'status': 'not_available', 'index': selected.relative_to(root.resolve()).as_posix(),
                'note': 'Ingen gyldig U1/U2-sammenligning i valgt indeks.'}
    comparison_path = selected.parent / reference
    comparison = _read_json(comparison_path, within=root, limit=MAX_JSON_BYTES)
    if comparison is None:
        return {'status': 'not_available', 'index': selected.relative_to(root.resolve()).as_posix(),
                'note': 'Sammenligningsfil mangler, er for stor eller kan ikke leses.'}
    statuses = Counter()
    findings = []
    def accept(key: str, entry: Any):
        status = str(entry.get('status') or '') if isinstance(entry, dict) else ''
        if status not in VALID_COMPARISON:
            status = 'unknown'
        statuses[status] += 1
        if status != 'match':
            findings.append({'check': key, 'status': status,
                             'error': str(entry.get('error') or '')[:350] if isinstance(entry, dict) else '',
                             'legacy': _preview(entry.get('legacy')) if isinstance(entry, dict) else '',
                             'canonical': _preview(entry.get('canonical')) if isinstance(entry, dict) else ''})
    whole = comparison.get('whole_extraction') or {}
    if not isinstance(whole, dict):
        raise ValueError('U1/U2-data har ugyldig whole_extraction-format.')
    for name, row in whole.items():
        accept('whole/' + name, row)
    parts = comparison.get('archive_parts') or {}
    if not isinstance(parts, dict):
        raise ValueError('U1/U2-data har ugyldig archive_parts-format.')
    for key, value in parts.items():
        checks = value.get('checks') if isinstance(value, dict) else None
        if not isinstance(checks, dict):
            accept('archive_part/' + key, None)
        else:
            for name, entry in checks.items():
                accept('archive_part/' + str(key) + '/' + name, entry)
    saved = comparison.get('summary') or {}
    counts = {'checks': sum(statuses.values()), 'matches': statuses['match'],
              'mismatches': statuses['mismatch'], 'not_comparable': statuses['not_comparable'],
              'unknown': statuses['unknown']}
    disagree = any(saved.get(k) != counts[k] for k in ('checks', 'matches', 'mismatches', 'not_comparable'))
    if counts['checks'] == 0:
        overall = 'no_comparisons'
    elif disagree or counts['unknown']:
        overall = 'invalid_summary'
    elif counts['mismatches']:
        overall = 'mismatch'
    elif counts['not_comparable']:
        overall = 'incomplete'
    else:
        overall = 'match'
    return {
        'status': overall,
        'index': selected.relative_to(root.resolve()).as_posix(),
        'comparison_file': comparison_path.relative_to(root.resolve()).as_posix(),
        'comparison_sha256': _digest(comparison_path.read_bytes()),
        'counts': counts, 'saved_counts_disagree': disagree,
        'findings': findings[:150], 'findings_truncated': len(findings) > 150,
        'note': 'U1/U2 mot individuelle DWM-resultater i én valgt kjøring; ikke direkte utføring av KDRS/Saxon-originalen.',
    }


def _preview(value: Any, length: int = 240) -> str:
    if value is None:
        return ''
    rendered = _canonical_json(value)
    return rendered if len(rendered) <= length else rendered[:length] + '...'


def compare_dwm_result_dirs(baseline_dir: Path, accelerated_dir: Path) -> dict[str, Any]:
    """Compare original engine and fast engine by stable test-ID and full values.

    Diagnostics and timing intentionally excluded. A missing XML source or two
    matching execution failures count as unverified, not equal outputs.
    """
    original = _read_json(baseline_dir / 'index.json', within=baseline_dir, limit=3_000_000)
    fast = _read_json(accelerated_dir / 'index.json', within=accelerated_dir, limit=3_000_000)
    if original is None or fast is None:
        raise ValueError('Mangler lesbare indeksfiler fra begge motorkjøringer.')
    def by_id(doc):
        found = {}
        for row in doc.get('tests') or []:
            if not isinstance(row, dict) or not isinstance(row.get('test_id'), str):
                raise ValueError('Ugyldig testpost i motorindeks.')
            if row['test_id'] in found:
                raise ValueError('Duplisert test-ID i motorindeks.')
            found[row['test_id']] = row
        return found
    a, b = by_id(original), by_id(fast)
    results = []
    counts = Counter()
    for test_id in sorted(set(a) | set(b)):
        left, right = a.get(test_id), b.get(test_id)
        if left is None or right is None:
            verdict, detail = 'mismatch', 'Test-ID mangler i én av kjøringene.'
        elif left.get('status') != right.get('status'):
            verdict, detail = 'mismatch', 'Ulik teknisk status.'
        elif left.get('status') != 'ok':
            verdict, detail = 'unverified', 'Kilde mangler / kjøring feilet / ikke utført.'
        else:
            lvalue = _safe_engine_result(baseline_dir, left, test_id)
            rvalue = _safe_engine_result(accelerated_dir, right, test_id)
            if lvalue is None or rvalue is None:
                verdict, detail = 'unverified', 'Resultat-JSON mangler eller har feil identitet.'
            elif lvalue.get('status') != 'ok' or rvalue.get('status') != 'ok':
                verdict, detail = 'mismatch', 'Ulik status mellom indeks og resultatfil.'
            elif lvalue.get('values') == rvalue.get('values') and isinstance(lvalue.get('values'), dict):
                verdict, detail = 'match', 'Samme verdier i ordinær og optimalisert DWM-motor.'
            else:
                verdict, detail = 'mismatch', 'Ulike beregnede metrikkverdier.'
        counts[verdict] += 1
        results.append({'test_id': test_id,
                        'baseline_status': left.get('status') if left else None,
                        'accelerated_status': right.get('status') if right else None,
                        'status': verdict, 'detail': detail})
    return {
        'comparison_format_version': FORMAT_VERSION,
        'purpose': 'dwm_original_lxml_vs_optimized_dwm_lxml',
        'summary': {'tests': len(results), 'matches': counts['match'],
                    'mismatches': counts['mismatch'], 'unverified': counts['unverified'],
                    'status': ('match' if results and counts['match'] and not counts['mismatch'] and not counts['unverified']
                               else 'review')},
        'tests': results,
        'semantic_equivalence_to_kdrs_saxon_verified': False,
    }


def _safe_engine_result(run_dir: Path, entry: dict, test_id: str) -> dict[str, Any] | None:
    path = str(entry.get('file') or '').replace('\\', '/')
    rel = Path(path)
    if len(rel.parts) != 2 or rel.parts[0] != 'results' or rel.suffix != '.json':
        return None
    obj = _read_json(run_dir / rel, within=run_dir, limit=MAX_JSON_BYTES)
    if obj and obj.get('test_id') == test_id:
        return obj
    return None


def execute_dwm_engine_parity(project: Path, extraction_root: Path,
                              *, execution_profile: str = 'normal') -> dict[str, Any]:
    """Explicit opt-in: run both existing engines with temporary outputs.

    Scans XML supplied by the caller; never writes to it. This may be slow for
    large extracts and should not be invoked by opening the Qt result view.
    """
    if execution_profile not in ('normal', 'regression'):
        raise ValueError('Ugyldig execution_profile.')
    extraction = Path(extraction_root).resolve(strict=True)
    if not extraction.is_dir():
        raise ValueError('Uttrekksrot er ikke en mappe.')
    if not any(extraction.glob('*.xml')):
        raise ValueError('Ingen XML-filer i valgt uttrekksrot; ingen reell motortest kan utføres.')
    catalog = Path(project) / 'config/noark5/tests/xpath_catalog_2026_05_26.json'
    if not catalog.is_file():
        raise FileNotFoundError('DWM XPath-katalogen finnes ikke.')
    from noark5_workflow.analysis import xpath_test_engine as engine
    from noark5_workflow.analysis.xpath_fast_a154 import run_catalog_profiled
    with tempfile.TemporaryDirectory(prefix='dwm-xpath-a2-') as directory:
        root = Path(directory)
        base_dir, fast_dir = root / 'original', root / 'optimized'
        engine.run_catalog(catalog, extraction, base_dir, execution_profile=execution_profile)
        run_catalog_profiled(catalog, extraction, fast_dir, execution_profile=execution_profile)
        report = compare_dwm_result_dirs(base_dir, fast_dir)
    report['extraction_root'] = str(extraction)
    report['execution_profile'] = execution_profile
    report['catalog_sha256'] = _digest(catalog.read_bytes())
    report['note'] = 'Kjørt mot samme XML-kilder uten å skrive i Source eller Work; ikke KDRS/Saxon-ekvivalens.'
    return report


def build_audit(project: Path | None = None, *, work: Path | None = None,
                chosen_run: Path | str | None = None,
                extraction_root: Path | None = None,
                execution_profile: str = 'normal') -> dict[str, Any]:
    root = (Path(project) if project is not None else repo_root()).resolve()
    report = {
        'report_format_version': FORMAT_VERSION,
        'dwm_version': VERSION,
        'generated_utc': datetime.now(timezone.utc).isoformat(),
        'static_source_crosswalk': source_crosswalk(load_rows(root), root),
        'separate_evidence_types': ('kdrs_literal_fragments', 'dwm_engine_parity', 'saved_u1_u2_regression'),
        'noark_requirement_conformance_claimed': False,
    }
    if work is not None:
        report['saved_regression_runs'] = discover_saved_regressions(work)
        if chosen_run is not None:
            report['selected_saved_regression'] = inspect_saved_regression(work, chosen_run)
    elif chosen_run is not None:
        raise ValueError('--run-index krever --work.')
    if extraction_root is not None:
        report['dwm_engine_parity'] = execute_dwm_engine_parity(root, extraction_root,
                                                               execution_profile=execution_profile)
    return report


def main(argv: list[str] | None = None) -> int:
    import argparse
    parser = argparse.ArgumentParser(description='KDRS-kildesporing og eksplisitt DWM XPath-regresjon (a2)')
    parser.add_argument('--project', type=Path, default=repo_root())
    parser.add_argument('--work', type=Path, default=None,
                        help='Oppdag lagrede U1/U2-kjøringer uten å velge dem automatisk.')
    parser.add_argument('--run-index', default=None,
                        help='Velg én indeks fra --work/noark5_tests/xpath_regression/<run>/index.json.')
    parser.add_argument('--extraction-root', type=Path, default=None,
                        help='Kjør to DWM-motorer mot samme XML (kan ta tid og minne).')
    parser.add_argument('--execution-profile', choices=('normal', 'regression'), default='normal')
    parser.add_argument('--output', type=Path, default=None,
                        help='Skriv rapport til denne filen, ellers stdout. Ikke i Source.')
    opts = parser.parse_args(argv)
    try:
        report = build_audit(opts.project, work=opts.work, chosen_run=opts.run_index,
                             extraction_root=opts.extraction_root,
                             execution_profile=opts.execution_profile)
        if opts.output and opts.extraction_root and (
            opts.output.resolve() == opts.extraction_root.resolve() or
            opts.output.resolve().is_relative_to(opts.extraction_root.resolve())):
            raise ValueError('Rapport kan ikke skrives inne i Source/uttrekksrot.')
        content = json.dumps(report, ensure_ascii=False, indent=2) + '\n'
        if opts.output:
            if opts.work and opts.output.resolve().is_relative_to(opts.work.resolve()):
                raise ValueError('Rapport kan ikke skrives inne i Work; velg separat mappe.')
            opts.output.write_text(content, encoding='utf-8')
        else:
            print(content)
        return 0
    except (OSError, ValueError, RuntimeError, ImportError) as exc:
        parser.exit(2, f'FEIL: {exc}\n')


if __name__ == '__main__':
    raise SystemExit(main())
