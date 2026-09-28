from pathlib import Path


def test_a16_24_runtime_is_final_import():
    text = Path("main.py").read_text(encoding="utf-8")
    assert "from gui.persistent_app_a16_24 import run_gui" in text
    assert text.rfind("persistent_app_a16_24") > text.rfind("persistent_app_a16_23")


def test_a16_24_loads_folder_and_registration_type_counts():
    text = Path("gui/depot_result_center_a16_24.py").read_text(encoding="utf-8")
    assert '"kdrs_c13.json"' in text
    assert '"kdrs_c14.json"' in text
    assert '"type_counts"' in text
    assert 'f"Andre mapper: ' in text
    assert 'f"Andre registreringer: ' in text
    assert '"Registreringer / journalposter"' in text


def test_a16_24_pair_card_uses_real_case_count():
    text = Path("gui/depot_result_center_a16_24.py").read_text(encoding="utf-8")
    assert 'right_value = self._case_count_for_row(row)' in text
