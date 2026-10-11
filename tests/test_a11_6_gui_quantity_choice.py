import ast
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from gui.noark5_quantity_choices_a116 import selection_key, selected_payload


class TestQuantityGUI(unittest.TestCase):
    def test_existing_gui_and_generator_compile(self):
        for path in (ROOT / 'gui/noark5_multi_overview_a65.py', ROOT / 'tools/noark5_batch_overview_a6.py'):
            ast.parse(path.read_text(encoding='utf-8'))

    def test_payload_explicit_and_scoped(self):
        items = [
            {'job': 'JOB-002', 'extraction': 'one', 'metric': 'folder_count', 'source': 'Arkade 5', 'count': 66834, 'label': 'Mapper', 'dwm_count': None},
            {'job': 'JOB-002', 'extraction': 'two', 'metric': 'folder_count', 'source': 'Arkade 5', 'count': 10, 'label': 'Mapper', 'dwm_count': 10},
        ]
        chosen = selected_payload(items, {selection_key(items[0])})
        self.assertEqual(chosen, {'choices': [{'job': 'JOB-002', 'extraction': 'one', 'metric': 'folder_count', 'source': 'Arkade 5', 'count': 66834}]})

    def test_no_selection(self):
        self.assertEqual(selected_payload([], set()), {'choices': []})

    def test_worker_manifest_is_transient(self):
        gui = (ROOT / 'gui/noark5_multi_overview_a65.py').read_text(encoding='utf-8')
        self.assertIn('TemporaryDirectory', gui)
        self.assertIn("'--quantity-selections'", gui)
        self.assertIn('self._quantity_selected', gui)
        self.assertIn('Velg Arkade 5-totaler', gui)


if __name__ == '__main__':
    unittest.main()
