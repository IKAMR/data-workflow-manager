from pathlib import Path


def _text(path):
    return Path(path).read_text(encoding="utf-8")


def test_a225_version_and_runtime():
    version = _text("version.py")
    main = _text("main.py")
    assert 'APP_VERSION = "0.1.6-a22.5"' in version
    assert "from gui.persistent_app_a22_4 import run_gui" in main


def test_a225_control_window_state_indicator():
    src = _text("gui/depot_result_center_a22_4.py")
    assert "Kontrollbehandling er åpent" in src
    assert "Hent frem behandlingsvindu" in src
    assert "_a224_set_control_window_state" in src


def test_a225_archive_selection_sync():
    src = _text("gui/depot_result_center_a22_4.py")
    assert "def sync_context(new_index: int)" in src
    assert "self._a224_control_sync = sync_context" in src
    assert "sync(int(index))" in src


def test_a225_windows_foreground_and_selected_control():
    src = _text("gui/depot_result_center_a22_4.py")
    assert "AttachThreadInput" in src
    assert "AllowSetForegroundWindow" in src
    assert "SetForegroundWindow" in src
    assert "border_width=3" in src
    assert "fg_color=theme.BLUE if bpos" in src
