from pathlib import Path
import subprocess
import sys
import tempfile
import json

ROOT=Path(__file__).resolve().parents[1]
GUI=(ROOT/'gui'/'noark5_multi_overview_a65.py').read_text(encoding='utf-8')

def test_selection_and_encoding():
    assert "'--select', *selection" in GUI
    assert 'PYTHONIOENCODING' in GUI
    assert 'CTkScrollableFrame' in GUI

def test_selected_jobs_on_synthetic_k18_structure():
    with tempfile.TemporaryDirectory() as tmp:
        base=Path(tmp)
        for index in range(1,29):
            folder=base/f'1502_{28+index:03d}_ephorte_noark5'/'repository_operations'/'dwm'/'noark5_reports'/'depot_validation'/f'JOB-{index:03d}__RUN-20261010-123456-id'
            folder.mkdir(parents=True)
            (folder/'depot_validation_report.json').write_text(json.dumps({'report_type':'noark5_depot_validation','archive_parts':[]}),encoding='utf-8')
        sys.path.insert(0,str(ROOT))
        import types
        sys.modules['customtkinter'] = types.SimpleNamespace(CTkToplevel=object)
        from gui.noark5_multi_overview_a65 import available_jobs
        jobs=available_jobs(base)
        assert len(jobs)==28
        assert jobs[0]=='JOB-001' and jobs[-1]=='JOB-028'
