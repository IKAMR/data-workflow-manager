"""DWM v0.2.2-a6: stable Qt shell with QA and per-job workflow ordering.

No new startup timers, global event filters or workflow runner changes.
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QPushButton

from gui_qt.basic_main_v0113_a2 import DwmMainWindow as _ExistingMainWindow


class DwmMainWindow(_ExistingMainWindow):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._a3_install_qa_shortcuts()
        self._a6_install_workflow_order()
        self._a7_install_postprocessing()
        self._a8_install_run_profiles()

    def _a3_install_qa_shortcuts(self):
        """No new top-level windows at startup and no Qt event filters."""
        self.a3_qa_action = QAction("Avvik, kvalitetssikring og godkjenning…", self)
        self.a3_qa_action.setToolTip(
            "Dokumenter kildefunn; lag kvalitetssikrings- og godkjenningsrapporter som utkast")
        self.a3_qa_action.triggered.connect(self._a3_open_qa)
        # Visible only when the existing Advanced menu bar is visible.
        menu = next((action.menu() for action in self.menuBar().actions()
                     if action.menu() is not None
                     and action.text().replace("&", "").strip() == "Rapport"), None)
        if menu is not None:
            menu.insertAction(self.report_selected_action, self.a3_qa_action)
        # Simple mode hides the native menu. Put the same action in its own
        # existing Overview, not in a second hidden workflow/joblist.
        overview = getattr(self, "_a2_overview_page", None)
        start = getattr(self, "_a2_overview_start", None)
        if overview is not None and start is not None and overview.layout() is not None:
            self.a3_basic_qa_button = QPushButton("Avvik / KS / godkjenning…", overview)
            self.a3_basic_qa_button.setToolTip(
                "Tilgjengelig for ferdig kontrollerte jobber med en lagret depotrapport")
            self.a3_basic_qa_button.clicked.connect(self._a3_open_qa)
            layout = overview.layout()
            index = layout.indexOf(start)
            layout.insertWidget(index if index >= 0 else layout.count(),
                                self.a3_basic_qa_button, 0, Qt.AlignmentFlag.AlignRight)

    def _a6_install_workflow_order(self):
        """Add a per-job editor to the existing two modes, without a new store."""
        self.a6_order_action = QAction('Endre rekkefølge på deljobber…', self)
        self.a6_order_action.setToolTip(
            'Bestem rekkefølgen for valgt jobb; lagres i den samme .n5jobs/Work-jobben')
        self.a6_order_action.triggered.connect(self._a6_change_order)
        run_menu = next((action.menu() for action in self.menuBar().actions()
                         if action.menu() is not None
                         and action.text().replace('&', '').strip() == 'Kjør'), None)
        if run_menu is not None:
            run_menu.addSeparator()
            run_menu.addAction(self.a6_order_action)

        # Advanced: own row in the existing workflow dock, not a fourth tiny
        # button squeezing the existing preset/checkpoint toolbar.
        preset = getattr(self, 'workflow_preset_button', None)
        if preset is not None:
            parent = preset.parentWidget()
            layout = parent.layout() if parent is not None else None
            if layout is not None:
                position = next((i for i in range(layout.count())
                                 if layout.itemAt(i).layout() is not None
                                 and layout.itemAt(i).layout().indexOf(preset) >= 0), -1)
                if position >= 0:
                    self.a6_workflow_order_button = QPushButton('Endre rekkefølge…', parent)
                    self.a6_workflow_order_button.setToolTip(self.a6_order_action.toolTip())
                    self.a6_workflow_order_button.clicked.connect(self._a6_change_order)
                    layout.insertWidget(position + 1, self.a6_workflow_order_button)

        # Basic hides the menu bar. Keep its action alongside control selection
        # in step 3; both modes edit the same per-job workflow IDs.
        run_group = getattr(self, '_a2_step_groups', {}).get('run')
        if run_group is not None and run_group.layout() is not None:
            self.a6_basic_order_button = QPushButton('Endre rekkefølge på deljobber…', run_group)
            self.a6_basic_order_button.setToolTip(self.a6_order_action.toolTip())
            self.a6_basic_order_button.clicked.connect(self._a6_change_order)
            layout = run_group.layout()
            layout.insertWidget(min(1, layout.count()), self.a6_basic_order_button,
                                0, Qt.AlignmentFlag.AlignLeft)

    def _a6_change_order(self, *_args):
        from gui_qt.workflow_order_v022_a6 import open_active_job_order
        return open_active_job_order(self)

    def _a7_install_postprocessing(self):
        self.a7_prepare_action = QAction('Legg til a7-etterbehandling...', self)
        self.a7_prepare_action.setToolTip(
            'Utvid en eksisterende fullfort Work-jobb med kanonisk evidens, '
            'kildeanalyse, evidensrevisjon og KS-utkast uten ny teknisk testkjoring')
        self.a7_prepare_action.triggered.connect(self._a7_prepare_postprocessing)
        run_menu = next((action.menu() for action in self.menuBar().actions()
                         if action.menu() is not None
                         and action.text().replace('&', '').strip() == 'Kjør'), None)
        if run_menu is not None:
            run_menu.addAction(self.a7_prepare_action)
        group = getattr(self,'_a2_step_groups',{}).get('run')
        if group is not None and group.layout() is not None:
            self.a7_prepare_button = QPushButton('Legg til a7-etterbehandling...', group)
            self.a7_prepare_button.clicked.connect(self._a7_prepare_postprocessing)
            group.layout().insertWidget(min(2,group.layout().count()),self.a7_prepare_button,
                                        0,Qt.AlignmentFlag.AlignLeft)

    def _a7_prepare_postprocessing(self, *_args):
        from PySide6.QtWidgets import QMessageBox
        if self._worker is not None or self.api.running:
            QMessageBox.warning(self,'a7-etterbehandling','Avslutt kjøringen først.')
            return False
        if getattr(self,'_basic_active',False):
            register=getattr(self,'_v022_register_current',None)
            if callable(register) and not register():
                return False
        if not self._active_id:
            QMessageBox.information(self,'a7-etterbehandling','Velg en jobb først.')
            return False
        decision=QMessageBox.question(
            self,'a7-etterbehandling - '+self._active_id,
            'Legg til evidens, eksterne kilder, kontroll av evidensdekning '
            'og KS-utkast for denne Work-jobben?\n\n'
            'En allerede fullført teknisk kjøring bevares. '
            'Status blir Klar for etterbehandling og tidligere rapporter slettes ikke.\n\n'
            'Dette gjelder bare valgt JOB. Fortsette?',
            QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No)
        if decision != QMessageBox.StandardButton.Yes:
            return False
        try:
            self.api.prepare_a7_postprocessing(self._active_id)
            if self.api.workspace().job_list_path:
                self.api.save_job_list()
            self._render_key=None
            self._refresh(force=True)
            QMessageBox.information(self,'a7 klargjort',
                'Tekniske deljobber gjenbrukes. Start kjøringen for kun '
                'etterbehandling i oppdatert arbeidsflyt.')
            return True
        except (OSError,ValueError,RuntimeError) as exc:
            QMessageBox.warning(self,'a7-etterbehandling',str(exc))
            return False

    def _refresh(self, *args, **kwargs):
        result = super()._refresh(*args, **kwargs)
        tree = getattr(self, 'workflow_tree', None)
        if tree is not None:
            from app.workflow_dependencies_v022_a7 import (
                dependency_label, dependency_links,
            )
            ids = tuple(str(tree.topLevelItem(i).data(0, Qt.ItemDataRole.UserRole))
                        for i in range(tree.topLevelItemCount()))
            for index, oid in enumerate(ids):
                item = tree.topLevelItem(index)
                number = dependency_label(oid)
                prefix = '[' + number + '] '
                if not item.text(1).startswith(prefix):
                    item.setText(1, prefix + item.text(1))
                prerequisites = ', '.join(dependency_links(oid, ids)) or 'Ingen'
                item.setToolTip(1, f'Avhengighetsnr. {number}\nOperasjon: {oid}\nEtter: {prerequisites}')
        return result

    def _a8_install_run_profiles(self):
        """One editor for both modes; no hidden secondary execution state."""
        self.a8_profiles_action = QAction('Kjøreprofiler…', self)
        self.a8_profiles_action.setToolTip(
            'Velg Standard DWM, Avansert DWM eller Komplett, og velg Arkade-testene uavhengig')
        self.a8_profiles_action.triggered.connect(self._a8_choose_run_profile)
        menu = next((action.menu() for action in self.menuBar().actions()
                     if action.menu() is not None
                     and action.text().replace('&', '').strip() == 'Kjør'), None)
        if menu is not None:
            menu.addAction(self.a8_profiles_action)
        group = getattr(self, '_a2_step_groups', {}).get('run')
        if group is not None and group.layout() is not None:
            self.a8_basic_profiles_button = QPushButton('Kjøreprofil…', group)
            self.a8_basic_profiles_button.setToolTip(self.a8_profiles_action.toolTip())
            self.a8_basic_profiles_button.clicked.connect(self._a8_choose_run_profile)
            group.layout().insertWidget(0, self.a8_basic_profiles_button,
                                        0, Qt.AlignmentFlag.AlignLeft)
        # Only an untouched Basic installation receives the user's configured
        # default. Existing explicit checkbox preferences are never reset.
        checks = getattr(self, 'basic_option_checks', {})
        if checks and not self.config.contains('qt/v0111_basic_options'):
            from app.run_profiles_v022_a8 import selected_default
            ids = set(selected_default(self.api.settings).operation_ids)
            mapping = {'dwm': 'run_noark5_xpath_tests_2026',
                       'siegfried': 'siegfried_pronom_identification',
                       'arkade_noark5': 'arkade5_noark5_test',
                       'arkade_pronom': 'arkade5_pronom_analysis'}
            self._setting_basic_workflow = True
            try:
                for key, checkbox in checks.items():
                    checkbox.setChecked(mapping.get(key) in ids)
            finally:
                self._setting_basic_workflow = False

    def _a8_choose_run_profile(self, *_args):
        from gui_qt.run_profiles_v022_a8 import open_run_profile_dialog
        return open_run_profile_dialog(self)

    def _a3_open_qa(self, *_args):
        from gui_qt.qa_workflow_v022_a3 import open_active_job_qa
        open_active_job_qa(self)

    def _a12_open_result_center(self, *args, **kwargs):
        existing = tuple(getattr(self, "_a12_result_windows", ()))
        outcome = super()._a12_open_result_center(*args, **kwargs)
        from gui_qt.result_navigation_v020_a6 import install_compact_result_navigation
        from gui_qt.noark5_xpath_audit_v021_a1 import install_xpath_catalog_link
        from gui_qt.qa_workflow_v022_a3 import install_qa_review_panel
        from gui_qt.checklist_v021_a15 import install_depot_checklist
        for viewer in getattr(self, "_a12_result_windows", ()):
            if viewer not in existing:
                install_compact_result_navigation(viewer)
                install_xpath_catalog_link(viewer)
                install_qa_review_panel(viewer)
                install_depot_checklist(viewer)
        return outcome
