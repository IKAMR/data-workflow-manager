from __future__ import annotations
from pathlib import Path
import json
import tempfile
import unittest
from app.xml_value_evidence_v0114_a3 import (find_xml_values, source_xpath_for_finding, source_xml_for_work)

class XmlValueEvidenceTests(unittest.TestCase):
    def test_xpath_catalog_mapping(self):
        self.assertEqual(source_xpath_for_finding('kdrs.c02','document_medium'),
                         '//arkivdel//dokumentbeskrivelse/dokumentmedium')
        self.assertIsNone(source_xpath_for_finding('unknown','document_medium'))

    def test_real_exact_value_and_location(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'arkivstruktur.xml'
            content='<arkiv><arkivdel><systemID>AD1</systemID><mappe><registrering><dokumentbeskrivelse><systemID>D1</systemID><dokumentmedium>Elektroniskarkiv</dokumentmedium></dokumentbeskrivelse><dokumentbeskrivelse><systemID>D2</systemID><dokumentmedium>Elektronisk arkiv</dokumentmedium></dokumentbeskrivelse></registrering></mappe></arkivdel></arkiv>'
            p.write_text(content,encoding='utf-8')
            selector=source_xpath_for_finding('kdrs.c02','document_medium')
            rows=find_xml_values(p,selector,'Elektroniskarkiv')
            self.assertEqual(len(rows),1)
            self.assertEqual(rows[0].value,'Elektroniskarkiv')
            self.assertEqual(rows[0].system_id,'D1')
            self.assertIn('/dokumentbeskrivelse[1]/dokumentmedium[1]',rows[0].xpath)
            self.assertGreater(rows[0].line,0)
            self.assertIn('Elektroniskarkiv',rows[0].xml)
            self.assertEqual(p.read_text('utf-8'),content)
            self.assertEqual(find_xml_values(p,selector,'Elektronisk arkiv')[0].system_id,'D2')

    def test_work_saved_source(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); w=root/'work'; w.mkdir(); src=root/'source'; src.mkdir()
            (src/'arkivstruktur.xml').write_text('<arkiv/>',encoding='utf-8')
            (w/'job.json').write_text(json.dumps({'job':{'source_extraction':str(src)}}),encoding='utf-8')
            self.assertEqual(source_xml_for_work(w),src/'arkivstruktur.xml')

    def test_saved_edge_position_remains_unchanged(self):
        from gui_qt.window_positions_v0114_a1 import Rect, restored_main_rect
        screen=Rect(6000,0,2000,1200)
        saved=Rect(6900,0,1100,800)
        self.assertEqual(restored_main_rect(saved,[screen]),saved)

    def test_only_allow_reviewed_xpath(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'arkivstruktur.xml'; p.write_text('<arkiv/>',encoding='utf-8')
            with self.assertRaises(ValueError): find_xml_values(p,'//*','x')

if __name__ == '__main__': unittest.main()
