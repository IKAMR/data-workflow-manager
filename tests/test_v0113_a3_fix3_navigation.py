"""Qt-free contract for accessible, linear Basic navigation."""
from __future__ import annotations

import ast
from pathlib import Path
import unittest

SOURCE = Path(__file__).resolve().parents[1] / 'gui_qt' / 'basic_main_v0113_a2.py'


class BasicNavigationTests(unittest.TestCase):
    def setUp(self):
        source = SOURCE.read_text(encoding='utf-8')
        self.source = source
        tree = ast.parse(source)
        cls = next(node for node in tree.body if isinstance(node, ast.ClassDef)
                   and node.name == 'DwmMainWindow')
        node = next(node for node in cls.body if isinstance(node, ast.FunctionDef)
                    and node.name == '_a3_neighbor_step')
        node.decorator_list = []
        module = ast.fix_missing_locations(ast.Module(body=[node], type_ignores=[]))
        namespace = {}
        exec(compile(module, str(SOURCE), 'exec'), namespace)
        self.neighbor = namespace['_a3_neighbor_step']

    def test_sequence_forward_and_backward(self):
        steps = ('overview', 'source', 'work', 'run')
        for i, step in enumerate(steps):
            self.assertEqual(self.neighbor(step, 1),
                             steps[i + 1] if i < len(steps) - 1 else None)
            self.assertEqual(self.neighbor(step, -1),
                             steps[i - 1] if i else None)

    def test_invalid_step_and_direction_are_safe(self):
        self.assertIsNone(self.neighbor('missing', 1))
        self.assertIsNone(self.neighbor('source', 0))

    def test_active_tab_and_previous_next_controls(self):
        self.assertIn("QPushButton:checked", self.source)
        self.assertIn("'Source' if key == 'source' else title", self.source)
        self.assertIn("button.setChecked(name == step)", self.source)
        self.assertIn("QPushButton('← Forrige'", self.source)
        self.assertIn("QPushButton('Neste →'", self.source)
        self.assertIn("navigation.addWidget(self._a3_previous_button)", self.source)
        self.assertIn("navigation.addWidget(self._a3_next_button)", self.source)
        self.assertIn("layout.insertLayout(1, navigation)", self.source)
        self.assertNotIn("self._a3_step_navigation = QWidget(content)", self.source)
        self.assertIn("self._a3_previous_button.setEnabled(self._a3_neighbor_step(step, -1) is not None)", self.source)


if __name__ == '__main__':
    unittest.main()
