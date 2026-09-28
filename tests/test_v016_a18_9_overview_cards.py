from gui.depot_result_center_a18_9 import _control_distribution


def test_distribution_uses_materialized_dwm_test_statuses_only():
    model = {
        "technical_validation": {
            "tests": [
                {"status": "ok"},
                {"status": "ok"},
                {"status": "error"},
                {"status": "disabled_by_legacy_source"},
                {"status": "something_else"},
            ]
        }
    }
    counts = _control_distribution(model)
    assert counts == {
        "ok": 2,
        "error": 1,
        "not_run": 1,
        "other": 1,
        "total": 5,
    }


def test_distribution_empty_report_is_safe():
    assert _control_distribution({})["total"] == 0
