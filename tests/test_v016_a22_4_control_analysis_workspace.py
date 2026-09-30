from pathlib import Path


def _text(path):
    return Path(path).read_text(encoding="utf-8")


def test_a224_runtime_and_version():
    main = _text("main.py")
    version = _text("version.py")
    assert "from gui.persistent_app_a22_4 import run_gui" in main
    assert 'APP_VERSION = "0.1.6-a22.4' in version
    assert 'APP_NAME = "Data Workflow Manager"' in version


def test_a224_workspace_has_target_structure():
    src = _text("gui/depot_result_center_a22_4.py")
    for token in (
        "Filtrer kontroller...",
        "Utvid alle",
        "Skjul alle",
        "Resultat og evidens",
        "Beskrivelse",
        "Relaterte kontroller",
        "Vurderingspunkter",
        "Faglig vurdering (valgfri)",
        "Evidens og relaterte data",
    ):
        assert token in src


def test_a224_foreground_is_explicit_and_not_permanent():
    src = _text("gui/depot_result_center_a22_4.py")
    assert "SetForegroundWindow" in src
    assert "SetWindowPos" in src
    assert 'win.attributes("-topmost", True)' in src
    assert 'win.attributes("-topmost", False)' in src


def test_a224_target_images_and_docs_present():
    root = Path("docs/design-reference/noark5")
    assert (root / "11-kontrollbehandling-arbeidsflate-mal-a.png").is_file()
    assert (root / "12-kontrollbehandling-arbeidsflate-mal-b.png").is_file()
    doc = _text(root / "11-12-kontrollbehandling-arbeidsflate.md")
    assert "Kontrollresultat, faglig vurdering og vurderingspunkt" in doc
