# One-time DWM a7.1 migration of obsolete exact-sequence regression assertions.
# Run from repository root after applying a7. Validates exact old test bodies before edits.
# Does not touch Work, Source, user job lists, or Git.
#
from __future__ import annotations
import ast
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parent
NEW_IDS=('build_noark5_canonical_evidence','analyze_noark5_external_evidence','audit_noark5_evidence','build_noark5_qa_draft')
CHANGES={
 'tests/test_a15_5_auto_workflow.py': {'test_standard_sequence_is_canonical_noark5_flow': '''        from app.workflow_dependencies_v022_a7 import validate_dependencies
        sequence = workflow_sequence_by_id("noark5_standard")
        self.assertIsNotNone(sequence)
        self.assertEqual(sequence.profile_id, "noark5")
        self.assertEqual(validate_dependencies(sequence.operation_ids), ())
        self.assertIn("run_noark5_xpath_tests_2026", sequence.operation_ids)
        self.assertIn("build_noark5_canonical_evidence", sequence.operation_ids)
        self.assertLess(sequence.operation_ids.index("run_noark5_xpath_tests_2026"), sequence.operation_ids.index("build_noark5_canonical_evidence"))
'''},
 'tests/test_profile_registry_a12.py': {'test_noark5_profile_preserves_operations': '''        from noark5_workflow.app import build_registry
        registered = [op.definition.operation_id for op in build_registry().all()]
        self.assertEqual(len(registered), len(set(registered)))
        for required in ("metadata_inventory", "run_noark5_xpath_tests_2026", "compose_noark5_views", "build_noark5_depot_report", "build_noark5_canonical_evidence", "analyze_noark5_external_evidence", "audit_noark5_evidence", "build_noark5_qa_draft"):
            self.assertIn(required, registered)
'''},
 'tests/test_v0111_a1_basic_start.py': {'test_plan_uses_selected_work_directly_and_existing_dwm_workflow': '''        from app.workflow_dependencies_v022_a7 import ensure_a7_processing, validate_dependencies
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / 'source'
            source.mkdir()
            (source / 'arkivstruktur.xml').write_text('<arkiv/>', encoding='utf-8')
            work = root / 'workroot'
            work.mkdir()
            calls = []
            def validate(path, *, profile_id):
                calls.append(('validate', path, profile_id))
                return () if (path / 'arkivstruktur.xml').is_file() else (SimpleNamespace(message='Uttrekk mangler'),)
            def workflow(_id):
                calls.append(('sequence', _id))
                return SimpleNamespace(profile_id='noark5', operation_ids=WORKFLOW)
            stubs = {
                'app.job_preflight_v018_a6': SimpleNamespace(check_extraction_folder=validate),
                'app.storage_profiles_v0110_a2': SimpleNamespace(resolve_storage_profile=lambda _settings: 'standard_enkel'),
                'app.workflow_sequences': SimpleNamespace(workflow_sequence_by_id=workflow),
            }
            with patch.dict(sys.modules, stubs):
                result = prepare_basic_plan(source, work, {'app_work_subfolder': 'dwm'})
            self.assertEqual(result.source_extraction, source)
            self.assertEqual(result.work_root, work)
            self.assertEqual(result.work_operations, work)
            self.assertEqual(result.operation_ids, ensure_a7_processing(WORKFLOW))
            self.assertEqual(validate_dependencies(result.operation_ids), ())
            self.assertIn(('validate', source, 'noark5'), calls)
            self.assertIn(('sequence', BASIC_WORKFLOW_ID), calls)
            self.assertEqual(list(work.iterdir()), [], 'Planning must not make folders')
'''},
 'tests/test_v0111_a2_profiles.py': {
 'test_extended_profile_produces_real_arkade_operations': '''        from app.workflow_dependencies_v022_a7 import ensure_a7_processing, validate_dependencies
        with tempfile.TemporaryDirectory() as tmp:
            source, work = Path(tmp) / 'source', Path(tmp) / 'work'
            source.mkdir(); work.mkdir()
            calls=[]
            with patch.dict(sys.modules, self._modules(calls)):
                result=prepare_basic_plan(source, work, {}, workflow_id=BASIC_ARKADE_WORKFLOW_ID)
            self.assertEqual(result.workflow_id, BASIC_ARKADE_WORKFLOW_ID)
            self.assertEqual(result.operation_ids, ensure_a7_processing(ARKADE))
            self.assertEqual(validate_dependencies(result.operation_ids), ())
            self.assertEqual(calls, [BASIC_ARKADE_WORKFLOW_ID])
            self.assertEqual(result.work_operations, work)
            self.assertFalse(list(work.iterdir()))
''',
 'test_standard_has_no_arkade_or_aip': '''        from app.workflow_dependencies_v022_a7 import ensure_a7_processing, validate_dependencies
        with tempfile.TemporaryDirectory() as tmp:
            source, work = Path(tmp) / 'source', Path(tmp) / 'work'
            source.mkdir(); work.mkdir()
            with patch.dict(sys.modules, self._modules()):
                result=prepare_basic_plan(source, work, {})
            self.assertEqual(result.operation_ids, ensure_a7_processing(STANDARD))
            self.assertEqual(validate_dependencies(result.operation_ids), ())
            self.assertNotIn('dias_package', result.operation_ids)
'''
 },
 'tests/test_v015_a15_1_effective_results_and_arkade_import.py': {'test_standard_sequence_imports_arkade_before_views': '''        from app.workflow_dependencies_v022_a7 import validate_dependencies
        from app.workflow_sequences import workflow_sequence_by_id
        ids=list(workflow_sequence_by_id('noark5_standard').operation_ids)
        self.assertEqual(validate_dependencies(ids), ())
        self.assertIn('build_noark5_canonical_evidence', ids)
        self.assertLess(ids.index('build_noark5_canonical_evidence'),ids.index('compose_noark5_views'))
'''},
 'tests/test_v015_a16_effective_results_and_arkade_import.py': {'test_standard_sequence_imports_arkade_before_views': '''        from app.workflow_dependencies_v022_a7 import validate_dependencies
        from app.workflow_sequences import workflow_sequence_by_id
        ids=list(workflow_sequence_by_id('noark5_standard').operation_ids)
        self.assertEqual(validate_dependencies(ids), ())
        self.assertIn('build_noark5_canonical_evidence', ids)
        self.assertLess(ids.index('build_noark5_canonical_evidence'),ids.index('compose_noark5_views'))
'''},
 'tests/test_v015_a20_workflow_profiles.py': {'test_standard_sequence_keeps_arkade_import': '''        from app.workflow_dependencies_v022_a7 import validate_dependencies
        from app.workflow_sequences import workflow_sequence_by_id
        sequence=workflow_sequence_by_id('noark5_standard')
        self.assertEqual(validate_dependencies(sequence.operation_ids), ())
        self.assertIn('build_noark5_canonical_evidence', sequence.operation_ids)
        arkade=workflow_sequence_by_id('noark5_standard_arkade').operation_ids
        self.assertIn('import_arkade5_reports', arkade)
        self.assertLess(arkade.index('import_arkade5_reports'), arkade.index('build_noark5_canonical_evidence'))
'''},
 'tests/test_v016_a27_2_arkade_workflow_operations.py': {
 'test_default_sequences_are_unchanged_in_a272': '''        from app.workflow_dependencies_v022_a7 import validate_dependencies
        catalog=load_workflow_sequences()
        standard=catalog.get('noark5_standard')
        self.assertEqual(validate_dependencies(standard.operation_ids), ())
        self.assertIn('build_noark5_canonical_evidence', standard.operation_ids)
        self.assertIn('build_noark5_qa_draft', standard.operation_ids)
''',
 'test_predefined_sequences_have_exact_contents_and_order': '''        from app.workflow_dependencies_v022_a7 import validate_dependencies
        catalog=load_workflow_sequences()
        for name in ('noark5_standard_arkade','noark5_dwm_only','noark5_arkade_only'):
            ids=catalog.get(name).operation_ids
            self.assertEqual(validate_dependencies(ids), (), name)
        arkade=catalog.get('noark5_standard_arkade').operation_ids
        self.assertLess(arkade.index('arkade5_noark5_test'), arkade.index('import_arkade5_reports'))
        self.assertLess(arkade.index('import_arkade5_reports'), arkade.index('build_noark5_canonical_evidence'))
        self.assertEqual(catalog.get('noark5_arkade_only').operation_ids,('arkade5_noark5_test','arkade5_pronom_analysis'))
'''
 },
 'tests/test_v016_a37_runtime.py': {'test_standard_arkade_sequence_has_nine_operations': '''        from app.workflow_dependencies_v022_a7 import validate_dependencies
        payload=json.loads((ROOT / 'config' / 'workflow_sequences.json').read_text(encoding='utf-8'))
        sequence=next(item for item in payload['sequences'] if item['sequence_id']=='noark5_standard_arkade')
        ids=sequence['operation_ids']
        self.assertEqual(validate_dependencies(ids), ())
        self.assertGreaterEqual(len(ids), 13)
        self.assertEqual('arkade5_noark5_test',ids[3])
        self.assertEqual('arkade5_pronom_analysis',ids[4])
        self.assertLess(ids.index('import_arkade5_reports'), ids.index('build_noark5_canonical_evidence'))
'''}
}

