"""Noark 5 XSD->DWM/XPath candidate trace, with evidence and explicit limits.

Reads local CHECKED OUT internal authority (digital-archive-workflow), not
remote third-party replacements. No normative PDF/DOCX requirement is assumed
from XSD alone. A lexical match is not an implemented test or conformance pass.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
from typing import Any
from lxml import etree

from app.noark_xsd_variant_qa_v021_a5 import source_checkout_commit, compare_dwm_value_sets
from app.noark_semantic_values_v021_a6 import load_registry, _read_json

SOURCE_PATH = Path('docs/kilder/noark/noark5')
XSD_NAMES = ('arkivstruktur.xsd', 'endringslogg.xsd', 'loependeJournal.xsd',
             'metadatakatalog.xsd', 'offentligJournal.xsd')
XSD_NS = '{http://www.w3.org/2001/XMLSchema}'
VERSIONS = ('3.1', '4.0', '5.0')
MAX_XSD_BYTES = 8_000_000
_ID = re.compile(r'^M\d{3}$')
_LITERAL = re.compile(r"'[^']*'|\"[^\"]*\"")


def _parse_schema(path: Path):
    if not path.is_file() or path.stat().st_size > MAX_XSD_BYTES:
        raise ValueError(f'XSD mangler eller overskrider grensen: {path}')
    data = path.read_bytes()
    parser = etree.XMLParser(resolve_entities=False, load_dtd=False, no_network=True)
    root = etree.fromstring(data, parser=parser)
    if root.tag != XSD_NS + 'schema':
        raise ValueError(f'Ikke gyldig XSD-rot: {path}')
    return root, hashlib.sha256(data).hexdigest()


def _annotated_metadata_types(root) -> list[dict[str, Any]]:
    out = []
    for node in root:
        if node.tag not in (XSD_NS+'simpleType', XSD_NS+'complexType'):
            continue
        if not node.get('name'):
            continue
        annotation = node.find(XSD_NS+'annotation')
        if annotation is None:
            continue
        ids = [''.join(x.itertext()).strip()
               for x in annotation.findall(XSD_NS+'documentation')]
        ids = [mid for mid in ids if _ID.fullmatch(mid)]
        if not ids:
            continue
        restrictions = [x for x in node.iter()
                        if x.tag in (XSD_NS+'restriction', XSD_NS+'extension')]
        enumerations = [str(x.get('value')) for x in node.iter(XSD_NS+'enumeration')]
        min_length = [x.get('value') for x in node.iter(XSD_NS+'minLength')]
        patterns = [x.get('value') for x in node.iter(XSD_NS+'pattern')]
        for mid in ids:
            out.append({
                'metadata_id': mid, 'type_name': node.get('name'),
                'xsd_type_definition_line': node.sourceline,
                'xsd_declared_kind': 'simple' if node.tag.endswith('simpleType') else 'complex',
                'restriction_base': restrictions[0].get('base') if restrictions else None,
                'enumeration_literals': enumerations,
                'min_length': int(min_length[0]) if min_length else None,
                'patterns': patterns,
            })
    return out


def _binding_candidates(types: list[dict[str, Any]], schema_roots: dict[str, Any]) -> dict[str, list[dict]]:
    by_type: dict[str, list[dict[str, Any]]] = {}
    for filename, root in schema_roots.items():
        if filename == 'metadatakatalog.xsd':
            continue
        for element in root.iter(XSD_NS+'element'):
            name = element.get('name') or ''
            xtype = str(element.get('type') or '').split(':')[-1]
            if xtype:
                by_type.setdefault(xtype, []).append({
                    'file': filename, 'element_name': name, 'line': element.sourceline,
                    'declared_min_occurs': element.get('minOccurs'),
                    'declared_max_occurs': element.get('maxOccurs'),
                    'kind': 'type_reference_candidate_only',
                })
    return {str(item['metadata_id']): by_type.get(str(item['type_name']), [])
            for item in types}


def _xpath_field_mentioned(expression: str, field_name: str) -> bool:
    """Conservative token lead outside string literals; NOT XPath evaluation."""
    if not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_.-]*', field_name):
        return False
    expr = _LITERAL.sub(' ', expression)
    return bool(re.search(r'(?<![A-Za-z0-9_.:-])'+re.escape(field_name)+r'(?![A-Za-z0-9_.:-])', expr))


def _metric_descriptors(test: dict) -> list[dict[str, str]]:
    execution = test.get('execution', {})
    if execution.get('kind') != 'metrics':
        return []
    found = []
    for key in ('metrics', 'archive_part_metrics'):
        for metric in execution.get(key, []) or []:
            if not isinstance(metric, dict):
                continue
            for prop in ('expression', 'select', 'value'):
                val = metric.get(prop)
                if isinstance(val, str) and val:
                    found.append({'metric_id':str(metric.get('id') or ''), 'scope':key, 'expression':val})
            fields = metric.get('fields', {})
            if isinstance(fields, dict):
                for expr in fields.values():
                    if isinstance(expr, str) and expr:
                        found.append({'metric_id':str(metric.get('id') or ''), 'scope':key, 'expression':expr})
    return found


def _lexical_xpath_candidates(metadata: list[dict], tests: list[dict], version: str) -> dict[str, list[dict]]:
    metrics = [(t, e) for t in tests if version in t.get('noark_versions', [])
               for e in _metric_descriptors(t)]
    out = {}
    for item in metadata:
        matches = []
        for test, expr in metrics:
            if _xpath_field_mentioned(expr['expression'], item['type_name']):
                matches.append({'test_id':test.get('test_id'), 'legacy_job_id':(test.get('legacy') or {}).get('job_id'),
                                'metric_id':expr['metric_id'], 'source_xml':test.get('source_xml'),
                                'basis':'lexical_xpath_candidate_not_semantic_coverage'})
        out[item['metadata_id']] = matches
    return out


def _registered_dwm_data(dwm_root: Path, version: str) -> tuple[set[str], list[dict]]:
    base = dwm_root/'config/noark5/standards'
    metadata = _read_json(base/'metadata'/f'{version}.json')
    requirements = _read_json(base/'requirements'/f'{version}.json')
    return ({x['metadata_id'] for x in metadata.get('metadata',[])},
            requirements.get('requirements',[]))


def build_trace(source_root: str | Path, dwm_root: str | Path, *,
                source_commit: str | None = None) -> dict[str, Any]:
    src, dwm = Path(source_root).resolve(), Path(dwm_root).resolve()
    if not src.is_dir() or not dwm.is_dir():
        raise ValueError('Begge repo må være lokalt tilgjengelige')
    committed = source_checkout_commit(src)
    if source_commit and committed and source_commit != committed:
        raise ValueError('Oppgitt kildecommit er ikke lokalt utsjekket HEAD')
    registry = load_registry(dwm/'config/noark5/standards/noark5_semantic_values_v021_a6.json')
    known_hashes = registry['source_xsd_metadatakatalog_sha256']
    catalogue = _read_json(dwm/'config/noark5/tests/xpath_catalog_2026_05_26.json')
    tests = catalogue.get('tests',[])
    report = {
        'report_version':1,
        'report_type':'technical_xsd_metadata_to_xpath_lexical_trace_not_normative_requirements_audit',
        'source_repository':'IKAMR/digital-archive-workflow',
        'source_checkout_commit': committed or source_commit,
        'source_checkout_commit_verified': bool(committed),
        'pinned_semantic_registry_source_commit':registry['source_commit'],
        'source_commit_matches_registry':bool(committed and committed==registry['source_commit']),
        'dwm_repository':'IKAMR/data-workflow-manager',
        'xpath_catalog_tests':len(tests),
        'xpath_special_handlers_not_semantically_audited':len([t for t in tests if (t.get('execution') or {}).get('kind')!='metrics']),
        'read_only':True, 'normative_requirements_all_read':False,
        'versions':{},
    }
    for version in VERSIONS:
        directory = src/SOURCE_PATH/f'v{version}'/'schemas'
        roots = {}
        sha256 = {}
        for filename in XSD_NAMES:
            root, digest = _parse_schema(directory/filename)
            if root.get('version') and root.get('version') != version:
                raise ValueError(f'Skjema-versjonskonflikt: {directory/filename}')
            roots[filename] = root
            sha256[filename] = digest
        types = _annotated_metadata_types(roots['metadatakatalog.xsd'])
        bindings = _binding_candidates(types,roots)
        candidates = _lexical_xpath_candidates(types,tests,version)
        registered, requirements = _registered_dwm_data(dwm,version)
        listed = {x['metadata_id']:x['enumeration_literals'] for x in types if x['enumeration_literals']}
        source_values = registry['xsd_enumerations_by_version'][version]
        enum_diff = {}
        for mid in sorted(set(listed)|set(source_values)):
            a,b=listed.get(mid,[]),source_values.get(mid,[])
            if a!=b:
                enum_diff[mid]={'xsd_actual':a,'pinned_registry':b}
        rows = []
        for x in sorted(types,key=lambda x:(x['metadata_id'],x['type_name'])):
            mid=x['metadata_id']
            referenced_reqs=[{'requirement_id':r.get('requirement_id'),
                              'verified_requirement_is_conformance_pass':False}
                             for r in requirements
                             if r.get('metadata_id')==mid or r.get('xml_field_name')==x['type_name']]
            rows.append({**x,
                'schema_filename':'metadatakatalog.xsd',
                'registered_in_dwm_metadata':mid in registered,
                'xsd_structural_type_reference_candidates':bindings.get(mid,[]),
                'xpath_lexical_candidates':candidates.get(mid,[]),
                'dwm_registered_requirement_references':referenced_reqs,
                'normative_requirement_tested':False,
                'xsd_declaration_is_not_full_occurrence_constraint':True,
            })
        coverage = Counter(x['metadata_id'] for x in types)
        results={
            'source_xsd_sha256':sha256,
            'reference_metadatakatalog_xsd_raw_sha256_matches_pinned':sha256['metadatakatalog.xsd']==known_hashes[version],
            'known_pinned_metadatakatalog_xsd_sha256':known_hashes[version],
            'xsd_metadata_type_definitions':len(types),
            'xsd_unique_metadata_ids':len(coverage),
            'duplicate_annotated_metadata_ids':{k:n for k,n in coverage.items() if n>1},
            'xsd_metadata_with_enumerations':len(listed),
            'semantic_xsd_reference_enumeration_diff':enum_diff,
            'dwm_registered_metadata_ids':len(registered),
            'dwm_registered_requirements':len(requirements),
            'metadata_with_xpath_lexical_candidates':sum(bool(candidates.get(x['metadata_id'])) for x in types),
            'unregistered_xsd_metadata':sorted(set(coverage)-registered),
            'rows':rows,
        }
        report['versions'][version]=results
    vcheck = compare_dwm_value_sets(src,dwm/'config/noark5/standards/noark5_standard_values.json')
    report['legacy_standard_value_registry_crosswalk']=vcheck
    report['qa_required']={
        'source_commit_differs_from_pinned_semantic_registry': bool(committed and committed!=registry['source_commit']),
        'xsd_reference_hash_mismatches':[v for v in VERSIONS
             if not report['versions'][v]['reference_metadatakatalog_xsd_raw_sha256_matches_pinned']],
        'enumeration_registry_conflicts':[v for v in VERSIONS
             if report['versions'][v]['semantic_xsd_reference_enumeration_diff']],
        'dwm_standard_values_need_review': {
             v:{'missing_enumerations_count':len(vcheck['versions'].get(v,{}).get('xsd_enumerations_not_registered',[])),
                'value_set_differences':vcheck['versions'].get(v,{}).get('literal_value_differences',[])}
             for v in VERSIONS},
    }
    return report


def main(argv: list[str] | None = None) -> int:
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source-root',type=Path,required=True,
                   help='Lokal utsjekking av IKAMR/digital-archive-workflow')
    p.add_argument('--dwm-root',type=Path,default=Path(__file__).resolve().parents[1])
    p.add_argument('--source-commit',default=None,
                   help='Valgfri sikkerhetskontroll mot faktisk lokalt Git HEAD')
    p.add_argument('--output',type=Path,required=True,
                   help='JSON-resultat i separat QA/Work-område; ikke kilderepo eller DWM-repo')
    args=p.parse_args(argv)
    source,dwm,out=args.source_root.resolve(),args.dwm_root.resolve(),args.output.resolve()
    if any(out==root or root in out.parents for root in (source,dwm)):
        p.error('Utdata må ligge utenfor både kilderepoet og DWM-repoet')
    if out.exists():
        p.error('Eksisterende QA-rapport overskrives ikke')
    result=build_trace(source,dwm,source_commit=args.source_commit)
    out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(f'Noark 5 teknisk kildesporing: {out}')
    for v,entry in result['versions'].items():
        print(f'v{v}: {entry["xsd_metadata_type_definitions"]} XSD-M-typer, '
              f'{entry["xsd_metadata_with_enumerations"]} enumerationer, '
              f'{entry["dwm_registered_metadata_ids"]} DWM-M registrert, '
              f'{entry["metadata_with_xpath_lexical_candidates"]} XPath-treff (ikke dekning)')
    return 0


if __name__=='__main__':
    raise SystemExit(main())
