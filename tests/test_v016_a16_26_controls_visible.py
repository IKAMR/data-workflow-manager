from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_a16_26_runtime_is_last():
    text = (ROOT / "main.py").read_text(encoding="utf-8")
    assert text.rfind("persistent_app_a16_26 import run_gui") > text.rfind("persistent_app_a16_25 import run_gui")


def test_controls_are_rebuilt_after_inheritance_chain():
    text = (ROOT / "gui" / "depot_result_center_a16_26.py").read_text(encoding="utf-8")
    assert 'tabs.tab("Kontroller")' in text
    assert "child.destroy()" in text
    assert "self._build_controls_tab(control_tab)" in text


def test_requested_materialized_xpath_dimensions_are_rendered():
    text = (ROOT / "gui" / "depot_result_center_a16_26.py").read_text(encoding="utf-8")
    for token in (
        "journalpost_type_counts",
        "journal_status_counts",
        "relation_type_counts",
        "document_type_counts",
        "variant_format_counts",
        "version_number_counts",
        "format_counts",
    ):
        assert token in text
