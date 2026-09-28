from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_a16_28_runtime_is_last():
    text = (ROOT / "main.py").read_text(encoding="utf-8")
    assert text.rfind("persistent_app_a16_28 import run_gui") > text.rfind("persistent_app_a16_26 import run_gui")


def test_a16_28_refreshes_pair_kpis_after_selected_row_render():
    text = (ROOT / "gui" / "depot_result_center_a16_28.py").read_text(encoding="utf-8")
    assert "super()._render_a10_archive_part(index)" in text
    assert "self._refresh_pair_kpis(index)" in text


def test_a16_28_does_not_add_multiselect_layer():
    text = (ROOT / "gui" / "depot_result_center_a16_28.py").read_text(encoding="utf-8")
    assert "a16_27" not in text
    assert "checkbox" not in text.casefold()
