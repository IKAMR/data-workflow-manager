import tempfile
import unittest
from pathlib import Path
from app.recovery_v027_a19 import arkade_log_has_error
from app.job_run_actions_v024_a2 import resume_option

class A19RecoveryTests(unittest.TestCase):
    def test_legacy_cancel(self):
        self.assertTrue(resume_option(status='Hoppet over', cursor=3, total=14, message='Avbrutt under XPath').allowed)
        self.assertFalse(resume_option(status='Hoppet over', cursor=3, total=14, message='Ingen operasjoner').allowed)
    def test_interrupted(self):
        self.assertTrue(resume_option(status='Avbrutt', cursor=0, total=14).allowed)
    def test_arkade_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)/'stdout.txt'
            p.write_text('[Error] Access denied\n[Warning] finished with errors', encoding='utf-8')
            self.assertTrue(arkade_log_has_error(p))
            p.write_text('[Warning] Could not get latest version\n[Information] successfully finished', encoding='utf-8')
            self.assertFalse(arkade_log_has_error(p))
