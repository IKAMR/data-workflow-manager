from pathlib import Path

from gui.depot_result_center_a18_5 import _context_from_report


def test_context_uses_extraction_root_and_job_id():
    model = {
        "summary": {"archive_part_count": 18},
        "evidence": {
            "source_xpath_run": (
                r"C:\arkiv-noark5\1543\1543_010_E-Docu-2025-0001_AIC-4"
                r"\repository_operations\dwm\bl0\noark5_tests\xpath"
                r"\JOB-001_RUN-20260927-193459"
            )
        },
    }
    label, job_id, count = _context_from_report(model, None)
    assert label == "1543_010_E-Docu-2025-0001_AIC-4"
    assert job_id == "JOB-001"
    assert count == 18


def test_context_has_safe_fallbacks():
    label, job_id, count = _context_from_report({"archive_parts": [{}, {}]}, None)
    assert label == "Ukjent uttrekk"
    assert job_id == "Ukjent jobb"
    assert count == 2
