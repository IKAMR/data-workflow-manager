from pathlib import Path


def test_a21_exposes_new_job_list_in_main_window():
    text = Path("gui/persistent_app_a56.py").read_text(encoding="utf-8")
    assert 'text="Ny jobbliste"' in text
    assert 'command=self._new_job_list' in text
    assert 'text="Ny jobb"' not in text


def test_main_uses_a21_runtime_layer():
    text = Path("main.py").read_text(encoding="utf-8")
    assert "from gui.persistent_app_a56 import run_gui" in text


def test_a21_version():
    text = Path("version.py").read_text(encoding="utf-8")
    assert 'APP_VERSION = "0.1.5-a21"' in text
