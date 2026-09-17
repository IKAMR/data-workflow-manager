import tempfile
import unittest

from app.run_overview_log import RunOverviewLog

ROOT = __import__("pathlib").Path(__file__).resolve().parents[1]

class BatchPhasesA2155Tests(unittest.TestCase):
    def test_run_log_persists_phase(self):
        with tempfile.TemporaryDirectory() as temp:
            log=RunOverviewLog({"temp_dir":temp,"run_log_dir":""},run_type="batch",app_version="0.1.2-a2",planned_jobs=2)
            log.set_phase("Worker startet"); self.assertIn("Fase: Worker startet",log.path.read_text(encoding="utf-8"))
    def test_runtime_has_explicit_pre_job_phases(self):
        text=(ROOT/"gui"/"persistent_app_a2155.py").read_text(encoding="utf-8")
        for phrase in ("Worker startet","Forbereder","Registrerer","Kjører","Avslutter batch"): self.assertIn(phrase,text)
    def test_runtime_has_nonblocking_startup_watchdog(self):
        text=(ROOT/"gui"/"persistent_app_a2155.py").read_text(encoding="utf-8")
        for phrase in ("startup_watchdog","first_job_registered","worker_started","BATCH STARTUP-FEIL","self.batch_running = False"): self.assertIn(phrase,text)
    def test_current_runtime_preserves_a2155_chain(self):
        main=(ROOT/"main.py").read_text(encoding="utf-8")
        a21=(ROOT/"gui"/"persistent_app_a21.py").read_text(encoding="utf-8")
        a20=(ROOT/"gui"/"persistent_app_a20.py").read_text(encoding="utf-8")
        a19=(ROOT/"gui"/"persistent_app_a19.py").read_text(encoding="utf-8")
        a18=(ROOT/"gui"/"persistent_app_a18.py").read_text(encoding="utf-8")
        a17=(ROOT/"gui"/"persistent_app_a17.py").read_text(encoding="utf-8")
        a13=(ROOT/"gui"/"persistent_app_a13.py").read_text(encoding="utf-8")
        a6=(ROOT/"gui"/"persistent_app_a6.py").read_text(encoding="utf-8")
        a5=(ROOT/"gui"/"persistent_app_a5.py").read_text(encoding="utf-8")
        self.assertIn("persistent_app_a21",main)
        self.assertIn("A20WorkflowApp",a21)
        self.assertIn("A19WorkflowApp",a20)
        self.assertIn("A18WorkflowApp",a19)
        self.assertIn("A17WorkflowApp",a18)
        self.assertIn("A13WorkflowApp",a17)
        self.assertIn("persistent_app_a6",a13)
        self.assertIn("A5WorkflowApp",a6)
        self.assertIn("A2155WorkflowApp",a5)

if __name__ == "__main__": unittest.main()
