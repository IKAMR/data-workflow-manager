from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class A5ConsoleErrorIndicatorTests(unittest.TestCase):
    def test_runtime_installs_exception_monitor(self):
        text = (
            ROOT / "gui" / "persistent_app_a37.py"
        ).read_text(encoding="utf-8")
        self.assertIn(
            "from app.exception_monitor import AppExceptionMonitor",
            text,
        )
        self.assertIn(
            "self.exception_monitor = AppExceptionMonitor(self)",
            text,
        )

    def test_monitor_catches_tk_and_worker_thread_exceptions(self):
        text = (
            ROOT / "app" / "exception_monitor.py"
        ).read_text(encoding="utf-8")
        self.assertIn("self.app.report_callback_exception", text)
        self.assertIn("threading.excepthook = self._thread_exception", text)
        self.assertIn("traceback.print_exception", text)

    def test_monitor_has_red_error_indicator_shown_only_after_recorded_error(self):
        text = (
            ROOT / "app" / "exception_monitor.py"
        ).read_text(encoding="utf-8")

        self.assertIn('text="⚠ FEIL"', text)
        self.assertIn("fg_color=theme.DANGER_TEXT", text)

        install = text.split(
            "def _install_indicator", 1
        )[1].split("def _show_indicator", 1)[0]
        self.assertNotIn("self.button.grid(", install)

        show = text.split(
            "def _show_indicator", 1
        )[1].split("def _hide_indicator", 1)[0]
        self.assertIn("self.button.grid(", show)

        record = text.split(
            "def _record(", 1
        )[1].split("def _record_from_any_thread", 1)[0]
        self.assertIn("self._show_indicator()", record)

        hide = text.split(
            "def _hide_indicator", 1
        )[1].split("def _install_hooks", 1)[0]
        self.assertIn("self.button.grid_remove()", hide)

    def test_error_details_are_available_inside_app(self):
        text = (
            ROOT / "app" / "exception_monitor.py"
        ).read_text(encoding="utf-8")
        self.assertIn("CTkToplevel", text)
        self.assertIn("CTkTextbox", text)
        self.assertIn('text="Kvitter"', text)


if __name__ == "__main__":
    unittest.main()
