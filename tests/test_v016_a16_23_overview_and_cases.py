from pathlib import Path


def test_a16_23_runtime_is_final_import():
    text = Path("main.py").read_text(encoding="utf-8")
    assert "from gui.persistent_app_a16_23 import run_gui" in text
    assert text.rfind("persistent_app_a16_23") > text.rfind("persistent_app_a16_22")


def test_a16_23_uses_materialized_saksmappe_count():
    text = Path("gui/depot_result_center_a16_23.py").read_text(encoding="utf-8")
    assert '"kdrs_c13.json"' in text
    assert '"saksmappe"' in text
    assert '"Registreringer / journalposter"' in text
    assert 'f"Saker: ' in text
    assert 'f"Arkiv: ' in text
