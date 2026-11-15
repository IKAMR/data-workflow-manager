"""A8 KDRS Standard/U1/U2 static implementation and dispatch QA.

Static dispatch or XPath syntax does not establish equality to the original
XPath 2/3 Saxon expressions.  Behavioral parity needs identical XML fixtures
and the actual KDRS/Saxon output plus DWM/lxml results.
"""
from __future__ import annotations

import ast
from collections import Counter
from hashlib import sha256
import json
from pathlib import Path
from typing import Any

from app.noark5_xpath_audit_v021_a1 import (
    load_rows, legacy_source_expression, legacy_job_audit, _all_paths, SOURCES,
)

ENGINE_REL = Path('noark5_workflow/analysis/xpath_test_engine.py')
CATALOG_REL = Path('config/noark5/tests/xpath_catalog_2026_05_26.json')


def static_special_dispatch(engine_source: str) -> set[str]:
    """Find explicitly compared execution.kind literals inside _special().

    Uses Python AST to avoid false matches in comments or unrelated helpers.
    Does not execute engine code and does not claim handler correctness.
    """
    parsed=ast.parse(engine_source)
    special=next((node for node in parsed.body if isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef))
                  and node.name=='_special'),None)
    if special is None:
        return set()
    kinds=set()
    for node in ast.walk(special):
        if not isinstance(node,ast.Compare) or not isinstance(node.left,ast.Name) or node.left.id!='kind':
            continue
        for op, other in zip(node.ops,node.comparators):
            if isinstance(op,ast.Eq) and isinstance(other,ast.Constant) and isinstance(other.value,str):
                kinds.add(other.value)
            if isinstance(op,ast.In) and isinstance(other,(ast.Set,ast.Tuple,ast.List)):
                kinds.update(x.value for x in other.elts if isinstance(x,ast.Constant) and isinstance(x.value,str))
    return kinds


def _catalog_entries(root: Path) -> tuple[list, dict]:
    catalog_path=root/CATALOG_REL
    if not catalog_path.is_file():
        return [], {'kind':'xpath_catalog_not_available','severity':'WARNING'}
    try:
        rows=load_rows(root)
    except (ValueError,OSError,KeyError,TypeError) as exc:
        return [], {'kind':'xpath_catalog_invalid','severity':'FEIL','exception':type(exc).__name__}
    return list(rows), {}


def _xpath_compile_status(expressions: tuple[str,...]) -> tuple[int,list[dict]]:
    """Syntax-only: successfully compiling an XPath proves no calculation."""
    try:
        from lxml import etree
    except ImportError:
        return 0, [{'reason':'lxml_missing','expression':''}]
    errors=[]
    passed=0
    for expression in expressions:
        try:
            etree.XPath(expression)
        except etree.XPathSyntaxError as exc:
            errors.append({'expression':expression[:300], 'reason':str(exc)[:200]})
        else:
            passed+=1
    return passed, errors


