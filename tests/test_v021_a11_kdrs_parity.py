import json
from pathlib import Path
import tempfile
import unittest

from app.noark5_kdrs_parity_v021_a11 import compare, write_report, canonical


class A11ParityTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.xml = self.root / 'arkivstruktur.xml'
        self.xml.write_text('<arkiv/>', encoding='utf-8')
        import hashlib
        self.hash = hashlib.sha256(self.xml.read_bytes()).hexdigest()
        self.out = self.root / 'work'
        (self.out / 'results').mkdir(parents=True)
        self.index = self.out / 'index.json'
        self.kdrs = self.root / 'kdrs.json'
        self.mapping = self.root / 'mapping.json'
        self._write(self.index, {'result_set_format_version':2, 'tests':[
            {'test_id':'kdrs.c01','status':'ok','file':'results/kdrs_c01.json'}]})
        self._write(self.out / 'results/kdrs_c01.json', {
            'test_id':'kdrs.c01','status':'ok','source_xml':'arkivstruktur.xml',
            'source_path':str(self.xml),'values':{'archive_count':1}})
        self._write(self.kdrs, {'format_version':1,'engine':'Saxon',
             'xml_sha256':{'arkivstruktur.xml':self.hash}, 'jobs':{'C01':{'count':1}}})
        self._write(self.mapping, {'format_version':1,'comparisons':[
             {'job_id':'C01','test_id':'kdrs.c01','kdrs_path':'count','dwm_path':'archive_count'}]})

    @staticmethod
    def _write(path, obj):
        path.write_text(json.dumps(obj), encoding='utf-8')

    def run_comparison(self):
        return compare(self.index, self.kdrs, self.mapping, self.root)

    def test_match_with_identical_xml(self):
        r = self.run_comparison()
        self.assertEqual(r['summary']['provisional_matches'],1)
        self.assertFalse(r['summary']['whole_standard_saxon_lxml_parity_verified'])

    def test_mismatch(self):
        k = json.loads(self.kdrs.read_text())
        k['jobs']['C01']['count'] = 2
        self._write(self.kdrs,k)
        self.assertEqual(self.run_comparison()['summary']['provisional_mismatches'],1)

    def test_source_changed_prevents_comparison(self):
        self.xml.write_text('<arkiv changed="yes"/>')
        r = self.run_comparison()
        self.assertEqual(r['summary']['not_comparable'],1)

    def test_missing_job_not_comparable(self):
        k = json.loads(self.kdrs.read_text())
        k['jobs'] = {}
        self._write(self.kdrs,k)
        self.assertEqual(self.run_comparison()['comparisons'][0]['reason'],'kdrs_job_missing')

    def test_missing_metric_not_comparable(self):
        k = json.loads(self.kdrs.read_text())
        k['jobs']['C01'] = {}
        self._write(self.kdrs,k)
        self.assertEqual(self.run_comparison()['comparisons'][0]['reason'],'metric_not_found')

    def test_dwm_xml_mismatch_prevents_comparison(self):
        d = json.loads((self.out/'results/kdrs_c01.json').read_text())
        different = self.root/'different.xml'
        different.write_text('<other/>')
        d['source_path']=str(different)
        self._write(self.out/'results/kdrs_c01.json',d)
        self.assertEqual(self.run_comparison()['comparisons'][0]['reason'],'dwm_xml_sha256_mismatch')

    def test_dict_order_ignored_list_order_kept(self):
        self.assertEqual(canonical({'a':1,'b':2}),canonical({'b':2,'a':1}))
        self.assertNotEqual(canonical([1,2]), canonical([2,1]))
        self.assertNotEqual(canonical(True), canonical(1))

    def test_duplicate_mapping_rejected(self):
        m = json.loads(self.mapping.read_text())
        m['comparisons'] *= 2
        self._write(self.mapping,m)
        with self.assertRaises(ValueError): self.run_comparison()

    def test_output_immutable(self):
        p=self.root/'reports'
        r=self.run_comparison()
        write_report(r,p)
        self.assertEqual(len(list(p.iterdir())),3)
        with self.assertRaises(FileExistsError): write_report(r,p)

    def test_path_traversal_rejected(self):
        d=json.loads(self.index.read_text())
        d['tests'][0]['file']='../../outside.json'
        self._write(self.index,d)
        with self.assertRaises(ValueError): self.run_comparison()

if __name__=='__main__': unittest.main()
