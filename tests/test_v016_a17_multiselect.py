from pathlib import Path


def test_a17_runtime_is_final_import():
    main = Path("main.py").read_text(encoding="utf-8")
    final = "from gui.persistent_app_a17_4 import run_gui"
    assert final in main
    assert main.rfind(final) > main.rfind("from gui.persistent_app_a16_31 import run_gui")


def test_a17_multiselect_has_no_checkbox_ui():
    source = Path("gui/depot_result_center_a17_1.py").read_text(encoding="utf-8")
    assert "CTkCheckBox" not in source
    assert "_a171_selected" in source
    assert "Virtuelt utvalg" in source


def test_a17_reads_ctrl_shift_from_mouse_event():
    source = Path("gui/depot_result_center_a17_3.py").read_text(encoding="utf-8")
    assert "state & 0x0004" in source
    assert "state & 0x0001" in source
    assert "bindtags((self._a173_bindtag,) + tags)" in source


def test_a17_guards_virtual_selection_health():
    source = Path("gui/depot_result_center_a17_4.py").read_text(encoding="utf-8")
    assert "_a174_is_virtual_index" in source
    assert "if not self._a174_is_virtual_index()" in source
    assert "super()._update_health_strip()" in source
    assert "Virtuelt utvalg" in source