def audit_implementation(dwm_root: Path | str) -> dict[str,Any]:
    """Verify catalog jobs and 15 special-kind dispatches in the actual engine."""
    root=Path(dwm_root).resolve()
    issues=[]
    entries, problem=_catalog_entries(root)
    if problem:
        issues.append(problem)
    path=root/ENGINE_REL
    dispatch=set()
    engine_sha=None
    if path.is_file():
        raw=path.read_bytes()
        engine_sha=sha256(raw).hexdigest()
        try:
            dispatch=static_special_dispatch(raw.decode('utf-8-sig'))
        except (UnicodeError,SyntaxError) as exc:
            issues.append({'severity':'FEIL','kind':'xpath_engine_ast_invalid',
                           'exception':type(exc).__name__})
    else:
        issues.append({'severity':'WARNING','kind':'xpath_engine_source_missing',
                       'source':str(ENGINE_REL)})
    audit={}
    if entries:
        try:
            from app.noark5_xpath_regression_v021_a2 import source_crosswalk
            audit=source_crosswalk(tuple(entries),project=root).get('tests',{})
        except (KeyError,OSError,ValueError,TypeError):
            issues.append({'severity':'WARNING','kind':'kdrs_a2_source_crosswalk_unavailable'})
    legacy=None
    if entries:
        legacy=legacy_job_audit(root)
        if legacy.get('not_in_dwm_catalog'):
            issues.append({'severity':'FEIL','kind':'kdrs_job_ids_missing_in_catalog',
                           'missing':legacy['not_in_dwm_catalog']})
        for rel in legacy.get('source_files_missing',[]):
            issues.append({'severity':'WARNING','kind':'kdrs_original_source_missing','source':rel})
    tests=[]
    all_ids=set()
    source_hashes={}
    for label, rel in SOURCES.items():
        path=root/rel
        if path.is_file():
            source_hashes[label]=sha256(path.read_bytes()).hexdigest()
    for row in entries:
        kind=str(row.definition.get('execution',{}).get('kind') or '')
        is_special=kind!='metrics'
        dispatched=(not is_special) or kind in dispatch
        if not kind:
            dispatched=False
        if row.test_id in all_ids:
            issues.append({'severity':'FEIL','kind':'duplicate_dwm_xpath_test_id',
                           'test_id':row.test_id})
        all_ids.add(row.test_id)
        original=legacy_source_expression(row,root)
        source_status='found'
        if row.legacy_id=='DWM-AU01':
            source_status='dwm_native_extension'
        elif not original or original.startswith(('Original KDRS-definisjon er ikke',
                                                   'Fant ikke opprinnelig',
                                                   'Fant KDRS-jobben',
                                                   'KDRS-kildefilen')):
            source_status='kdrs_original_unavailable'
        if source_status=='kdrs_original_unavailable':
            issues.append({'severity':'WARNING','kind':'kdrs_original_expression_missing',
                           'test_id':row.test_id})
        if is_special and not dispatched:
            issues.append({'severity':'FEIL','kind':'catalog_kind_not_dispatched_by_engine',
                           'test_id':row.test_id,'execution_kind':kind})
        paths=row.paths
        parsed_count,syntax_errors=_xpath_compile_status(paths)
        if syntax_errors:
            issues.append({'severity':'FEIL' if syntax_errors[0]['reason']!='lxml_missing' else 'WARNING',
                           'kind':'dwm_xpath_syntax_review', 'test_id':row.test_id,
                           'errors':syntax_errors[:3]})
        crosswalk=audit.get(row.test_id,{})
        severity='FEIL' if is_special and not dispatched else 'WARNING'
        reason=('catalog_kind_not_dispatched_by_engine' if is_special and not dispatched
                else 'dispatch_exists_but_saxon_semantics_not_verified' if is_special
                else 'dwm_xpath_source_mapping_not_behavioral_parity')
        if source_status=='kdrs_original_unavailable' and severity!='FEIL':
            severity='WARNING'
            reason='original_kdrs_expression_unavailable_for_comparison'
        tests.append({
            'test_id':row.test_id, 'legacy_id':row.legacy_id,
            'execution_kind':kind, 'source_xml':row.source_xml,
            'special_handler':is_special,
            'dispatch_verdict':('not_dispatched' if not dispatched else
                                'special_dispatch_located' if is_special else 'metrics_engine_path'),
            'original_source_status':source_status,
            'original_expression_sha256':(sha256(original.encode('utf-8')).hexdigest()
                                         if source_status=='found' else None),
            'a2_source_link_status':crosswalk.get('status') or 'not_available',
            'a2_original_expression_sha256':crosswalk.get('original_expression_sha256'),
            'version_declarations':list(row.versions),
            'xpath_literals':len(paths), 'xpath_literals_compiled':parsed_count,
            'xpath_literal_syntax_errors':syntax_errors,
            'qa_severity':severity, 'qa_reason':reason,
            'dwm_handler_semantics_verified':False,
            'kdrs_saxon_parity_verified':False,
        })
    kinds=Counter(row['execution_kind'] for row in tests)
    specials=[row for row in tests if row['special_handler']]
    summary={
        'catalog_tests':len(tests), 'special_handler_tests':len(specials),
        'special_dispatch_kinds':sorted(dispatch),
        'special_handler_kind_counts':dict(kinds),
        'dispatch_missing':sum(row['dispatch_verdict']=='not_dispatched' for row in tests),
        'original_kdrs_unavailable':sum(row['original_source_status']=='kdrs_original_unavailable' for row in tests),
        'source_only_missing_job_count':len(legacy.get('not_in_dwm_catalog',[])) if legacy else None,
        'xpath_literal_syntax_errors':sum(len(row['xpath_literal_syntax_errors']) for row in tests),
        'engine_sha256':engine_sha,'original_sources_sha256':source_hashes,
    }
    return {
        'report_format_version':1,
        'report_type':'noark5_a8_kdrs_dispatch_and_provenance_audit_not_semantic_parity',
        'summary':summary,'legacy_id_audit':legacy,'tests':tests,'issues':issues,
        'source_files_modified':False,
        'semantics_verified_via_real_identical_xml':False,
        'saxon_lxml_semantic_parity_verified':False,
        'note':'Katalog/AST/uttrykkssyntaks er teknisk dekningskontroll, ikke Saxon-vs-lxml resultatlikhet.',
    }
