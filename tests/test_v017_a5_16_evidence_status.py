import unittest
from noark5_workflow.external_evidence.evidence_status_a5 import coverage_summary
from noark5_workflow.external_evidence.archive_part_evidence_a5 import part_evidence_lines

class EvidenceStatusTest(unittest.TestCase):
    def test_unknown_not_claimed_as_agreement(self):
        annex={'records':[{'dwm_comparison':'unknown','external_comparison':'agreement','status':'missing'},
                          {'dwm_comparison':'conflict','external_comparison':'conflict','status':'external_evidence_selected'}]}
        message=coverage_summary(annex)
        self.assertIn('1 ikke sammenlignbare',message)
        self.assertIn('1 avvik',message)
        self.assertIn('1 motstridende',message)
        self.assertIn('1 valgte eksterne verdier',message)
    def test_available_not_selected(self):
        annex={'records':[{'archive_part_index':43,'metric_id':'folder_count','dwm_value':None,
                           'external_candidates':[{'value':2188,'report_type':'u02'}],
                           'external_comparison':'agreement','dwm_comparison':'unknown','status':'missing'}]}
        message='\n'.join(part_evidence_lines(annex,43))
        self.assertIn('2 188',message)
        self.assertIn('Valgt Ingen',message)
        self.assertIn('Kan ikke sammenlignes',message)
    def test_zero_is_known_value(self):
        annex={'records':[{'archive_part_index':43,'metric_id':'journalpost_count','dwm_value':0,
                           'external_unique_values':[0], 'status':'dwm', 'dwm_comparison':'agreement'}]}
        self.assertIn('DWM 0', '\n'.join(part_evidence_lines(annex,43)))

if __name__ == '__main__': unittest.main()
