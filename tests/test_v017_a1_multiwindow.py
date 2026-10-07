from __future__ import annotations

import unittest
from types import SimpleNamespace

from gui.jobs_window_v017_a1 import V017A1JobsWindow
from gui.persistent_app_v017_a1 import WorkflowApp, _v017_job_display_name
from gui.depot_result_center_v017_a1 import V017A1DepotResultCenterDialog
from gui.depot_result_center_a16_16 import DepotResultCenterDialogA16_16
from gui.depot_result_center_a19_5 import DepotResultCenterDialogA19_5


class _FakeJobsWindow:
    def __init__(self):
        self.opened = []
        self.refreshed = 0

    def on_open_job(self, job):
        self.opened.append(job)

    def winfo_exists(self):
        return True

    def refresh(self):
        self.refreshed += 1


class _FakeApp:
    def __init__(self, dialog):
        self._v017_depot_result_windows = {"JOB-002": dialog, "JOB-003": object()}
        self._depot_assessment_dialog = dialog


class V017A1MultiWindowTests(unittest.TestCase):
    def test_job_open_keeps_jobs_window_alive_and_refreshes(self):
        fake = _FakeJobsWindow()
        job = object()
        V017A1JobsWindow._open(fake, job)
        self.assertEqual(fake.opened, [job])
        self.assertEqual(fake.refreshed, 1)

    def test_closing_one_result_window_keeps_other_job_window_registered(self):
        dialog = object()
        fake = _FakeApp(dialog)
        event = SimpleNamespace(widget=dialog)
        WorkflowApp._v017_depot_result_closed(fake, event, dialog, "JOB-002")
        self.assertNotIn("JOB-002", fake._v017_depot_result_windows)
        self.assertIn("JOB-003", fake._v017_depot_result_windows)
        self.assertIsNone(fake._depot_assessment_dialog)


    def test_display_name_prefers_label_and_falls_back_to_source_folder(self):
        import gui.persistent_app_v017_a1 as module

        original = module.job_display_name
        try:
            job = SimpleNamespace(
                job_id="JOB-003",
                name="mofb-technical",
                source_root=r"G:\arkiv-noark5\1502\1502_025_ephorte-mofb_noark5",
            )
            module.job_display_name = lambda _job: "1502_025 ePhorte mofb (2008-2019)"
            self.assertEqual(
                _v017_job_display_name(job),
                "1502_025 ePhorte mofb (2008-2019)",
            )

            module.job_display_name = lambda _job: job.name
            self.assertEqual(
                _v017_job_display_name(job),
                "1502_025_ephorte-mofb_noark5",
            )
        finally:
            module.job_display_name = original

    def test_result_window_receives_and_displays_job_identity(self):
        import inspect
        app_source = inspect.getsource(WorkflowApp._open_depot_assessment)
        dialog_init_source = inspect.getsource(V017A1DepotResultCenterDialog.__init__)
        dialog_title_source = inspect.getsource(V017A1DepotResultCenterDialog._apply_v017_identity_title)
        nav_source = inspect.getsource(WorkflowApp._install_active_job_navigation)

        self.assertIn("display_name=display_name", app_source)
        self.assertIn("Resultatvisninger – Noark 5 –", dialog_title_source)
        self.assertIn("<Map>", dialog_init_source)
        self.assertIn("UTTREKK:", dialog_init_source)
        # Active-job identity now lives in the compact top-row navigation strip;
        # the old temporary second header row is intentionally gone.
        self.assertIn("_v017_active_job_display_label", nav_source)
        self.assertIn("row=0, column=3", nav_source)


    def test_result_window_restores_a19_5_period_bar_profiles(self):
        self.assertTrue(issubclass(V017A1DepotResultCenterDialog, DepotResultCenterDialogA19_5))
        import inspect
        source = inspect.getsource(__import__("gui.depot_result_center_a19_5", fromlist=["*"]).DepotResultCenterDialogA19_5)
        self.assertIn("_a194_replace_period_sparklines", source)
        self.assertIn("tk.Canvas", source)
        self.assertIn("canvas.create_rectangle", source)

    def test_result_dialog_skips_a1616_period_layer_until_period_vars_exist(self):
        calls = []

        class Parent:
            def _show_archive_part(self, index):
                calls.append(("parent", index))

        # Exercise the guard without constructing Tk widgets: emulate the
        # historical MRO call that occurs while a16.16 is still initializing.
        class Probe(V017A1DepotResultCenterDialog, Parent):
            pass

        probe = object.__new__(Probe)
        probe._a1616_start_var = None
        probe._a1616_end_var = None

        # The implementation must not call DepotResultCenterDialogA16_16's
        # _show_archive_part while those vars are None.  Structural source
        # verification keeps this regression test headless on Windows CI.
        import inspect
        source = inspect.getsource(V017A1DepotResultCenterDialog._show_archive_part)
        self.assertIn('getattr(self, "_a1616_start_var", None)', source)
        self.assertIn('super(DepotResultCenterDialogA16_16, self)._show_archive_part(index)', source)

    def test_major_work_windows_remember_position_without_touching_small_dialogs(self):
        import inspect
        from gui.depot_metadata_editor_v017_a1 import DepotMetadataEditor
        from gui.work_window_state_v017_a1 import install_work_window_state

        jobs_source = inspect.getsource(V017A1JobsWindow.__init__)
        result_source = inspect.getsource(V017A1DepotResultCenterDialog.__init__)
        metadata_source = inspect.getsource(DepotMetadataEditor.__init__)
        helper_source = inspect.getsource(install_work_window_state)

        self.assertIn("install_work_window_state", jobs_source)
        self.assertIn("install_work_window_state", result_source)
        self.assertIn("install_work_window_state", metadata_source)
        self.assertIn("<Configure>", helper_source)
        self.assertIn("work_window_states_v017_a1", inspect.getsource(__import__("gui.work_window_state_v017_a1", fromlist=["*"])))

    def test_job_window_titles_use_human_facing_identity(self):
        import inspect
        from gui.depot_metadata_editor_v017_a1 import DepotMetadataEditor

        metadata_source = inspect.getsource(DepotMetadataEditor.__init__)
        result_source = inspect.getsource(V017A1DepotResultCenterDialog._apply_v017_identity_title)
        self.assertIn("Rediger metadata –", metadata_source)
        self.assertIn("Resultatvisninger – Noark 5 –", result_source)

    def test_info_panel_visibility_is_persistent(self):
        import inspect
        restore_source = inspect.getsource(WorkflowApp._v017_restore_info_panel_state)
        shutdown_source = inspect.getsource(WorkflowApp._v017_persist_info_panel_actual_state)
        close_source = inspect.getsource(WorkflowApp._close_with_persistence)
        self.assertIn("info_panel_visible", restore_source)
        self.assertIn("panel.on_close = close_and_persist", restore_source)
        self.assertIn("<Map>", restore_source)
        self.assertIn("winfo_ismapped", shutdown_source)
        self.assertIn("_v017_persist_info_panel_actual_state", close_source)
        self.assertNotIn("<Unmap>", restore_source)

    def test_job_row_action_order_is_locked(self):
        import inspect
        source = inspect.getsource(V017A1JobsWindow._row)
        self.assertIn('("open", "mapper", "standard", "reset", "delete")', source)

    def test_job_open_does_not_withdraw_persistent_job_list(self):
        import inspect
        source = inspect.getsource(V017A1JobsWindow._open)
        self.assertIn("self.on_open_job(job)", source)
        self.assertNotIn("self.withdraw()", source)
        self.assertNotIn("self.destroy()", source)

    def test_job_list_open_state_is_restored_across_app_restart(self):
        import inspect
        init_source = inspect.getsource(WorkflowApp.__init__)
        restore_source = inspect.getsource(WorkflowApp._v017_restore_job_list_window)
        open_source = inspect.getsource(WorkflowApp._open_jobs)
        close_source = inspect.getsource(V017A1JobsWindow._v017_close_jobs_window)
        self.assertIn("_v017_restore_job_list_window", init_source)
        self.assertIn("job_list_window_open", restore_source)
        self.assertIn("_v017_remember_jobs_window_open", open_source)
        self.assertIn('save_config({"job_list_window_open": False})', close_source)

    def test_main_window_title_follows_active_job_label_without_duplicate_header_label(self):
        import inspect
        source = inspect.getsource(WorkflowApp._refresh_active_job_label)
        self.assertIn('self.title(f"{APP_NAME} v{VERSION} – {display_name}")', source)
        self.assertIn('f"AKTIV JOBB: {position_text} | {self.current_job.job_id} | {workflow_text}"', source)
        self.assertNotIn('f"{display_name} | {workflow_text}"', source)

    def test_info_close_persists_direct_user_intent(self):
        import inspect
        source = inspect.getsource(WorkflowApp._v017_restore_info_panel_state)
        self.assertIn("panel.on_close = close_and_persist", source)
        self.assertIn("persist(False)", source)
        self.assertIn('panel.bind("<Map>"', source)
        self.assertIn('if not startup["settled"]', source)
        self.assertNotIn('panel.bind("<Unmap>"', source)

    def test_major_window_state_blocks_generic_parent_recentering(self):
        import inspect
        from gui.work_window_state_v017_a1 import install_work_window_state
        source = inspect.getsource(install_work_window_state)
        self.assertIn("_n5wf_parent_positioned", source)


    def test_job_list_title_includes_app_version(self):
        import inspect
        source = inspect.getsource(V017A1JobsWindow.__init__)
        self.assertIn('self.title(f"Jobber - {APP_NAME} v{VERSION}")', source)

    def test_job_list_startup_restore_is_not_scheduled_inside_ctk_after_loop(self):
        import inspect
        source = inspect.getsource(WorkflowApp.__init__)
        self.assertIn("self._v017_restore_job_list_window()", source)
        self.assertNotIn("after_idle(self._v017_restore_job_list_window)", source)

    def test_major_window_geometry_is_clamped_to_monitor_work_area(self):
        import inspect
        import gui.work_window_state_v017_a1 as state_module
        restore_source = inspect.getsource(state_module.install_work_window_state)
        fit_source = inspect.getsource(state_module._fit_to_work_area)
        monitor_source = inspect.getsource(state_module._monitor_work_area)
        self.assertIn("_fit_to_work_area", restore_source)
        self.assertIn("max_height", fit_source)
        self.assertIn("MonitorFromRect", monitor_source)
        self.assertIn("rcWork", monitor_source)

    def test_main_log_actions_keep_depot_assessment_before_raw_results(self):
        import inspect
        source = inspect.getsource(WorkflowApp._v017_arrange_log_actions)
        self.assertIn('("Depotvurdering", 1)', source)
        self.assertIn('("Råresultater", 2)', source)

    def test_active_job_header_has_previous_next_navigation(self):
        import inspect
        install_source = inspect.getsource(WorkflowApp._install_active_job_navigation)
        step_source = inspect.getsource(WorkflowApp._v017_step_active_job)
        state_source = inspect.getsource(WorkflowApp._v017_update_job_navigation_state)
        self.assertIn('text="◀"', install_source)
        self.assertIn('text="▶"', install_source)
        self.assertIn('row=0, column=3', install_source)
        self.assertIn('_v017_active_job_display_label', install_source)
        self.assertIn('(index + int(delta)) % len(jobs)', step_source)
        self.assertIn('self._open_job(jobs[target_index])', step_source)
        self.assertIn('total > 1', state_source)

    def test_result_open_does_not_lower_or_minimize_main_window(self):
        import inspect
        source = inspect.getsource(WorkflowApp._open_depot_assessment)
        self.assertIn('present_native_work_window', source)
        self.assertNotIn('release_parent_work_window', source)
        self.assertNotIn('present_child_over_parent', source)

    def test_result_windows_have_comparison_friendly_size_cap(self):
        import inspect
        source = inspect.getsource(V017A1DepotResultCenterDialog.__init__)
        self.assertIn('self.geometry("1180x720")', source)
        self.assertIn('max_height_fraction=0.82', source)


if __name__ == "__main__":
    unittest.main()
