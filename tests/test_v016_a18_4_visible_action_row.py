from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_a18_4_review_actions_share_visible_period_action_row():
    source = (ROOT / "gui/depot_result_center_a18_4.py").read_text(encoding="utf-8")
    assert 'text="+"' in source
    assert 'text="−"' in source
    assert 'text="?"' in source
    assert 'text="Kommentar…"' in source
    assert 'int(info.get("row", -1)) == 1' in source
    assert 'int(info.get("column", -1)) == 4' in source
    assert 'old_inline.grid_remove()' in source


def test_a18_4_runtime_and_version():
    main = (ROOT / "main.py").read_text(encoding="utf-8")
    version = (ROOT / "version.py").read_text(encoding="utf-8")
    assert "from gui.persistent_app_a18_4 import run_gui" in main
    assert 'VERSION = "0.1.6-a18.4"' in version
