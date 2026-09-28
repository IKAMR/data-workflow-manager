from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_a168_runtime_is_wired():
    text = (ROOT / "main.py").read_text(encoding="utf-8")
    assert "from gui.persistent_app_a16_8 import run_gui" in text


def test_a168_contains_structured_controls_and_period_check():
    text = (ROOT / "gui" / "depot_result_center_a16_8.py").read_text(encoding="utf-8")
    assert 'headers = ("Kontroll / felt", "Resultat / verdi", "Kilde", "Status")' in text
    assert "MANGLER OPPGITT YTTERÅR" in text
    assert "Journal-krysskontroll" in text
    assert "width=1110" in text
