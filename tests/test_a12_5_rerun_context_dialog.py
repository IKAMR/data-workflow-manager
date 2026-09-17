from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = (ROOT / "gui" / "persistent_app_a21.py").read_text(encoding="utf-8")


class A125RerunContextDialogTests(unittest.TestCase):
    def test_dialog_has_per_job_context(self):
        self.assertIn("def _rerun_context_for_job", RUNTIME)
        self.assertIn("Følgende kjøring er planlagt", RUNTIME)
        self.assertIn("Tidligere fullført: operasjon 1-", RUNTIME)
        self.assertIn("Kjøres nå: operasjon", RUNTIME)

    def test_failed_tail_retry_is_named_explicitly(self):
        self.assertIn("Prøver igjen fra operasjon", RUNTIME)
        self.assertIn("Fortsettelse feilet - prøv igjen fra operasjon ", RUNTIME)

    def test_append_resume_is_named_explicitly(self):
        self.assertIn("Fortsetter fra operasjon", RUNTIME)
        self.assertIn("append_resume", RUNTIME)

    def test_checkpoint_resume_is_distinct(self):
        self.assertIn("Fortsetter fra kontrollpunkt ved operasjon", RUNTIME)
        self.assertIn("checkpoint_resume", RUNTIME)

    def test_full_rerun_is_distinct(self):
        self.assertIn("Kjøres på nytt fra operasjon 1 av", RUNTIME)

    def test_previous_results_are_preserved(self):
        self.assertIn("Tidligere resultatmapper slettes ikke", RUNTIME)
        self.assertIn("ny hendelse", RUNTIME)


if __name__ == "__main__":
    unittest.main()
