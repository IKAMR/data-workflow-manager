from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_a16_30_runtime_is_last():
    text = (ROOT / "main.py").read_text(encoding="utf-8")
    assert text.rfind("persistent_app_a16_30 import run_gui") > text.rfind("persistent_app_a16_29 import run_gui")


def test_a16_30_refreshes_cards_at_render_point():
    text = (ROOT / "gui" / "depot_result_center_a16_30.py").read_text(encoding="utf-8")
    assert "def _render_a10_archive_part" in text
    assert "row = parts[index]" in text
    assert "self._case_count_for_row(row)" in text
    assert "label.configure" in text
