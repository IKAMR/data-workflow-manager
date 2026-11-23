"""Regression: python -m gui_qt must actually invoke the GUI main function.

This test intentionally does not import Qt or open a window.
"""
from __future__ import annotations

import ast
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
ENTRYPOINT = ROOT / 'gui_qt' / '__main__.py'


class V025A3Fix1StartupTests(unittest.TestCase):
    def test_python_module_entrypoint_invokes_main(self):
        source = ENTRYPOINT.read_text(encoding='utf-8')
        tree = ast.parse(source, filename=str(ENTRYPOINT))
        guards = [
            item for item in tree.body
            if isinstance(item, ast.If)
            and isinstance(item.test, ast.Compare)
            and ast.unparse(item.test) == "__name__ == '__main__'"
        ]
        self.assertEqual(len(guards), 1, 'Missing __main__ launch guard')
        self.assertIn('raise SystemExit(main())', ast.unparse(guards[0]))

    def test_launch_guard_dispatches_exactly_once(self):
        source = ENTRYPOINT.read_text(encoding='utf-8')
        tree = ast.parse(source)
        guard = next(
            item for item in tree.body
            if isinstance(item, ast.If)
            and ast.unparse(item.test) == "__name__ == '__main__'"
        )
        events = []
        def fake_main():
            events.append('started')
            return 27
        scope = {'__name__': '__main__', 'main': fake_main}
        with self.assertRaises(SystemExit) as stopped:
            exec(compile(ast.Module(body=[guard], type_ignores=[]), str(ENTRYPOINT), 'exec'), scope)
        self.assertEqual(stopped.exception.code, 27)
        self.assertEqual(events, ['started'])


if __name__ == '__main__':
    unittest.main()
