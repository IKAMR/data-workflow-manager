from gui.depot_result_center_a18_8 import _overview_metrics


def test_overview_metrics_use_materialized_report_only():
    model = {
        "summary": {
            "archive_part_count": 3,
            "registration_count": 120,
            "journalpost_count": 95,
            "document_object_count": 40,
        },
        "archive_parts": [
            {"archive_part": {"system_id": "A"}},
            {"archive_part": {"system_id": "B"}},
            {"archive_part": {"system_id": "C"}},
        ],
        "deviations": [{"id": "x"}, {"id": "y"}],
        "technical_validation": {"status": "OK"},
        "external_validation": {
            "arkade5": {
                "imports": [{}, {}],
                "pronom_summary": {"statistics_rows": 7},
            }
        },
    }
    metrics = _overview_metrics(model)
    assert metrics["archive_part_count"] == 3
    assert metrics["review_points"] == 2
    assert metrics["technical_status"] == "OK"
    assert metrics["arkade_runs"] == 2
    assert metrics["pronom_rows"] == 7


def test_overview_metrics_ignore_synthetic_all_archive_parts_row():
    model = {
        "archive_parts": [
            {"is_all_archive_parts": True},
            {"archive_part": {"system_id": "A"}},
        ]
    }
    metrics = _overview_metrics(model)
    assert metrics["archive_part_count"] == 1
