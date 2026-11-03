from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]


class PythonGilA13Tests(unittest.TestCase):
    def test_test_bat_enables_gil_before_python(self):
        text = (ROOT / "test.bat").read_text(encoding="utf-8")
        self.assertLess(text.index('set "PYTHON_GIL=1"'), text.index("py tests"))

    def test_start_bat_enables_gil_before_python(self):
        # v0.1.8-a3 starts Qt with `py -m gui_qt`, while the legacy
        # launcher continues to use `py main.py`. Check both launchers.
        for filename in ("start.bat", "start-legacy.bat"):
            path = ROOT / filename
            if filename == "start-legacy.bat" and not path.exists():
                continue  # Older releases did not have a legacy launcher.
            with self.subTest(launcher=filename):
                text = path.read_text(encoding="utf-8")
                python_command = re.search(r"(?im)^\s*py(?:\s|$)", text)
                self.assertIsNotNone(python_command, f"Ingen Python-kommando i {filename}")
                self.assertIn('set "PYTHON_GIL=1"', text)
                self.assertLess(text.index('set "PYTHON_GIL=1"'), python_command.start())

    def test_cli_launcher_generated_with_gil_enabled(self):
        text = (ROOT / "install.bat").read_text(encoding="utf-8")
        self.assertIn('echo set "PYTHON_GIL=1"', text)


if __name__ == "__main__":
    unittest.main()
