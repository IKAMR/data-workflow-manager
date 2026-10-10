"""Regression: archive 41-43 must be accessible even if popup clips after 40."""
import ast
from pathlib import Path
import unittest
from noark5_workflow.external_evidence.archive_part_evidence_a5 import available_archive_parts


class ArchiveNavigationA514Tests(unittest.TestCase):
    def test_all_43_archive_parts_remain_available(self):
        records = [dict(archive_part_index=i, dwm_archive_part=dict(title=f'Del {i}'))
                   for i in range(1, 44)]
        result = available_archive_parts({'records': records})
        self.assertEqual(len(result), 43)
        self.assertEqual(result[-1], (43, 'Del 43'))

    def test_gui_offers_navigable_controls_and_position(self):
        source = (Path(__file__).resolve().parents[1] / 'gui' /
                  'depot_result_center_v017_a1.py').read_text(encoding='utf-8')
        ast.parse(source)
        self.assertIn('def _step_a5_part(', source)
        self.assertIn('self._a5_part_menu.set(labels[target])', source)
        self.assertIn("f'{position} / {len(labels)} arkivdeler'", source)
        self.assertIn("target = (index + step) % len(labels)", source)
        self.assertIn("len(labels) > 1", source)
        self.assertLess(source.index('self._a5_prev_part.pack('), source.index('self._a5_part_menu.pack('))

if __name__ == '__main__':
    unittest.main()
