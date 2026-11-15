"""Verify that the 15 non-metrics catalog kinds have an engine dispatch path."""
from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase, skipUnless
import json

from app.noark5_kdrs_semantic_audit_v021_a8 import (
    audit_implementation, static_special_dispatch,
)

REPO=Path(__file__).resolve().parents[1]


class KDRSDispatchReview(TestCase):
    def test_ast_catches_only_reachable_special_branches(self):
        source='''def _special(tree,test,source_path,extraction_root):
    kind = test['execution']['kind']
    if kind == 'class_folder_list':
        return 1
    if kind in {'u1_total', 'u2_archive_parts'}:
        return 2
# if kind == 'fake_only_comment':
    raise ValueError(kind)
'''
        found=static_special_dispatch(source)
        self.assertEqual(found,{'class_folder_list','u1_total','u2_archive_parts'})

    def test_ast_does_not_count_unrelated_helper(self):
        source='''def _other(kind):
    if kind == 'outside': return 1

def _special(tree,test,source_path,extraction_root):
    kind=test['execution']['kind']
    if kind == 'inside': return 1
'''
        self.assertEqual(static_special_dispatch(source),{'inside'})

    def test_missing_engine_branch_is_not_silent(self):
        with TemporaryDirectory() as temp:
            root=Path(temp)
            catalog=root/'config/noark5/tests/xpath_catalog_2026_05_26.json'
            catalog.parent.mkdir(parents=True)
            catalog.write_text(json.dumps({'tests':[
                {'test_id':'kdrs.u01','legacy':{'job_id':'U01'},
                 'execution':{'kind':'u1_total'},'source_xml':'arkivstruktur.xml',
                 'noark_versions':['3.1','4.0','5.0']},
            ]}),encoding='utf-8')
            e=root/'noark5_workflow/analysis/xpath_test_engine.py'
            e.parent.mkdir(parents=True)
            e.write_text('def _special(tree,test,source,root):\n    pass\n',encoding='utf-8')
            r=audit_implementation(root)
            self.assertEqual(r['summary']['special_handler_tests'],1)
            self.assertEqual(r['summary']['dispatch_missing'],1)
            self.assertEqual(r['tests'][0]['qa_severity'],'FEIL')
            self.assertFalse(r['saxon_lxml_semantic_parity_verified'])
            self.assertTrue(any(q['kind']=='catalog_kind_not_dispatched_by_engine'
                                for q in r['issues']))

    def test_engine_dispatch_does_not_approve_semantics(self):
        with TemporaryDirectory() as temp:
            root=Path(temp)
            cat=root/'config/noark5/tests/xpath_catalog_2026_05_26.json'
            cat.parent.mkdir(parents=True)
            cat.write_text(json.dumps({'tests':[
                {'test_id':'kdrs.u01','legacy':{'job_id':'U01'},
                 'execution':{'kind':'u1_total'},'source_xml':'arkivstruktur.xml',
                 'noark_versions':['3.1','4.0','5.0']},
            ]}),encoding='utf-8')
            e=root/'noark5_workflow/analysis/xpath_test_engine.py'
            e.parent.mkdir(parents=True)
            e.write_text('''def _special(tree,test,source,root):
    kind = test['execution']['kind']
    if kind == 'u1_total':
        return {'metric':17}
''',encoding='utf-8')
            r=audit_implementation(root)
            self.assertEqual(r['tests'][0]['dispatch_verdict'],'special_dispatch_located')
            self.assertFalse(r['tests'][0]['dwm_handler_semantics_verified'])
            self.assertFalse(r['tests'][0]['kdrs_saxon_parity_verified'])
            self.assertEqual(r['summary']['special_handler_tests'],1)
            self.assertEqual(r['summary']['dispatch_missing'],0)

    @skipUnless((REPO/'config/noark5/tests/xpath_catalog_2026_05_26.json').is_file()
                and (REPO/'noark5_workflow/analysis/xpath_test_engine.py').is_file(),
                'full checkout only (not included in delta test harness)')
    def test_actual_full_repo_kdrs_60_and_special_15(self):
        r=audit_implementation(REPO)
        self.assertEqual(r['summary']['catalog_tests'],60)
        self.assertEqual(r['summary']['special_handler_tests'],15)
        self.assertEqual(r['summary']['dispatch_missing'],0)
        self.assertEqual(len(r['tests']),60)
        self.assertFalse(r['saxon_lxml_semantic_parity_verified'])
        self.assertEqual(r['summary']['original_kdrs_unavailable'],0)


if __name__=='__main__':
    from unittest import main
    main()