def rewrite_test(file, methods):
    path=ROOT/file
    if not path.is_file(): raise RuntimeError(f'Mangler historisk testfil: {file}')
    original=path.read_text(encoding='utf-8')
    tree=ast.parse(original)
    lines=original.splitlines(keepends=True)
    patches=[]
    for name, body in methods.items():
        matches=[n for n in ast.walk(tree) if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef)) and n.name==name]
        if len(matches)!=1:raise RuntimeError(f'{file}: forventet akkurat en {name}, fant {len(matches)}')
        node=matches[0]
        start=node.body[0].lineno - 1
        end=node.end_lineno
        patches.append((start,end,body))
    for start,end,body in sorted(patches,reverse=True):
        lines[start:end]=[body]
    updated=''.join(lines)
    ast.parse(updated)
    if updated!=original:path.write_text(updated,encoding='utf-8')


def main():
    required=(ROOT/'app/workflow_dependencies_v022_a7.py',ROOT/'noark5_workflow/profile.py')
    if not all(p.is_file() for p in required):raise RuntimeError('Installer a7 i repo-roten forst.')
    for file,methods in CHANGES.items():rewrite_test(file,methods)
    metadata=ROOT/'config/operations.json'
    obj=json.loads(metadata.read_text(encoding='utf-8'))
    entries={
       'build_noark5_canonical_evidence': ('Bygg kanonisk Noark 5-evidens',1),
       'analyze_noark5_external_evidence': ('Analyser ekstern evidens',2),
       'audit_noark5_evidence': ('Kontroller evidensdekning',3),
       'build_noark5_qa_draft': ('Forbered KS-grunnlag (utkast)',6),
    }
    for op,(name,priority) in entries.items():
        obj['operations'].setdefault(op,{})
        obj['operations'][op].update({'maturity':'alpha','short_name':name,'display_category':'Resultat','profiles':['noark5'],'display_order':priority})
    metadata.write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    runner=ROOT/'noark5_workflow/core/job_runner_a39.py'
    source=runner.read_text(encoding='utf-8')
    source=source.replace("_NON_BLOCKING_OPERATION_ID = 'validate_xml_schema'",'_NON_BLOCKING_OPERATION_ID = "validate_xml_schema"')
    runner.write_text(source,encoding='utf-8')
    print('a7.1: historiske arbeidsflyttester oppdatert til a7-avhengighetskontrakt, fire operasjoner registrert i katalogen, XSD-kontrakt rettet.')
    print('Kjor deretter test.bat. Ingen Git-operasjoner er utført.')

if __name__=='__main__':main()
