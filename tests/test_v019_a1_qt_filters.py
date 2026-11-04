"""Headless Qt filtering logic tests: actual method AST, no GUI display required."""
from __future__ import annotations

import ast
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
import unittest

ROOT = Path(__file__).resolve().parents[1]


class _Row:
    def __init__(self, *values):
        self.values = values
        self.hidden = False

    def text(self, index):
        return self.values[index]

    def columnCount(self):
        return len(self.values)

    def setHidden(self, hidden):
        self.hidden = hidden


class _Tree:
    def __init__(self, rows):
        self.rows = rows

    def topLevelItemCount(self):
        return len(self.rows)

    def topLevelItem(self, index):
        return self.rows[index]


class _Control:
    def __init__(self, value=""):
        self.value = value

    def currentData(self):
        return self.value

    def text(self):
        return self.value


class _Label:
    value = ""

    def setText(self, value):
        self.value = value


def _methods(*names):
    text = (ROOT / "gui_qt" / "result_center_v019_a1.py").read_text(encoding="utf-8")
    module = ast.parse(text)
    target = next(node for node in module.body if isinstance(node, ast.ClassDef)
                  and node.name == "ResultCenterWindow")
    functions = []
    for name in names:
        source = next(node for node in target.body if isinstance(node, ast.FunctionDef)
                      and node.name == name)
        node = deepcopy(source)
        node.decorator_list = []
        functions.append(node)
    compiled = ast.Module(body=[ast.ImportFrom(module="__future__", names=[
        ast.alias(name="annotations")], level=0)] + functions, type_ignores=[])
    relation_node = next(node for node in module.body
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name)
           and t.id == "_RELATION_LABELS" for t in node.targets))
    namespace = {"_RELATION_LABELS": ast.literal_eval(relation_node.value)}
    exec(compile(ast.fix_missing_locations(compiled), str(ROOT), "exec"), namespace)
    return tuple(namespace[name] for name in names)


class HeadlessQtFilterTests(unittest.TestCase):
    def test_source_filter_category_and_search(self):
        checker, apply = _methods("_match", "_filter_sources")
        rows = [_Row("JOB-001 – Example", "DWM – tekniske kontroller", "", "", "", "", ""),
                _Row("JOB-002 – Test", "Arkade 5 – PRONOM", "I-1", "OK", "14", "filer", "abc"),
                _Row("JOB-003 – Other", "Arkade 5 – PRONOM", "I-2", "", "", "", "")]
        w = SimpleNamespace(_trees={"Kildeoversikt": _Tree(rows)},
                            source_kind=_Control("Arkade 5 – PRONOM"),
                            source_search=_Control("Test"), source_count=_Label(),
                            _match=checker)
        apply(w)
        self.assertEqual([row.hidden for row in rows], [True, False, True])
        self.assertIn("1 av 3", w.source_count.value)

    def test_arkade_relations_are_filtered_without_status_inference(self):
        checker, apply = _methods("_match", "_filter_coverage")
        rows = [_Row("JOB-001", "I-1", "N5.62", "Endringslogg", "FEIL", "Delvis overlapp", "dwm-7"),
                _Row("JOB-001", "I-1", "N5.70", "Arkade alene", "OK", "Kun Arkade 5", "–")]
        models = [SimpleNamespace(relation="partial"), SimpleNamespace(relation="arkade_only")]
        w = SimpleNamespace(_trees={"Arkade-dekning": _Tree(rows)},
                            _a1_coverage=models, coverage_kind=_Control("partial"),
                            coverage_search=_Control("N5.62"), coverage_count=_Label(),
                            _match=checker)
        apply(w)
        self.assertEqual([row.hidden for row in rows], [False, True])
        self.assertIn("1 av 2", w.coverage_count.value)

    def test_kdrs_standard_u1_u2_filter_has_no_near_matches(self):
        checker, apply = _methods("_match", "_filter_kdrs")
        rows = [_Row("JOB-001", "X", "U1", "", ""),
                _Row("JOB-001", "X", "U2", "", ""),
                _Row("JOB-001", "X", "U11", "", ""),
                _Row("JOB-001", "X", "Standard", "", "")]
        w = SimpleNamespace(_trees={"KDRS Query": _Tree(rows)},
                            kdrs_kind=_Control("u1"), kdrs_search=_Control(),
                            kdrs_count=_Label(), _match=checker)
        apply(w)
        self.assertEqual([row.hidden for row in rows], [False, True, True, True])
        self.assertIn("1 av 4", w.kdrs_count.value)

    def test_kdrs_placeholder_is_not_counted_as_evidence(self):
        checker, apply = _methods("_match", "_filter_kdrs")
        placeholder = _Row("Ingen lagret evidens for denne kilden", "", "", "", "")
        w = SimpleNamespace(_trees={"KDRS Query": _Tree([placeholder])},
                            kdrs_kind=_Control(), kdrs_search=_Control(),
                            kdrs_count=_Label(), _match=checker)
        apply(w)
        self.assertFalse(placeholder.hidden)
        self.assertIn("0 av 1", w.kdrs_count.value)
        w.kdrs_kind.value = "standard"
        apply(w)
        self.assertTrue(placeholder.hidden)


if __name__ == "__main__":
    unittest.main()
