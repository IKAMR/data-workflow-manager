"""a11.5: real KDRS 0.9 text-layout workflow, evidence and publish guards."""
from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from app.noark5_kdrs_parity_v021_a11 import OUTPUTS as PARITY_FILES
from app.noark5_kdrs_text_import_v021_a11 import REPORT_NAMES as IMPORT_FILES
from app.noark5_kdrs_practical_qa_v021_a11 import (
    EXTRA_FILES, _classify_report, _disjoint_output, _parse_reports,
    discover_reports, inspect_inputs, main, resolve_index, run_practical_qa,
)


class A11PracticalQATests(unittest.TestCase):
    def setUp(self):
        temp = TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.dwm_root = self.root / 'dwm'
        ref = self.dwm_root / 'docs/reference/kdrs-query'
        ref.mkdir(parents=True)
        refs = {
            'xml-queries_noark5_2026-05-26.txt': '''[XML_QUERY]
job_id=C05
source=arkivstruktur.xml
#START#
concat("N5.07 Klassifikasjonssystemer: ", count(//klassifikasjonssystem))
#STOP#
''',
            'xml-queries_noark5_2026-05-26_U1.txt': '''[XML_QUERY]
job_id=U01
source=arkivstruktur.xml
#START#
concat("N5.04 Arkiv: ", count(//arkiv))
#STOP#
''',
            'xml-queries_noark5_2026-05-26_U2.txt': '''[XML_QUERY]
job_id=U02
source=arkivstruktur.xml
#START#
//arkivdel/(concat("Arkivdel ", position(), ": ", tittel),
concat("[.3] Registreringer; Alle: ", count(descendant::registrering)))
#STOP#
''',
        }
        for name, value in refs.items():
            (ref / name).write_text(value, encoding='utf-8')
        catalog = self.dwm_root / 'config/noark5/tests/xpath_catalog_2026_05_26.json'
        catalog.parent.mkdir(parents=True)
        catalog.write_text(json.dumps({'tests':[
            {'test_id':'kdrs.c05','legacy':{'job_id':'C05'},'source_xml':'arkivstruktur.xml',
             'execution':{'kind':'metrics','metrics':[
                 {'id':'classification_system_count','type':'xpath',
                  'expression':'count(//klassifikasjonssystem)'}]}},
            {'test_id':'kdrs.u01','legacy':{'job_id':'U01'},'source_xml':'arkivstruktur.xml',
             'execution':{'kind':'u1_total'}},
            {'test_id':'kdrs.u02','legacy':{'job_id':'U02'},'source_xml':'arkivstruktur.xml',
             'execution':{'kind':'u2_archive_parts'}},
        ]}),encoding='utf-8')
        self.xml_root = self.root / 'source'
        self.xml_root.mkdir()
        self.xmlfile = self.xml_root / 'arkivstruktur.xml'
        self.xmlfile.write_text('<arkiv><klassifikasjonssystem/>'
            '<arkivdel><systemID>A</systemID><tittel>Del A</tittel>'
            '<registrering/><registrering/><registrering/></arkivdel></arkiv>',encoding='utf-8')
        self.kdrs_root = self.root / 'kdrs_original'
        self.kdrs_root.mkdir()
        def report(filename, sourcefile, job, body):
            p = self.kdrs_root / filename
            p.write_text('Query file: C:\\KDRS\\doc\\'+sourcefile+'\n\n'
                         '=================================\n\n'+job+'\n\n'+body+'\n'
                         '=================================\n', encoding='utf-8')
            return p
        self.standard = report('kdrs_query_results_uttrekk_clean.txt',
            'xml-queries_noark5_2026-05-26.txt','C05','N5.07 Klassifikasjonssystemer: 1')
        self.u1 = report('kdrs_query_results_uttrekk_U01.txt',
            'xml-queries_noark5_2026-05-26_U1.txt','U01','N5.04 Arkiv: 1')
        self.u2 = report('kdrs_query_results_uttrekk_U02.txt',
            'xml-queries_noark5_2026-05-26_U2.txt','U02',
            'Arkivdel 1: Del A, [.3] Registreringer; Alle: 3')
        self.run_dir = self.root / 'run'
        results = self.run_dir / 'results'
        results.mkdir(parents=True)
        identity = {'index':1,'title':'Del A','system_id':'A','status':''}
        values = {
            'kdrs.c05':{'classification_system_count':1},
            'kdrs.u01':{'archive':{'count':1}},
            'kdrs.u02':{'archive_parts':[{'archive_part':identity,
                                        'values':{'registration_count':3}}]},
        }
        index = []
        for test_id, value in values.items():
            file = f'results/{test_id.replace(".","_")}.json'
            (self.run_dir/file).write_text(json.dumps({
                'test_id':test_id,'status':'ok','source_xml':'arkivstruktur.xml',
                'source_path':str(self.xmlfile),'values':value,
            }),encoding='utf-8')
            index.append({'test_id':test_id,'status':'ok','file':file})
        self.index = self.run_dir / 'index.json'
        self.index.write_text(json.dumps({'result_set_format_version':2,
                                          'tests':index}),encoding='utf-8')
        self.reports = {'STANDARD':self.standard,'U1':self.u1,'U2':self.u2}
        self.dest = self.root / 'qa_output'

    def run_qa(self):
        return run_practical_qa(dwm_root=self.dwm_root,xml_root=self.xml_root,
                                dwm_index=self.index,reports=self.reports,
                                noark_version='5.0',output_dir=self.dest)

    def test_finds_all_three_profiles_by_actual_job_id(self):
        found = discover_reports(self.kdrs_root)
        self.assertEqual(found,self.reports)
        self.assertEqual(_classify_report(self.u1)[0],'U1')
        self.assertEqual(_classify_report(self.u2)[0],'U2')
        self.assertEqual(resolve_index(None,self.run_dir),self.index.resolve())

    def test_discovery_retains_selected_path_spelling_instead_of_resolving_alias(self):
        # Windows TemporaryDirectory can use an 8.3 alias (USERNA~1) while
        # Path.resolve() expands it. An explicit lexical alias reproduces
        # the same path-equality contract on Windows, Linux and macOS.
        marker = self.root / 'lexical_alias'
        marker.mkdir()
        selected = marker / '..' / 'kdrs_original'
        found = discover_reports(selected)
        expected = {profile: selected / original.name
                    for profile, original in self.reports.items()}
        self.assertEqual(found, expected)
        self.assertEqual({profile: path.resolve() for profile, path in found.items()},
                         {profile: path.resolve() for profile, path in self.reports.items()})

    def test_preflight_does_not_open_or_hash_xml(self):
        original = self.xmlfile.read_bytes()
        import app.noark5_kdrs_practical_qa_v021_a11 as module
        real_digest = module.digest
        def check_digest(path):
            self.assertNotEqual(path.resolve(),self.xmlfile.resolve())
            return real_digest(path)
        with patch.object(module,'digest',side_effect=check_digest):
            pre = inspect_inputs(self.dwm_root,self.xml_root,self.index,self.reports)
        self.assertEqual(self.xmlfile.read_bytes(),original)
        self.assertFalse(pre['xml_sha256_read'])
        self.assertFalse(pre['findings'])
        self.assertEqual([x['profile'] for x in pre['reports']],['STANDARD','U1','U2'])
        self.assertEqual(len(pre['xml_files']),1)

    def test_integrated_provisional_standard_u1_u2_and_atomic_nine_files(self):
        before = self.xmlfile.read_bytes()
        report_bodies = {p:p.read_bytes() for p in self.reports.values()}
        summary=self.run_qa()
        self.assertEqual(summary['mapped_metric_rows'],3)
        self.assertEqual(summary['comparison_summary']['provisional_matches'],3)
        self.assertEqual(summary['comparison_summary']['provisional_mismatches'],0)
        self.assertEqual(summary['comparison_summary']['not_comparable'],0)
        self.assertFalse(summary['whole_saxon_lxml_parity_verified'])
        self.assertFalse(summary['historical_execution_time_xml_sha256_attested'])
        self.assertEqual(summary['review_status'],'REVIEW_REQUIRED')
        self.assertEqual({x.name for x in self.dest.iterdir()},
                         set(EXTRA_FILES)|set(PARITY_FILES)|set(IMPORT_FILES))
        comparisons=json.loads((self.dest/PARITY_FILES[0]).read_text())['comparisons']
        self.assertEqual({r['profile'] for r in comparisons},set(self.reports))
        self.assertEqual(self.xmlfile.read_bytes(),before)
        self.assertEqual({p:p.read_bytes() for p in self.reports.values()},report_bodies)
        self.assertFalse(any(p.name.startswith('.noark5-a11.5-') for p in self.root.iterdir()))
        with self.assertRaises(FileExistsError): self.run_qa()

    def test_mismatch_kept_as_review_not_pass_and_no_source_mutation(self):
        d=json.loads((self.run_dir/'results/kdrs_c05.json').read_text())
        d['values']['classification_system_count']=99
        (self.run_dir/'results/kdrs_c05.json').write_text(json.dumps(d))
        summary=self.run_qa()
        self.assertEqual(summary['comparison_summary']['provisional_mismatches'],1)
        self.assertEqual(summary['review_status'],'REVIEW_REQUIRED')
        self.assertIn('MATCH_PROVISIONAL', (self.dest/PARITY_FILES[1]).read_text())
        self.assertIn('MISMATCH_PROVISIONAL',(self.dest/EXTRA_FILES[1]).read_text())

    def test_ambiguous_report_selection_rejected_not_arbitrary_first(self):
        self.standard.with_name('kdrs_query_results_another.txt').write_bytes(self.standard.read_bytes())
        with self.assertRaisesRegex(ValueError,'Tvetydige KDRS-profiler'):
            discover_reports(self.kdrs_root)
        self.assertEqual(_parse_reports(['STANDARD='+str(self.standard)]),{'STANDARD':self.standard})
        with self.assertRaisesRegex(ValueError,'Duplisert'):
            _parse_reports(['U1=x','U1=y'])

    def test_preflight_missing_xml_raises_without_publishing_any_files(self):
        self.xmlfile.unlink()
        pre = inspect_inputs(self.dwm_root,self.xml_root,self.index,self.reports)
        self.assertEqual(pre['findings'][0]['reason'],'xml_source_missing')
        with self.assertRaisesRegex(ValueError,'Forhåndskontroll stoppet'):
            self.run_qa()
        self.assertFalse(self.dest.exists())

    def test_output_overlaps_source_work_kdrs_or_repo_are_refused(self):
        for protected in (self.xml_root,self.dwm_root,self.run_dir,self.kdrs_root):
            with self.subTest(protected=protected), self.assertRaises(ValueError):
                _disjoint_output(protected/'report',self.xml_root,self.dwm_root,
                                 self.run_dir,self.kdrs_root)
        with self.assertRaises(ValueError):
            _disjoint_output(self.root,self.xml_root)

    def test_failed_compare_removes_staging_without_overwriting_reports(self):
        d = json.loads(self.index.read_text())
        d['tests'][0]['file']='../../untrusted.json'
        self.index.write_text(json.dumps(d))
        with self.assertRaisesRegex(ValueError,'Utrygg resultatfil'):
            self.run_qa()
        self.assertFalse(self.dest.exists())
        self.assertFalse(any(p.name.startswith('.noark5-a11.5-') for p in self.root.iterdir()))

    def test_cli_preflight_and_regular_run(self):
        args=['--dwm-root',str(self.dwm_root),'--xml-root',str(self.xml_root),
              '--noark-version','5.0','--kdrs-dir',str(self.kdrs_root),
              '--dwm-run-dir',str(self.run_dir)]
        from contextlib import redirect_stdout
        from io import StringIO
        with redirect_stdout(StringIO()) as stream:
            self.assertEqual(main(args+['--preflight']),0)
        self.assertIn('"xml_sha256_read": false',stream.getvalue())
        with redirect_stdout(StringIO()):
            self.assertEqual(main(args+['--output-dir',str(self.dest)]),0)
        self.assertTrue((self.dest/EXTRA_FILES[1]).is_file())

if __name__ == '__main__':
    unittest.main()
