from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]


def _a14_version():
    text = (ROOT / "version.py").read_text(encoding="utf-8")
    match = re.search(r'VERSION\s*=\s*"0\.1\.6-a(\d+)(?:\.(\d+)(?:\.(\d+))?)?"', text)
    if not match:
        return None, None
    alpha = int(match.group(1))
    if alpha > 14:
        return match, (999, 0)
    if alpha < 14:
        return None, None
    if match.group(2) is None:
        return match, (999, 0)
    return match, (int(match.group(2)), int(match.group(3) or 0))



class V016A143ResultWindowFixTests(unittest.TestCase):
    def test_initial_result_center_opens_on_stable_overview(self):
        text = (ROOT / "gui" / "depot_result_center_a14_3.py").read_text(encoding="utf-8")
        self.assertIn("def _activate_archive_parts_tab", text)
        self.assertIn('tabs.set("Oversikt")', text)
        self.assertNotIn('tabs.set("Arkivdeler")', text)

    def test_raw_results_are_named_and_ordered_explicitly(self):
        runtime = ROOT / "gui" / "persistent_app_a14_3_runtime.py"
        if runtime.is_file():
            text = runtime.read_text(encoding="utf-8")
            self.assertIn("Råresultater", text)
            self.assertIn("Depotvurdering", text)

    def test_result_window_is_presented_once_after_rebuild(self):
        text = (ROOT / "gui" / "depot_result_center_a14_3.py").read_text(encoding="utf-8")
        pos_super = text.index("super().__init__(master, **kwargs)")
        pos_release = text.rindex("release_parent_work_window(master)")
        pos_present = text.rindex("present_child_over_parent(self, master)")
        self.assertLess(pos_super, pos_release)
        self.assertLess(pos_release, pos_present)
        self.assertIn("_a26_window_layer.present_native_work_window = lambda", text)
        self.assertIn("_a26_window_layer.present_child_over_parent = lambda", text)

    def test_runtime_activates_a14_3(self):
        main = ROOT / "main.py"
        if main.is_file():
            text = main.read_text(encoding="utf-8")
            self.assertIn("from gui.persistent_app_a14_3 import run_gui", text)

    def test_sources_compile(self):
        compile((ROOT / "gui" / "depot_result_center_a14_3.py").read_text(encoding="utf-8"), "depot_result_center_a14_3.py", "exec")

    def test_version_is_a14_3_or_newer_increment(self):
        match, version = _a14_version()
        self.assertIsNotNone(match)
        self.assertGreaterEqual(version, (3, 0))


if __name__ == "__main__":
    unittest.main()
