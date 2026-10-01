from pathlib import Path


def _source():
    return Path("gui/arkade5_run_dialog.py").read_text(encoding="utf-8")


class V016A268ArkadeLocationWarningTests:
    def test_dialog_shows_effective_arkade_output(self):
        source = _source()
        assert "Arkade output:" in source
        assert "resolve_arkade5_output_subfolder" in source

    def test_existing_location_mismatch_is_confirmed_before_run(self):
        source = _source()
        assert "def _location_mismatches" in source
        assert "Arkade 5 – endret output-lokasjon" in source
        assert "messagebox.askyesno" in source

    def test_existing_configured_target_does_not_warn_just_for_old_versions(self):
        source = _source()
        assert "if any(root.resolve() == target.resolve() for root in roots):" in source
        assert "continue" in source
