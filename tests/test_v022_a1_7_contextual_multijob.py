"""v0.2.2-a1.7 – Introduce multi-job actions only after first extraction.

Qt-independent UI regression tests using the real extension class with fake
widgets. The shared job API and saved .n5jobs are covered by a1.2 tests.
"""
from __future__ import annotations

from pathlib import Path
import unittest

from app.basic_multijob_v022_a1_2 import (
    basic_extraction_status, basic_selector_visible,
)
import test_v022_a1_6_source_first as fixture


class PresentationPolicyTests(unittest.TestCase):
    def test_zero_jobs_has_no_batch_ui_on_any_step(self):
        for step in ('source', 'work', 'run', 'overview'):
            self.assertFalse(basic_selector_visible(0, step, new_draft=True))

    def test_first_job_does_not_show_multi_job_bar_during_source_or_work(self):
        for step in ('source', 'work'):
            self.assertFalse(basic_selector_visible(1, step))
        for step in ('run', 'overview'):
            self.assertTrue(basic_selector_visible(1, step))

    def test_existing_jobs_with_second_draft_must_remain_accessible(self):
        for step in ('source', 'work', 'run', 'overview'):
            self.assertTrue(basic_selector_visible(1, step, new_draft=True))
            self.assertTrue(basic_selector_visible(2, step))
            self.assertTrue(basic_selector_visible(3, step))

    def test_registration_status_is_not_file_save_status(self):
        self.assertEqual(basic_extraction_status('Klar'), 'Registrert, ikke kjørt')
        self.assertEqual(basic_extraction_status('Klar', progress=.4), 'Klar for ny kjøring')
        self.assertEqual(basic_extraction_status('Klar', current_operation=2), 'Klar for ny kjøring')
        self.assertEqual(basic_extraction_status('Ferdig'), 'Kontroll fullført')
        self.assertEqual(basic_extraction_status('Kjører'), 'Kontroll pågår')
        self.assertEqual(basic_extraction_status('Feil'), 'Kontroll feilet')
        self.assertEqual(basic_extraction_status('Hoppet over'), 'Kontroll hoppet over')
        self.assertEqual(basic_extraction_status('Venter ved kontrollpunkt'),
                         'Venter ved kontrollpunkt')
        self.assertEqual(basic_extraction_status('Frakoblet (sist: Ferdig)'),
                         'Frakoblet (sist: Ferdig)')


class ContextualQtFakeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.window_class = fixture.load_gui_class()

    def window(self):
        legacy = fixture.SourceFirstTests()
        legacy.window_class = self.window_class
        return legacy.window()

    def prepared(self, count=1, stage='source', status='Klar', path=None):
        w = self.window()
        w.api.jobs = [(f'JOB-{i:03}', f'uttrekk-{i}') for i in range(1, count + 1)]
        w.api.statuses = {f'JOB-{i:03}': status for i in range(1, count + 1)}
        w.api.path = path
        w._v022_draft = False
        w._active_id = 'JOB-001' if count else None
        w._a2_current_step = stage
        return w

    def test_first_job_hidden_on_source_and_work_but_show_on_next_click(self):
        w = self.prepared(stage='work')
        w._v022_refresh_selector()
        self.assertFalse(w.v022_selector_group.visible)
        self.assertEqual(w.v022_registration_status.text(),
                         'Status: Registrert, ikke kjørt.')
        self.assertIn('Ikke lagret til fil', w.v022_joblist_status.text())
        w._a2_set_step('run')
        self.assertTrue(w.v022_selector_group.visible)
        self.assertTrue(w.v022_current_job_label.visible)
        self.assertFalse(w.v022_job_selector.visible)
        self.assertIn('Registrert, ikke kjørt', w.v022_registration_status.text())
        w._a2_set_step('work')
        self.assertFalse(w.v022_selector_group.visible)

    def test_first_job_offers_add_and_save_on_overview_without_running(self):
        w = self.prepared(stage='overview')
        w._v022_refresh_selector(force=True)
        self.assertTrue(w.v022_selector_group.visible)
        self.assertTrue(w.v022_new_job_button.enabled)
        self.assertTrue(w.v022_save_job_button.enabled)
        self.assertEqual(w.v022_current_job_label.text(),
                         'Aktivt uttrekk: JOB-001 · uttrekk-1')
        self.assertEqual(w.api.workspace().jobs[0].status, 'Klar')

    def test_two_jobs_can_be_selected_on_every_step(self):
        w = self.prepared(count=2, stage='source')
        w._v022_refresh_selector(force=True)
        self.assertTrue(w.v022_selector_group.visible)
        self.assertTrue(w.v022_job_selector.visible)
        self.assertEqual([id for _, id in w.v022_job_selector.entries],
                         ['JOB-001', 'JOB-002'])
        self.assertEqual(w.v022_job_selector.currentData(), 'JOB-001')
        w._a2_set_step('work')
        self.assertTrue(w.v022_selector_group.visible)
        w._a2_set_step('run')
        self.assertTrue(w.v022_selector_group.visible)

    def test_second_unregistered_draft_keeps_first_job_accessible(self):
        w = self.prepared(count=1, stage='source')
        w._v022_draft = True
        w._v022_refresh_selector(force=True)
        self.assertTrue(w.v022_selector_group.visible)
        self.assertEqual(w.v022_job_selector.currentData(), None)
        self.assertEqual([id for _, id in w.v022_job_selector.entries],
                         [None, 'JOB-001'])
        self.assertFalse(w.v022_new_job_button.enabled)
        self.assertIn('under registrering', w.v022_registration_status.text())

    def test_file_status_is_distinct_after_save_and_for_completed_job(self):
        w = self.prepared(stage='run', status='Ferdig', path=Path('/tmp/work/shared.n5jobs'))
        w._v022_refresh_selector()
        self.assertIn('Kontroll fullført', w.v022_registration_status.text())
        self.assertNotIn('ikke kjørt', w.v022_registration_status.text())
        self.assertIn('Lagret i shared.n5jobs', w.v022_joblist_status.text())
        self.assertNotIn('Kontroll fullført', w.v022_joblist_status.text())
        w._v022_save_failed = True
        w._v022_refresh_selector()
        self.assertIn('Lagring: Feilet', w.v022_joblist_status.text())
        self.assertIn('Kontroll fullført', w.v022_registration_status.text())

    def test_job_status_changes_without_picker_change_repaint_correctly(self):
        w = self.prepared(stage='run')
        w._v022_refresh_selector()
        self.assertIn('ikke kjørt', w.v022_registration_status.text())
        w.api.statuses['JOB-001'] = 'Kjører'
        w._v022_refresh_selector()  # no force: this is the 500 ms timer path
        self.assertIn('Kontroll pågår', w.v022_registration_status.text())
        w.api.statuses['JOB-001'] = 'Ferdig'
        w._v022_refresh_selector()
        self.assertIn('Kontroll fullført', w.v022_registration_status.text())

    def test_no_controls_disables_add_without_hiding_current_job(self):
        w = self.prepared(stage='run')
        w._selected_basic_controls = lambda: ()
        w._v022_refresh_selector()
        self.assertTrue(w.v022_selector_group.visible)
        self.assertFalse(w.v022_new_job_button.enabled)
        self.assertIn('Velg minst én kontroll', w.v022_new_job_button.tooltip)
        self.assertTrue(w.v022_save_job_button.enabled)

    def test_running_state_prevents_add_save_and_change_job(self):
        w = self.prepared(count=3, stage='source')
        w.api.running = True
        w._v022_refresh_selector()
        self.assertTrue(w.v022_selector_group.visible)
        self.assertFalse(w.v022_job_selector.enabled)
        self.assertFalse(w.v022_new_job_button.enabled)
        self.assertFalse(w.v022_save_job_button.enabled)


if __name__ == '__main__':
    unittest.main()
