from pathlib import Path


def test_a16_25_runtime_is_final_import():
    text = Path("main.py").read_text(encoding="utf-8")
    assert "from gui.persistent_app_a16_25 import run_gui" in text
    assert text.rfind("persistent_app_a16_25") > text.rfind("persistent_app_a16_24")


def test_a16_25_uses_structured_noark_hierarchy():
    text = Path("gui/depot_result_center_a16_25.py").read_text(encoding="utf-8")
    for heading in (
        "Arkiv / arkivdeler",
        "Mapper / saker",
        "Registreringer / journalposter",
        "Dokumentbeskrivelser / dokumentobjekter",
    ):
        assert heading in text
    for result_file in (
        "kdrs_c13.json",
        "kdrs_c14.json",
        "kdrs_c15.json",
        "kdrs_c21.json",
        "kdrs_c24.json",
    ):
        assert result_file in text


def test_a16_25_preserves_case_sensitive_format_metadata():
    text = Path("gui/depot_result_center_a16_25.py").read_text(encoding="utf-8")
    assert "case beholdes" in text
    assert "format_counts" in text
    assert "journalpost_type_counts" in text
    assert "relation_type_counts" in text
    assert "variant_format_counts" in text
