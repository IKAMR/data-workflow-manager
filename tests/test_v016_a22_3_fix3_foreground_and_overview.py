from pathlib import Path

SRC = Path('gui/depot_result_center_a22_3.py').read_text(encoding='utf-8')

def test_windows_foreground_presentation_is_explicit():
    assert 'SetForegroundWindow' in SRC
    assert 'BringWindowToTop' in SRC
    assert 'attributes("-topmost", False)' in SRC

def test_control_workspace_has_progress_overview():
    assert 'Fremdrift:' in SRC
    assert 'overview_progress' in SRC
    assert 'Valgt kontroll:' in SRC

def test_selected_control_is_visually_marked():
    assert 'border_color=theme.BLUE' in SRC
