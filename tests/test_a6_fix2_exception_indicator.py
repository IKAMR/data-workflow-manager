from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class A6Fix2ExceptionIndicatorTests(unittest.TestCase):
    def test_indicator_is_not_gridded_during_install(self):
        text = (
            ROOT / "app" / "exception_monitor.py"
        ).read_text(encoding="utf-8")
        install = text.split("def _install_indicator", 1)[1].split(
            "def _show_indicator", 1
        )[0]
        self.assertNotIn("self.button.grid(", install)

    def test_stale_empty_indicator_can_be_acknowledged(self):
        text = (
            ROOT / "app" / "exception_monitor.py"
        ).read_text(encoding="utf-8")
        show = text.split("def show_errors", 1)[1].split(
            "def clear_indicator", 1
        )[0]
        self.assertIn("if not self.errors:", show)
        self.assertIn("self.clear_indicator()", show)
        self.assertIn('text="Kvitter"', show)


if __name__ == "__main__":
    unittest.main()
