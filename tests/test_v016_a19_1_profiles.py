from gui.depot_result_center_a19_1 import _correspondence_profile, _sparkline
from gui.persistent_app_a19_1 import _group_journalpost_types


def test_correspondence_groups_standard_and_short_values():
    grouped = _group_journalpost_types({
        "Inngående dokument": 10,
        "U": 7,
        "Organinternt dokument for oppfølging": 3,
        "X": 2,
        "Saksframlegg": 1,
    })
    assert grouped == {"incoming": 10, "outgoing": 7, "note": 5, "other": 1}


def test_correspondence_profile_is_presentation_only_model_data():
    model = {"_a19_correspondence_counts": {"incoming": 4, "outgoing": 3, "note": 2, "other": 1}}
    assert _correspondence_profile(model) == {"incoming": 4, "outgoing": 3, "note": 2, "other": 1}


def test_sparkline_preserves_outer_years_and_shape():
    text = _sparkline({2007: 1, 2008: 4, 2009: 8, 2010: 4, 2011: 1})
    assert text.startswith("2007")
    assert text.endswith("2011")
    assert "█" in text


def test_sparkline_marks_missing_middle_year():
    text = _sparkline({2007: 5, 2009: 5})
    assert "·" in text


def test_sparkline_empty_is_explicit():
    assert _sparkline({}) == "–"
