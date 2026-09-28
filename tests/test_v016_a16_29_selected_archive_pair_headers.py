from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_a16_29_runtime_is_last():
    text = (ROOT / "main.py").read_text(encoding="utf-8")
    assert text.rfind("persistent_app_a16_29 import run_gui") > text.rfind("persistent_app_a16_26 import run_gui")


def test_a16_29_skips_abandoned_multiselect_chain():
    text = (ROOT / "gui" / "depot_result_center_a16_29.py").read_text(encoding="utf-8")
    assert "from .depot_result_center_a16_26 import" in text
    assert "from .depot_result_center_a16_27 import" not in text
    assert "from .depot_result_center_a16_28 import" not in text


def test_a16_29_refreshes_cards_from_current_archive_row():
    text = (ROOT / "gui" / "depot_result_center_a16_29.py").read_text(encoding="utf-8")
    assert "row = parts[index]" in text
    assert "self._case_count_for_row(row)" in text
    assert "registration_count" in text
    assert "journalpost_count" in text
    assert "document_description_count" in text
    assert "document_object_count" in text
    assert "self._archive_index" in text


def test_a16_29_keeps_full_journalpost_heading():
    text = (ROOT / "gui" / "depot_result_center_a16_29.py").read_text(encoding="utf-8")
    assert "Registreringer / journalposter" in text
