"""a8.1 read-only XML formatting/export and Work isolation regression."""
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from app.xml_context_v0114_a8 import readable_xml, save_xml_extract


class XmlExportTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.source = self.root / 'content' / 'sip' / 'content' / 'arkivstruktur.xml'
        self.source.parent.mkdir(parents=True)
        self.source.write_text('<arkiv><mappe><dokumentmedium>Elektroniskarkiv</dokumentmedium></mappe></arkiv>', encoding='utf-8')
        self.work = self.root / 'repository_operations' / 'dwm' / 'a03'
        self.work.mkdir(parents=True)
        (self.work / 'job.json').write_text('{}', encoding='utf-8')

    def tearDown(self):
        self.tmp.cleanup()

    def test_readable_fixed_indentation_preserves_text(self):
        xml = '<mappe xmlns="urn:a">\n              <tittel> Ord  med  mellomrom </tittel>\n                       <registrering>\n                                         <journalposttype>Inngående brev</journalposttype>\n                       </registrering>\n         </mappe>'
        formatted = readable_xml(xml)
        self.assertIn('\n  <tittel> Ord  med  mellomrom </tittel>', formatted)
        self.assertIn('\n  <registrering>\n    <journalposttype>', formatted)
        self.assertNotIn('                                         <journalposttype>', formatted)
        from lxml import etree
        self.assertEqual(etree.fromstring(xml.encode()).xpath('//*[local-name()="tittel"]')[0].text,
                         etree.fromstring(formatted.encode()).xpath('//*[local-name()="tittel"]')[0].text)

    def test_export_isolated_inside_work_with_manifest(self):
        original = self.source.read_bytes()
        xml = '<dokumentmedium xmlns="urn:a">Elektroniskarkiv</dokumentmedium>'
        folder = save_xml_extract(self.work, source=self.source,
                                  xpath='/arkiv[1]/mappe[1]/dokumentmedium[1]',
                                  xml_text=xml, scope='metadatafelt', line=3,
                                  test_id='kdrs.c02', full_section=False)
        self.assertEqual(folder.parent, self.work / 'custom_work' / 'xml_extracts')
        self.assertEqual((folder / 'extract.xml').read_text(), xml)
        man = json.loads((folder / 'manifest.json').read_text())
        self.assertEqual(man['source_xpath'], '/arkiv[1]/mappe[1]/dokumentmedium[1]')
        self.assertEqual(man['export_sha256'], hashlib.sha256(xml.encode()).hexdigest())
        self.assertEqual(self.source.read_bytes(), original)
        self.assertFalse((self.root / 'content' / 'custom_work').exists())

    def test_reject_truncated_xml_and_missing_work(self):
        args = dict(source=self.source, xpath='/arkiv[1]/mappe[1]',
                    scope='mappe', line=1, test_id='kdrs.c02')
        with self.assertRaises(ValueError):
            save_xml_extract(self.work, xml_text='<mappe><x/></mappe>\n<!-- XML-utdrag avkortet for visning; original uendret -->', **args)
        with self.assertRaises(ValueError):
            save_xml_extract(self.root / 'content', xml_text='<mappe/>', **args)
        self.assertFalse((self.work / 'custom_work').exists())

    def test_gui_contract_sort_reset_and_export(self):
        source = (Path(__file__).resolve().parents[1] / 'gui_qt/standard_values_v0114_a2.py').read_text(encoding='utf-8')
        self.assertIn('def _click_sort(', source)
        self.assertIn('def _reset_sorting(', source)
        self.assertIn('def _export_xml(', source)
        self.assertIn('def _switch_xml_mode(', source)
        self.assertIn('save_xml_extract(', source)
        self.assertIn('self.results.horizontalHeader().sectionClicked.connect(self._click_sort)', source)
        self.assertIn('self.results.setSortingEnabled(False)', source)

if __name__ == '__main__':
    unittest.main()
