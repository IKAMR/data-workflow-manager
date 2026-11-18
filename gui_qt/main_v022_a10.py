"""v0.2.2-a10: focused improvements over the a9 Qt multi-job window.

Presentation only: no new runner, no global Qt event filters, no automatic
rewrites of existing .n5jobs, Work or historic evidence records.
"""
from __future__ import annotations

from pathlib import Path

from app.run_display_v022_a10 import (
    ready_job_list, ready_label, readable_job_name, result_file_explanation,
)
from app.source_locator_v022_a10 import (
    find_source_candidates, picker_start, source_within_info_parent,
)
from gui_qt.basic_multijob_v022_a1_2 import DwmMainWindow as _PreviousWindow


class DwmMainWindow(_PreviousWindow):
    """A10 GUI additions use the same DWMWorkbenchAPI for both modes."""

    def restoreGeometry(self, geometry):
        """Do not submit obsolete, unbounded native window geometry to Qt.

        The older main window calls this during its settings restoration.
        We keep all the other settings and docks, while replacing that one
        unsafe call with a bounded restore from existing a14 window metadata.
        Other explicit restoreGeometry calls retain their normal behavior.
        """
        if getattr(self, '_a102_suppress_legacy_restore', False):
            return True
        return super().restoreGeometry(geometry)

    def _restore_settings(self):
        # Called by the established QMainWindow constructor. The native Qt
        # restore may request an oversized client area on mixed-DPI monitors.
        self._a102_suppress_legacy_restore = True
        try:
            result = super()._restore_settings()
        finally:
            self._a102_suppress_legacy_restore = False
        self._a102_restore_bounded_geometry()
        return result

    def _a102_restore_bounded_geometry(self):
        from PySide6.QtWidgets import QApplication
        from app.window_geometry_v022_a10_2 import (
            ScreenArea, WindowRect, bounded_window_rect,
        )
        try:
            valid = self.config.value('qt/a14_main_valid', False, type=bool)
            saved = WindowRect(*(int(self.config.value('qt/a14_main_' + part))
                                 for part in ('x', 'y', 'width', 'height')))
            if not valid or saved.width < 100 or saved.height < 100:
                return
        except (TypeError, ValueError):
            return
        screens = tuple(
            ScreenArea(screen.availableGeometry().x(),
                       screen.availableGeometry().y(),
                       screen.availableGeometry().width(),
                       screen.availableGeometry().height(), screen.name())
            for screen in QApplication.screens()
        )
        if not screens:
            return
        preferred = str(self.config.value('qt/a14_main_screen', '') or '')
        safe = bounded_window_rect(saved, screens, preferred_screen=preferred)
        self._a102_safe_main_rect = safe
        # A single bounded request avoids two competing native resize/move
        # operations. A subsequent a14 position controller should see the
        # same bounded normal geometry rather than the obsolete oversized one.
        current = self.geometry()
        if any(abs(a-b) > 4 for a,b in zip(
            (current.x(), current.y(), current.width(), current.height()),
            (safe.x, safe.y, safe.width, safe.height),
        )):
            self.setGeometry(safe.x, safe.y, safe.width, safe.height)

    def _a102_sync_position_controller(self):
        controller = getattr(self, '_a14_window_positions', None)
        safe = getattr(self, '_a102_safe_main_rect', None)
        if controller is not None and safe is not None:
            from gui_qt.window_positions_v0114_a1 import Rect
            controller._startup_rect = Rect(safe.x, safe.y, safe.width, safe.height)
            # The saved offset belongs to the old unbounded rectangle;
            # preserve the selected screen but use the bounded location.
            controller._startup_maximized = bool(self.config.value(
                'qt/a14_main_maximized', False, type=bool))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if hasattr(self, '_a14_window_positions'):
            self._a102_sync_position_controller()
        # Qt startup tests instantiate the shared window via a minimal stand-in
        # without widgets/docks.  Keep A10's GUI enhancements opt-in for that
        # stand-in, while the real window always has a constructed toolbar.
        if not hasattr(self, '_toolbar'):
            return
        self._a10_install_actions()
        self._a10_configure_columns()
        self._a10_refresh_labels()

    def _a10_install_actions(self):
        from PySide6.QtWidgets import QPushButton
        # The existing QAction is shared by the Kjor menu and the toolbar.
        # Adding it to a second container does not create a second runner.
        if not self._toolbar.actions().count(self.ready_action):
            self._toolbar.insertAction(self.continue_action, self.ready_action)
        self.ready_action.setToolTip(
            'Kj\u00f8r alle klare jobber i rekkef\u00f8lgen i .n5jobs. '
            'F\u00f8rkontroll og bekreftelse vises f\u00f8r start.')

        self.a10_autofit_action = self._preset_menu.addAction(
            'Autojuster arbeidsflate', self._a10_autofit)
        self.a10_autofit_action.setToolTip(
            'Gi mer plass til Kj\u00f8rel\u00f8p og gj\u00f8r venstre paneler lesbare. '
            'Endrer ikke en lagret brukerdefinert arbeidsflate.')
        group = getattr(self, '_a2_step_groups', {}).get('run')
        if group is not None and group.layout() is not None:
            self.a10_basic_all_button = QPushButton('Kj\u00f8r alle klare', group)
            self.a10_basic_all_button.setObjectName('a10_run_all_basic')
            self.a10_basic_all_button.setToolTip(
                'Bruker samme sekvensielle kj\u00f8ring som Avansert modus. '
                'Bekreft jobblisten f\u00f8r start.')
            self.a10_basic_all_button.clicked.connect(self._a10_run_all_basic)
            group.layout().addWidget(self.a10_basic_all_button)

    def _a10_configure_columns(self):
        from PySide6.QtCore import Qt
        from PySide6.QtWidgets import QHeaderView
        # Stretching a column disables the operator's manual drag resize.
        for tree, width in ((self.jobs_tree, 235), (self.workflow_tree, 275)):
            header = tree.header()
            header.setStretchLastSection(False)
            header.setSectionResizeMode(1, QHeaderView.ResizeMode.Interactive)
            header.setMinimumSectionSize(35)
            tree.setColumnWidth(1, width)
            tree.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self._a10_history_headers()

    def _a10_history_headers(self):
        from PySide6.QtWidgets import QHeaderView
        tree = getattr(self, 'run_history_tree', None)
        if tree is not None:
            if tree.columnCount() != 6:
                tree.setHeaderLabels([
                    'Tid', 'Deljobb', 'Kj\u00f8ring', 'Teknisk',
                    'Resultatfiler', 'Logg-advarsler'])
                tree.header().setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
                tree.header().setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
            tree.headerItem().setToolTip(4,
                'Antall registrerte filer, IKKE antall testfeil eller funn.')
            tree.headerItem().setToolTip(5,
                'Tekniske loggadvarsler, ikke alle faglige Arkade-/DWM-funn.')

    def _a10_refresh_labels(self):
        if not hasattr(self, 'api') or not hasattr(self, 'ready_action'):
            return
        jobs = self.api.workspace().jobs
        ready = ready_job_list(jobs)
        running = bool(getattr(self, '_worker', None) or self.api.running
                       or getattr(self, '_job_controls_running', False))
        self.ready_action.setText(ready_label(jobs))
        self.ready_action.setEnabled(bool(ready) and not running)
        button = getattr(self, 'a10_basic_all_button', None)
        if button is not None:
            button.setText(ready_label(jobs))
            button.setEnabled(bool(ready) and not running)
        # Full job names remain available even when the dock is narrow.
        for tree in (getattr(self, 'jobs_tree', None),
                     getattr(self, 'workflow_tree', None)):
            if tree is None:
                continue
            for index in range(tree.topLevelItemCount()):
                item = tree.topLevelItem(index)
                if tree is self.jobs_tree:
                    job = next((j for j in jobs if j.job_id == item.text(0)), None)
                    if job is not None:
                        item.setToolTip(1, str(job.name))
                else:
                    item.setToolTip(1, item.toolTip(1) + '\n' + item.text(1)
                                    if item.text(1) not in item.toolTip(1) else item.toolTip(1))

    def _refresh(self, *args, **kwargs):
        result = super()._refresh(*args, **kwargs)
        # _refresh is also called before the subclass constructor finishes.
        if hasattr(self, 'ready_action'):
            self._a10_refresh_labels()
        return result

    def _set_running_ui(self, running: bool):
        result = super()._set_running_ui(running)
        if hasattr(self, 'ready_action'):
            self._a10_refresh_labels()
        return result

    def _a11_refresh_operation_history(self):
        result = super()._a11_refresh_operation_history()
        if not hasattr(self, 'run_history_tree'):
            return result
        self._a10_history_headers()
        for index, event in enumerate(getattr(self, '_a11_history_cache', ())):
            if index >= self.run_history_tree.topLevelItemCount():
                break
            row = self.run_history_tree.topLevelItem(index)
            files = len(getattr(event, 'work_results', ()) or ())
            warnings = getattr(event, 'warning_count', 0)
            row.setText(5, str(warnings))
            row.setToolTip(4, result_file_explanation(files, warnings))
            row.setToolTip(5, f'{warnings} tekniske loggadvarsler. '
                           'Arkade- og Noark-funn m\u00e5 vurderes i resultatrapportene.')
        return result

    def _a9_sync_detached_run(self):
        result = super()._a9_sync_detached_run()
        viewer = getattr(self, '_detached_run_window', None)
        if viewer is not None and hasattr(viewer, 'history_tree'):
            viewer.history_tree.headerItem().setText(4, 'Resultatfiler')
            viewer.history_tree.headerItem().setToolTip(4,
                'Antall filer, ikke antall testfunn eller feil.')
            for i in range(viewer.history_tree.topLevelItemCount()):
                item = viewer.history_tree.topLevelItem(i)
                item.setToolTip(4, result_file_explanation(int(item.text(4) or 0)))
        return result

    def _a10_autofit(self):
        from PySide6.QtCore import Qt
        """Explicit one-shot geometry only; no startup timer or resize loop."""
        if not self.dock_log.isFloating() and self.dock_log.isVisible():
            target = max(400, min(730, int(self.height() * 0.57)))
            self.resizeDocks([self.dock_log], [target], Qt.Orientation.Vertical)
        if (self.dock_jobs.isVisible() and self.dock_workflow.isVisible()
                and not self.dock_jobs.isFloating() and not self.dock_workflow.isFloating()):
            self.resizeDocks([self.dock_jobs, self.dock_workflow],
                             [420, 420], Qt.Orientation.Horizontal)
        self._a10_configure_columns()
        self.statusBar().showMessage(
            'Arbeidsflaten er autojustert. Du kan fremdeles dra panel- og kolonnedelere.', 6000)

    def _run_ready(self):
        from PySide6.QtWidgets import QMessageBox
        """Existing batch engine with a concrete, job-by-job confirmation."""
        if (self._worker is not None or self.api.running
                or getattr(self, '_job_controls_running', False)):
            return
        ready = ready_job_list(self.api.workspace().jobs)
        if not ready:
            QMessageBox.information(self, 'Kj\u00f8r klare jobber',
                                    'Ingen klare jobber \u00e5 kj\u00f8re.')
            return
        targets = []
        descriptions = []
        for job in ready:
            rerun = self.api.job_details(job.job_id).message == (
                'Konfigurasjon endret - klar for ny kj\u00f8ring')
            targets.append((job.job_id, rerun, False))
            descriptions.append(f'{job.job_id}: {job.name}' +
                                (' (ny kj\u00f8ring)' if rerun else ''))
        visible = descriptions[:25]
        if len(descriptions) > len(visible):
            visible.append(f'... og {len(descriptions) - len(visible)} flere')
        answer = QMessageBox.question(
            self, 'Kj\u00f8r alle klare jobber',
            f'Starte {len(ready)} klare jobber sekvensielt i denne rekkef\u00f8lgen?\n\n'
            + '\n'.join(visible)
            + '\n\nF\u00f8rkontroll utf\u00f8res f\u00f8r start. '
            'Kj\u00f8ringen stopper ved f\u00f8rste tekniske feil. '
            '100 % betyr teknisk fullf\u00f8rt, ikke faglig godkjent.',
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer == QMessageBox.StandardButton.Yes:
            self._start_worker(targets)

    def _a10_run_all_basic(self, _checked=False):
        if (self._worker is not None or self.api.running
                or getattr(self, '_job_controls_running', False)):
            return
        # Register the selected Basic draft first, just like Start kontroll.
        if getattr(self, '_basic_active', False) and self._active_id:
            if not self._v022_register_current():
                return
        elif getattr(self, '_v022_draft', False):
            if not self._v022_register_current():
                return
        self._run_ready()

    def _choose_basic_source(self):
        from PySide6.QtWidgets import QFileDialog, QInputDialog, QMessageBox
        """Never jump to a previously used unrelated extraction on Finn."""
        if self._worker is not None or self.api.running:
            return
        info = (getattr(self, '_a2_original', None)
                if getattr(self, '_a3_manually_loaded_info', False) else None)
        suggested = ()
        if info is not None:
            from app.job_preflight_v018_a6 import check_extraction_folder
            suggested = find_source_candidates(
                info, validator=lambda candidate: not check_extraction_folder(
                    str(candidate), profile_id='noark5'))
        source = None
        if len(suggested) == 1:
            candidate = suggested[0]
            response = QMessageBox.question(
                self, 'Uttrekk funnet ved info.xml',
                'DWM fant ett gyldig uttrekk under mappen for info.xml:\n\n'
                + str(candidate)
                + '\n\nDette bekrefter ikke at metadataene beskriver samme uttrekk. '
                'Bruke dette som Source?',
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No)
            if response == QMessageBox.StandardButton.Yes:
                source = candidate
        elif len(suggested) > 1:
            choices = [str(p) for p in suggested] + ['Velg annen mappe ...']
            selection, ok = QInputDialog.getItem(
                self, 'Flere uttrekk ved info.xml',
                'Velg riktig Source (kontroller identiteten):', choices, 0, False)
            if not ok:
                return
            if selection != choices[-1]:
                source = Path(selection)
        if source is None:
            origin = picker_start(info, home=Path.home())
            selected = QFileDialog.getExistingDirectory(
                self, 'Velg Noark 5-uttrekksmappe (Source)', str(origin),
                QFileDialog.Option.ShowDirsOnly | QFileDialog.Option.DontUseNativeDialog)
            if not selected:
                return
            source = Path(selected)
        if info is not None and not source_within_info_parent(source, info):
            decision = QMessageBox.question(
                self, 'Kontroller Source og info.xml',
                'Source ligger ikke under mappen med importert info.xml.\n\n'
                'Info.xml: ' + str(info) + '\nSource: ' + str(source)
                + '\n\nBekreft at filen tilh\u00f8rer dette uttrekket. Fortsette?',
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No)
            if decision != QMessageBox.StandardButton.Yes:
                return
        self._a3_accept_source(source)  # The established full Source validator.

    def _v022_register_current(self, *, show_errors: bool = True) -> bool:
        from PySide6.QtWidgets import QMessageBox
        """Give NEW jobs useful names, without changing existing saved jobs."""
        previous_ids = {job.job_id for job in self.api.workspace().jobs}
        result = super()._v022_register_current(show_errors=show_errors)
        if not result:
            return False
        created = [job for job in self.api.workspace().jobs
                   if job.job_id not in previous_ids]
        if len(created) != 1:
            return True
        job = created[0]
        if str(job.name or '').strip().casefold() not in {'content', 'sip', 'uttrekk', ''}:
            return True
        name = readable_job_name(str(job.source_extraction or ''),
                                 self.basic_dias_label.text())
        try:
            self.api.rename_job(job.job_id, name)
            if not self._v022_save_joblist_to_existing_file():
                return False
            self._refresh(force=True)
        except (ValueError, RuntimeError, OSError) as exc:
            if show_errors:
                QMessageBox.warning(self, 'Jobbnavn',
                    'Jobben ble opprettet, men navnet m\u00e5 lagres manuelt:\n' + str(exc))
        return True
