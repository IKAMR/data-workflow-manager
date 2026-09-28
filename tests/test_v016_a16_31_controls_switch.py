from pathlib import Path


def test_a1631_bypasses_destroyed_legacy_controls_table():
    text = Path('gui/depot_result_center_a16_31.py').read_text(encoding='utf-8')
    assert 'def _render_a169_controls' in text
    assert '_render_structured_controls' in text
    assert '_a168_controls_table' not in text


def test_main_uses_a1631_runtime():
    text = Path('main.py').read_text(encoding='utf-8')
    assert 'from gui.persistent_app_a16_31 import run_gui' in text
