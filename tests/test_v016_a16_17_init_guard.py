from pathlib import Path


def test_a16_17_guards_reviewed_period_vars_during_construction():
    text = Path("gui/depot_result_center_a16_17.py").read_text(encoding="utf-8")
    assert 'getattr(self, "_a1616_start_var", None) is None' in text
    assert "DepotResultCenterDialogA16_15._show_archive_part(self, index)" in text
    assert "DepotResultCenterDialogA16_16._show_archive_part(self, index)" in text
