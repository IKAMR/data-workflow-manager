"""a11.3: real KDRS Query 0.9 text output, guarded candidate extraction."""
from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest
from hashlib import sha256

from app.noark5_kdrs_text_import_v021_a11 import (
    _read_report, _parse_count, _source_jobs, build_import, write_import,
)
from app.noark5_kdrs_parity_v021_a11 import compare, write_report


class A11HistoricalReportTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.dwm = self.root / 'dwm'
        src = self.dwm / 'docs/reference/kdrs-query'
        src.mkdir(parents=True)
        self.xml = self.root / 'source'
        self.xml.mkdir()
        (self.xml/'arkivstruktur.xml').write_text('<arkiv/>', encoding='utf-8')
        source_def = '''_PARAMETERS_
[XML_QUERY]
job_id=C05
job_enabled=1
job_name=Klassifikasjonssystemer
source=arkivstruktur.xml
#START#
concat("N5.07 Klassifikasjonssystemer: ", count(//klassifikasjonssystem))
#STOP#
[XML_QUERY]
job_id=C10
job_enabled=1
job_name=Klassekonflikt
source=arkivstruktur.xml
#START#
concat("N5.12 Klasser med både mappe og underklasse (>0 er avvik): ", count(//klasse[klasse]/mappe))
#STOP#
[XML_QUERY]
job_id=U01
job_enabled=3
job_name=U1
source=arkivstruktur.xml
#START#
concat("U1. N5.101", count(//arkiv))
#STOP#
'''
        (src/'xml-queries_noark5_2026-05-26.txt').write_text(source_def,encoding='utf-8')
        (src/'xml-queries_noark5_2026-05-26_U1.txt').write_text('''[XML_QUERY]
job_id=U01
source=arkivstruktur.xml
#START#
concat("U1. N5.101", count(//arkiv))
#STOP#
''',encoding='utf-8')
        (src/'xml-queries_noark5_2026-05-26_U2.txt').write_text('''[XML_QUERY]
job_id=U02
source=arkivstruktur.xml
#START#
concat("U2. N5.102", count(//arkivdel))
#STOP#
''',encoding='utf-8')
        cat = {'tests': [
            {'test_id':'kdrs.c05','legacy':{'job_id':'C05'},'source_xml':'arkivstruktur.xml',
             'execution':{'kind':'metrics','metrics':[{'id':'classification_system_count','type':'xpath',
                                                      'expression':'count(//klassifikasjonssystem)'}]}},
            {'test_id':'kdrs.c10','legacy':{'job_id':'C10'},'source_xml':'arkivstruktur.xml',
             'execution':{'kind':'metrics','metrics':[{'id':'class_with_subclass_and_folder','type':'xpath',
                                                      'expression':'count(//klasse[klasse]/mappe)'}]}},
            {'test_id':'kdrs.u01','legacy':{'job_id':'U01'},'source_xml':'arkivstruktur.xml',
             'execution':{'kind':'u1_total'}},
            {'test_id':'kdrs.u02','legacy':{'job_id':'U02'},'source_xml':'arkivstruktur.xml',
             'execution':{'kind':'u2_archive_parts'}},
        ]}
        dest = self.dwm / 'config/noark5/tests/xpath_catalog_2026_05_26.json'
        dest.parent.mkdir(parents=True)
        dest.write_text(json.dumps(cat),encoding='utf-8')
        self.standard = self.root/'standard.txt'
        self.standard.write_text('''Query file: C:\\git\\KDRS_Query\\doc\\xml-queries_noark5_2026-05-26.txt

=================================

C05
1
Klassifikasjonssystemer
N5.07
noark5

arkivstruktur.xml
noark5_analyse.log
concat("N5.07 Klassifikasjonssystemer: ", count(//klassifikasjonssystem))

Query result:
N5.07 Klassifikasjonssystemer: 0
=================================
C10

N5.12 Klasser med både mappe og underklasse (>0 er avvik): 0
=================================
''',encoding='utf-8')
        self.u1 = self.root/'u1.txt'
        self.u1.write_text('''Query file: C:\\git\\KDRS_Query\\doc\\xml-queries_noark5_2026-05-26.txt

=================================
U01
3
U1
N5.101
noark5

arkivstruktur.xml
noark5_analyse.log
concat("U1. N5.101", count(//arkiv))

Query result:
U1. N5.101, Arkiv 1
=================================
''',encoding='utf-8')
        self.u2 = self.root/'u2.txt'
        self.u2.write_text('''Query file: C:\\git\\KDRS_Query\\doc\\xml-queries_noark5_2026-05-26_U2.txt

=================================
U02

U2. N5.102: Arkivdel 1
  Generisk mappe 4
=================================
''',encoding='utf-8')

    def build(self, reports=None):
        return build_import(dwm_root=self.dwm,xml_root=self.xml,
                            reports=reports or {'STANDARD':self.standard,'U1':self.u1,'U2':self.u2},
                            noark_version='5.0')

    def test_read_full_and_clean_and_separate_files(self):
        source,jobs=_read_report(self.standard)
        self.assertEqual(source,'xml-queries_noark5_2026-05-26.txt')
        self.assertEqual([j.job_id for j in jobs],['C05','C10'])
        self.assertTrue(jobs[0].verbose)
        self.assertIn('count(//klassifikasjonssystem)',jobs[0].embedded_query)
        self.assertFalse(jobs[1].verbose)
        self.assertEqual(jobs[1].raw_result,'N5.12 Klasser med både mappe og underklasse (>0 er avvik): 0')
        self.assertEqual([j.job_id for j in _read_report(self.u1)[1]],['U01'])
        self.assertEqual([j.job_id for j in _read_report(self.u2)[1]],['U02'])

    def test_import_all_profiles_keeps_complex_u1_u2_opaque(self):
        legacy,map_,inventory=self.build()
        self.assertEqual(sorted(legacy['jobs']),['C05','C10','U01','U02'])
        self.assertEqual(legacy['jobs']['C05']['metrics']['classification_system_count'],0)
        self.assertEqual(legacy['jobs']['C10']['metrics']['class_with_subclass_and_folder'],0)
        self.assertEqual(legacy['jobs']['U01']['metrics'],{})
        self.assertEqual(legacy['jobs']['U02']['metrics'],{})
        self.assertFalse(legacy['runtime_input_bytes_attested'])
        self.assertFalse(legacy['runtime_saxon_engine_attested'])
        self.assertEqual(len(map_['comparisons']),2)
        self.assertEqual(sum(r['mapping_status']=='COUNT_CANDIDATE_PROVISIONAL' for r in inventory),2)
        self.assertTrue(legacy['xml_sha256']['arkivstruktur.xml'])

    def test_correct_dwm_input_produces_provisional_match_not_verified_parity(self):
        legacy,map_,inv=self.build({'STANDARD':self.standard})
        out=self.root/'out'
        kdrs_path,mapping_path,*_=write_import(legacy,map_,inv,out)
        dwm_run=self.root/'dwm_run'
        (dwm_run/'results').mkdir(parents=True)
        files=[]
        for id_,metric in [('c05','classification_system_count'),('c10','class_with_subclass_and_folder')]:
            (dwm_run/'results'/f'kdrs_{id_}.json').write_text(json.dumps({
                'test_id':f'kdrs.{id_}','status':'ok','source_xml':'arkivstruktur.xml',
                'source_path':str(self.xml/'arkivstruktur.xml'), 'values':{metric:0}}))
            files.append({'test_id':f'kdrs.{id_}','file':f'results/kdrs_{id_}.json','status':'ok'})
        index=dwm_run/'index.json'
        index.write_text(json.dumps({'result_set_format_version':2,'tests':files}))
        result=compare(index,kdrs_path,mapping_path,self.xml)
        self.assertEqual(result['summary']['provisional_matches'],2)
        self.assertFalse(result['summary']['whole_standard_saxon_lxml_parity_verified'])
        self.assertFalse(result['summary']['execution_time_source_identity_attested'])
        write_report(result,out)
        self.assertEqual(len(list(out.glob('noark5-a11*'))),7)
        csvtext=(out/'noark5-a11-parity.csv').read_text()
        self.assertIn('kdrs_value,dwm_value',csvtext.splitlines()[0])
        self.assertIn('MATCH_PROVISIONAL',csvtext)

    def test_unknown_query_basename_does_not_map(self):
        self.standard.write_text(self.standard.read_text().replace('2026-05-26.txt','2022-09-21.txt'))
        legacy,map_,inv=self.build({'STANDARD':self.standard})
        self.assertEqual(legacy['jobs']['C05']['metrics'],{})
        self.assertEqual(len(map_['comparisons']),0)
        self.assertTrue(any(x['kind']=='historical_query_source_basename_unknown'
                            for x in legacy['import_issues']))

    def test_standard_no_journal_variant_is_checked_against_its_own_source(self):
        p=self.dwm/'docs/reference/kdrs-query/xml-queries_noark5_2026-05-26_no-journal.txt'
        source=(self.dwm/'docs/reference/kdrs-query/xml-queries_noark5_2026-05-26.txt').read_text()
        p.write_text(source,encoding='utf-8')
        self.standard.write_text(self.standard.read_text().replace(
            'xml-queries_noark5_2026-05-26.txt',
            'xml-queries_noark5_2026-05-26_no-journal.txt'))
        legacy,map_,inv=self.build({'STANDARD':self.standard})
        self.assertEqual(legacy['jobs']['C05']['metrics']['classification_system_count'],0)
        self.assertIn('xml-queries_noark5_2026-05-26_no-journal.txt',
                      legacy['kdrs_reference_source_sha256'])
        self.assertEqual(len(map_['comparisons']),2)

    def test_wrong_embedded_query_rejected_from_matching(self):
        text=self.standard.read_text().replace('count(//klassifikasjonssystem))','count(//wrong))',1)
        self.standard.write_text(text)
        legacy,map_,inv=self.build({'STANDARD':self.standard})
        self.assertEqual(legacy['jobs']['C05']['metrics'],{})
        self.assertEqual(len(map_['comparisons']),1)  # C10 is still safe to compare.
        self.assertTrue(any(x['kind']=='embedded_query_differs_from_reference'
                            for x in legacy['import_issues']))

    def test_missing_source_xml_keeps_opaque_and_records_qa(self):
        (self.xml/'arkivstruktur.xml').unlink()
        legacy,map_,inv=self.build({'STANDARD':self.standard})
        self.assertEqual(legacy['missing_xml_at_import'],['arkivstruktur.xml'])
        self.assertEqual(legacy['xml_sha256'],{})

    def test_dwm_xpath_change_blocks_unreviewed_mapping(self):
        path=self.dwm/'config/noark5/tests/xpath_catalog_2026_05_26.json'
        cat=json.loads(path.read_text())
        cat['tests'][0]['execution']['metrics'][0]['expression']='count(//other)'
        path.write_text(json.dumps(cat))
        legacy,map_,inv=self.build({'STANDARD':self.standard})
        self.assertEqual(legacy['jobs']['C05']['metrics'],{})
        self.assertEqual(len(map_['comparisons']),1)
        self.assertTrue(any(x['kind']=='kdrs_or_dwm_xpath_witness_mismatch'
                            for x in legacy['import_issues']))

    def test_error_not_numeric_and_ambiguous_rejected(self):
        self.assertEqual(_parse_count('ERROR 1, unable to compile: bad','N5.07 Klassifikasjonssystemer:'),
                         (None,'kdrs_query_failed'))
        self.assertEqual(_parse_count('N5.07 Klassifikasjonssystemer: 12.3','N5.07 Klassifikasjonssystemer:'),
                         (None,'label_missing_or_ambiguous'))
        self.assertEqual(_parse_count('N5.07 Klassifikasjonssystemer: 12, N5.07 Klassifikasjonssystemer: 13',
                                      'N5.07 Klassifikasjonssystemer:'),
                         (None,'label_missing_or_ambiguous'))

    def test_duplicate_job_and_missing_separator_error(self):
        self.standard.write_text(self.standard.read_text()+'C05\n\nN5.07 Klassifikasjonssystemer: 1\n=================================\n')
        with self.assertRaisesRegex(ValueError,'Duplisert'):
            _read_report(self.standard)
        self.standard.write_text('Query file: file.txt\nC05\n')
        with self.assertRaisesRegex(ValueError,'seksjonsskilletegn'):
            _read_report(self.standard)

    def test_output_immutable_and_raw_results_not_republished(self):
        legacy,map_,inv=self.build()
        out=self.root/'out'
        paths=write_import(legacy,map_,inv,out)
        self.assertEqual(len(paths),4)
        self.assertIn('Saxon',paths[-1].read_text())
        with self.assertRaises(FileExistsError): write_import(legacy,map_,inv,out)
        self.assertNotIn('U2. N5.102: Arkivdel 1', paths[0].read_text())

    def test_manifest_is_exact_bytes_not_normalized_xml(self):
        legacy,_,_=self.build()
        actual=sha256((self.xml/'arkivstruktur.xml').read_bytes()).hexdigest()
        self.assertEqual(legacy['xml_sha256']['arkivstruktur.xml'],actual)
        self.assertTrue(len(legacy['kdrs_reference_source_sha256'])==3)


if __name__=='__main__':
    unittest.main()
