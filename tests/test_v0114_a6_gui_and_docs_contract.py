"""No Qt required: guard the a6 integration and durable architecture documentation."""
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]

class A6IntegrationContract(unittest.TestCase):
    def test_result_dialog_shows_current_then_historical_and_has_work_save(self):
        code=(ROOT/'gui_qt/standard_values_v0114_a2.py').read_text(encoding='utf-8')
        self.assertIn('comparison_rows(ref[\'metadata_id\'], evidence.version, item.extra)',code)
        self.assertIn("'5.0': 0, '4.0': 1, '3.1': 2",code)
        self.assertIn('Lagre XSD-evidens i Work',code)
        self.assertIn('save_xsd_evidence(self._evidence, work)',code)
        self.assertIn('work_from_report(self._report_path)',code)
        self.assertIn('Referanse-XSD',code)

    def test_documentation_and_main_readme_link(self):
        readme=(ROOT/'README.md').read_text(encoding='utf8')
        roadmap=(ROOT/'docs/NOARK5-CANONICAL-RESULTS-AND-KNOWLEDGE-ROADMAP.md').read_text(encoding='utf8')
        for word in ('godkjenning/bevaring','sammenligning av flere','arkivskaper','arkiveier'):
            self.assertIn(word.lower(),(readme+roadmap).lower())
        self.assertIn('NOARK5-CANONICAL-RESULTS-AND-KNOWLEDGE-ROADMAP.md',readme)
        self.assertIn('IKAMR/digital-archive-workflow',roadmap)
        self.assertIn('NOARK-XSD-VERSION-DETECTION.md',readme)

if __name__ == '__main__':unittest.main()
