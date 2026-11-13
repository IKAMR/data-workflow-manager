import tempfile
import unittest
from pathlib import Path
from app.xml_context_v0114_a8 import inspect_xml_context
from app.xml_value_evidence_v0114_a3 import find_xml_values, source_xpath_for_finding

NS = 'http://www.arkivverket.no/standarder/noark5/arkivstruktur'


def xml_document():
    return f'''<?xml version="1.0"?><arkiv xmlns="{NS}"><systemID>arkiv-id</systemID>
  <arkivdel><systemID>del-id</systemID><klassifikasjonssystem><klasse><mappe>
    <systemID>mappe-id</systemID><tittel>Testmappe</tittel>
    <registrering><systemID>reg1</systemID><dokumentbeskrivelse><dokumentmedium>Normal</dokumentmedium></dokumentbeskrivelse></registrering>
    <registrering><systemID>reg2</systemID><dokumentbeskrivelse><systemID>dok2</systemID><dokumentmedium>Elektroniskarkiv</dokumentmedium></dokumentbeskrivelse></registrering>
    <registrering><systemID>reg3</systemID></registrering>
    </mappe></klasse></klassifikasjonssystem></arkivdel></arkiv>'''

class ContextTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.file = Path(self.dir.name) / 'arkivstruktur.xml'
        self.file.write_text(xml_document(), encoding='utf-8')
    def tearDown(self):
        self.dir.cleanup()
    def test_context_and_actual_sibling_count(self):
        xp = source_xpath_for_finding('kdrs.c02', 'document_medium')
        item = find_xml_values(self.file, xp, 'Elektroniskarkiv')[0]
        ctx = inspect_xml_context(self.file, item.xpath)
        self.assertEqual(ctx.scope, 'mappe')
        self.assertEqual(ctx.xpath, item.xpath)
        self.assertIn('reg1', ctx.xml)
        self.assertIn('reg3', ctx.xml)
        self.assertIn('Elektroniskarkiv', ctx.xml)
        self.assertFalse(ctx.truncated)
        reg = next(x for x in ctx.levels if x.element == 'registrering')
        self.assertEqual((reg.position, reg.total, reg.system_id), (2, 3, 'reg2'))
        self.assertTrue(ctx.levels[-1].selected)
        self.assertEqual(ctx.levels[-1].element, 'dokumentmedium')
        self.assertEqual(ctx.levels[0].element, 'arkiv')
        self.assertIsNone(ctx.levels[0].total)
    def test_wrong_xpath_or_source_fails(self):
        with self.assertRaises(ValueError):
            inspect_xml_context(self.file, '/arkiv[1]/arkivdel[33]/mappe[1]/x[1]')
        with self.assertRaises(ValueError):
            inspect_xml_context(self.file, '../../etc/passwd')
    def test_size_limit_fails_closed(self):
        item = find_xml_values(self.file, source_xpath_for_finding('kdrs.c02','document_medium'), 'Elektroniskarkiv')[0]
        with self.assertRaises(ValueError):
            inspect_xml_context(self.file, item.xpath, max_nodes=4)
    def test_source_is_not_modified(self):
        before = self.file.read_bytes()
        item = find_xml_values(self.file, source_xpath_for_finding('kdrs.c02','document_medium'), 'Elektroniskarkiv')[0]
        inspect_xml_context(self.file, item.xpath)
        self.assertEqual(self.file.read_bytes(), before)


class GuiContract(unittest.TestCase):
    def test_sorting_preserves_evidence_identity(self):
        source = (Path(__file__).resolve().parents[1] /
                  'gui_qt/standard_values_v0114_a2.py').read_text(encoding='utf8')
        import ast
        ast.parse(source)
        self.assertIn('self.results.setSortingEnabled(False)', source)
        self.assertIn('cell.data(Qt.ItemDataRole.UserRole)', source)
        self.assertIn('self.table.setSortingEnabled(True)', source)
        self.assertIn('self.vertical_splitter = QSplitter(', source)
        self.assertIn('self.lower_splitter = QSplitter(', source)
        self.assertIn('inspect_xml_context, self.xml_path, xpath', source)
        self.assertIn('self.structure.setSortingEnabled(False)', source)
        self.assertIn('self._pool.shutdown(wait=False, cancel_futures=True)', source)
