"""v0.2.2-a1.2: many jobs in one Basic/Advanced Qt workbench.

Basic's Source/Work selection immediately registers an unrun job in the same
DwmWorkbenchAPI used by Advanced. Existing .n5jobs is saved after registration;
a new list needs a user-selected filename once. No second runner or job store.
"""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox, QGroupBox, QHBoxLayout, QLabel, QMessageBox, QPushButton,
    QVBoxLayout,
)

from app.basic_window_fit_v022_a1_8 import (
    fit_basic_height, should_auto_fit, visible_basic_layout_height,
)
from app.basic_multijob_v022_a1_2 import (
    basic_extraction_status, basic_selector_visible, list_job_labels,
    register_basic_plan, same_path,
)
from gui_qt.main_v020_a6 import DwmMainWindow as _ExistingDwmWindow


class DwmMainWindow(_ExistingDwmWindow):
    def __init__(self, *args, **kwargs):
        # Virtual calls may occur during the historical window constructor.
        self._v022_loading_job = True
        self._v022_draft = False
        self._v022_selector_signature = None
        self._v022_save_failed = False
        # Do not infer manual resizing from Qt's startup geometry restoration.
        # Geometry changes made by this controller are explicitly guarded.
        self._v022_fit_ready = False
        self._v022_fit_pending = False
        self._v022_fit_programmatic = False
        self._v022_fit_started = False
        self._v022_last_fitted_step = None
        super().__init__(*args, **kwargs)
        self._v022_install_job_selector()
        self._v022_auto_fit_enabled = self.config.value(
            'qt/v022_basic_auto_fit', True, type=bool)
        self._v022_install_fit_control()
        self._v022_draft = not bool(self._active_id)
        self._v022_loading_job = False
        self._v022_refresh_selector(force=True)
        # A new control starts where the operator actually begins: with the
        # extraction, not an empty job selector or a job-list summary.
        if not self.api.workspace().jobs and getattr(self, '_basic_active', False):
            self._a2_set_step('source')
        self._v022_fit_ready = True
        # The v0.1.14 window-restoration controller was installed by super().
        # It is also queued with a 0-ms timer; let it restore first.
        from PySide6.QtCore import QTimer
        QTimer.singleShot(0, self._v022_schedule_auto_fit)

    def _v022_install_fit_control(self):
        """Only display the size-reset button after manual resizing."""
        content = self._a2_step_groups['source'].parentWidget()
        header = content.layout().itemAt(0).layout()
        button = QPushButton('Tilpass vindu', content)
        button.setObjectName('v022_basic_fit_window')
        button.setToolTip('Gjenoppta automatisk vindushøyde for hvert steg.')
        button.clicked.connect(self._v022_enable_auto_fit)
        header.insertWidget(header.indexOf(self.basic_new_control_button),
                            button, 0, Qt.AlignmentFlag.AlignTop)
        self.v022_fit_window_button = button
        button.setVisible(not self._v022_auto_fit_enabled)

    def _v022_enable_auto_fit(self, _checked=False):
        self._v022_auto_fit_enabled = True
        self.config.setValue('qt/v022_basic_auto_fit', True)
        self.v022_fit_window_button.hide()
        self._v022_schedule_auto_fit()

    def _v022_mark_manual_size(self):
        """Manual size is sticky until the operator chooses 'Tilpass vindu'."""
        self._v022_auto_fit_enabled = False
        self.config.setValue('qt/v022_basic_auto_fit', False)
        if hasattr(self, 'v022_fit_window_button'):
            self.v022_fit_window_button.show()

    def resizeEvent(self, event):
        result = super().resizeEvent(event)
        if (getattr(self, '_v022_fit_ready', False)
                and getattr(self, '_v022_fit_started', False)
                and getattr(self, '_v022_auto_fit_enabled', False)
                and not getattr(self, '_v022_fit_programmatic', False)
                and not getattr(self, '_v022_fit_pending', False)
                and getattr(self, '_basic_active', False)
                and self.isVisible() and not self.isMaximized()
                and not self.isFullScreen() and not self.isMinimized()):
            self._v022_mark_manual_size()
        return result

    def showEvent(self, event):
        result = super().showEvent(event)
        self._v022_schedule_auto_fit()
        return result

    def _v022_auto_fit_allowed(self):
        page = getattr(self, '_basic_page', None)
        # The integrated Depot home/ingest pages can be active while the
        # internal Basic tab still points at this page. Only resize when it
        # is actually displayed; never resize Startside in the background.
        visible = bool(page is not None and self.pages.currentWidget() is page
                       and page.isVisible())
        return should_auto_fit(
            ready=bool(getattr(self, '_v022_fit_ready', False)),
            basic=bool(getattr(self, '_basic_active', False)),
            page_visible=visible, window_visible=self.isVisible(),
            maximized=self.isMaximized(), fullscreen=self.isFullScreen(),
            minimized=self.isMinimized(),
            manual_override=not bool(getattr(self, '_v022_auto_fit_enabled', False)),
        )

    def _v022_schedule_auto_fit(self):
        """Coalesce step/status layout changes into one Qt geometry request."""
        if not getattr(self, '_v022_fit_ready', False):
            return  # Historical Qt-free tests and base ctor lack the new GUI.
        if not self._v022_auto_fit_allowed():
            return
        if getattr(self, '_v022_fit_pending', False):
            return
        self._v022_fit_pending = True
        from PySide6.QtCore import QTimer
        QTimer.singleShot(0, self._v022_apply_auto_fit)

    def _v022_apply_auto_fit(self):
        self._v022_fit_pending = False
        if not self._v022_auto_fit_allowed():
            return
        controller = getattr(self, '_a14_window_positions', None)
        if controller is not None and not getattr(controller, '_ready', True):
            # The original geometry restoration has priority at startup.
            from PySide6.QtCore import QTimer
            QTimer.singleShot(100, self._v022_schedule_auto_fit)
            return
        from PySide6.QtWidgets import QApplication, QScrollArea
        from PySide6.QtCore import QTimer
        scroll = self._basic_page.findChild(QScrollArea)
        if scroll is None or scroll.widget() is None:
            return
        body = scroll.widget()
        # Measure ONLY the active step. The scroll area's resizable body may
        # still have the old, tall Run-step hint after switching back to Work.
        # Its child content has a vertical layout with hidden inactive steps
        # and a final stretch; the visible items give the natural height.
        source_group = getattr(self, '_a2_step_groups', {}).get('source')
        outer_layout = body.layout()
        if source_group is not None and outer_layout is not None:
            content = source_group.parentWidget()
            content_layout = content.layout()
            if content_layout is None:
                return
            content_layout.invalidate()
            content_layout.activate()
            outer_layout.invalidate()
            outer_layout.activate()
            outer_margins = outer_layout.contentsMargins()
            natural = visible_basic_layout_height(
                content_layout, max(240, content.width()))
            natural += outer_margins.top() + outer_margins.bottom()
        else:
            # Qt-free legacy callback tests supply only a scroll-area body.
            # Real Basic windows always have the three step groups above.
            if outer_layout is not None:
                outer_layout.invalidate()
                outer_layout.activate()
            natural = max(body.sizeHint().height(),
                          body.minimumSizeHint().height())
        if natural <= 0 or scroll.viewport().height() <= 0:
            return
        frame = self.frameGeometry()
        screen = QApplication.screenAt(frame.center()) or self.screen()
        if screen is None:
            screen = QApplication.primaryScreen()
        if screen is None:
            return
        area = screen.availableGeometry()
        choice = fit_basic_height(
            content_height=natural,
            viewport_height=scroll.viewport().height(),
            window_height=self.height(),
            # minimumSizeHint() can temporarily include stale Run hints from
            # the shared QStackedWidget. Keep the stable explicit minimum;
            # QWidget will enforce any true native minimum on resize.
            minimum_height=max(480, self.minimumHeight()),
            screen_top=area.y(), screen_height=area.height(),
            frame_top=frame.y(),
            frame_extra=max(0, frame.height() - self.height()),
        )
        self._v022_fit_programmatic = True
        try:
            if abs(choice.window_height - self.height()) > 4:
                self.resize(self.width(), choice.window_height)
            # Move vertically only if expansion would run below usable screen
            # geometry. The original horizontal position/monitor is retained.
            updated_frame = self.frameGeometry()
            if updated_frame.y() != choice.frame_top:
                self.move(self.x(), self.y() + choice.frame_top - updated_frame.y())
            # Reset scrolling only when the operator changes steps. Run
            # progress updates can arrive every 500 ms and must NEVER pull
            # someone away from the controls they have scrolled to inspect.
            step = getattr(self, '_a2_current_step', None)
            if step != getattr(self, '_v022_last_fitted_step', None):
                scroll.verticalScrollBar().setValue(0)
            self._v022_last_fitted_step = step
        finally:
            self._v022_fit_started = True
            # Some platforms deliver native resize notifications on the next
            # event-loop tick rather than during QWidget.resize().
            QTimer.singleShot(0, self._v022_finish_programmatic_fit)

    def _v022_finish_programmatic_fit(self):
        self._v022_fit_programmatic = False

    @staticmethod
    def _a3_neighbor_step(step, direction):
        """Source-first order. The saved-list overview is optional and last."""
        steps = ('source', 'work', 'run', 'overview')
        if step not in steps or direction not in (-1, 1):
            return None
        target = steps.index(step) + direction
        return steps[target] if 0 <= target < len(steps) else None

    def _v022_install_source_first_navigation(self):
        """Present one obvious entry point without moving any Source/Work data.

        Only existing navigation widgets are reordered; Basic and Advanced
        still share the same fields, API, file, and runner.
        """
        nav = self._a2_navigation
        buttons = self._a2_step_buttons
        for key, text in (
            ('source', '1. Velg uttrekk'),
            ('work', '2. Arbeidsmappe'),
            ('run', '3. Kontroller / kjør'),
            ('overview', 'Oversikt'),
        ):
            buttons[key].setText(text)
            nav.removeWidget(buttons[key])
        for position, key in enumerate(('source', 'work', 'run', 'overview')):
            nav.insertWidget(position, buttons[key], 1)
        self._a2_step_groups['source'].setTitle('1. Velg arkivuttrekk')
        self._a2_step_groups['work'].setTitle('2. Velg arbeidsmappe (Work)')
        self._a2_step_groups['run'].setTitle('3. Velg kontroller og kjør')
        content = self._a2_step_groups['source'].parentWidget()
        for label in content.findChildren(QLabel):
            if label.text().startswith('Source og info.xml · Work · Kjøring'):
                label.setText('Velg uttrekk · Velg arbeidsmappe · Velg kontroller · Start')
        # Let the original navigation implementation read our order for
        # Previous/Next, and synchronize its enabled state immediately.
        self._a2_set_step(self._a2_current_step)

    def _v022_install_job_selector(self):
        content = self._a2_step_groups['source'].parentWidget()
        layout = content.layout()
        group = QGroupBox('Uttrekk i kontrollen', content)
        group.setObjectName('v022_basic_job_selector')
        outer = QVBoxLayout(group)
        row = QHBoxLayout()
        self.v022_selector_caption = QLabel('Bytt uttrekk:', group)
        row.addWidget(self.v022_selector_caption)
        self.v022_current_job_label = QLabel(group)
        self.v022_current_job_label.setObjectName('v022_basic_current_extraction')
        self.v022_current_job_label.setWordWrap(True)
        row.addWidget(self.v022_current_job_label, 1)
        self.v022_job_selector = QComboBox(group)
        self.v022_job_selector.setObjectName('v022_basic_job_selector_combo')
        self.v022_job_selector.setMinimumWidth(235)
        self.v022_job_selector.currentIndexChanged.connect(self._v022_choose_job)
        row.addWidget(self.v022_job_selector, 1)
        self.v022_new_job_button = QPushButton('Legg til nytt uttrekk', group)
        self.v022_new_job_button.setObjectName('v022_basic_add_job')
        self.v022_new_job_button.clicked.connect(self._v022_new_draft)
        row.addWidget(self.v022_new_job_button)
        self.v022_save_job_button = QPushButton('Lagre', group)
        self.v022_save_job_button.setObjectName('v022_basic_save_job')
        self.v022_save_job_button.clicked.connect(self._v022_save_selected_job)
        row.addWidget(self.v022_save_job_button)
        self.v022_save_list_button = QPushButton('Lagre som…', group)
        self.v022_save_list_button.setObjectName('v022_basic_save_list')
        self.v022_save_list_button.clicked.connect(self._v022_save_joblist)
        row.addWidget(self.v022_save_list_button)
        outer.addLayout(row)
        # Registration is not the same as persistence. Keep these statuses in
        # separate labels so an unrun job is never presented as unsaved/absent.
        self.v022_registration_status = QLabel(group)
        self.v022_registration_status.setObjectName('v022_basic_registration_status')
        self.v022_registration_status.setWordWrap(True)
        outer.addWidget(self.v022_registration_status)
        self.v022_joblist_status = QLabel(group)
        self.v022_joblist_status.setObjectName('v022_basic_joblist_status')
        self.v022_joblist_status.setWordWrap(True)
        self.v022_joblist_status.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse)
        outer.addWidget(self.v022_joblist_status)
        # The existing-extractions panel is shown ONLY after a job exists.
        # Source itself is the one primary input for a completely empty list.
        self.v022_selector_group = group
        layout.insertWidget(1, group)
        self._v022_install_source_first_navigation()
        # Restore the separate, established fresh-start action. Adding an
        # extraction must NOT be mistaken for discarding the current control.
        self.basic_new_control_button.setText('Ny kontroll')
        self.basic_new_control_button.setToolTip(
            'Start med helt tomt kontrolloppsett. Tidligere lagrede '
            'kontroller, uttrekk og Work-resultater beholdes.')
        self.basic_new_control_button.show()
        self.v022_new_job_button.setToolTip(
            'Legg et nytt uttrekk til denne kontrollen uten å fjerne de andre.')
        self.v022_save_job_button.setToolTip(
            'Lagre denne kontrollen. Første gang velges filnavn.')
        self.v022_save_list_button.setToolTip(
            'Lagre denne kontrollen under et nytt filnavn.')
        # Save As remains available under the existing Kjøring and Oversikt
        # controls. Do not show duplicate Save As buttons in the same view.
        self.v022_save_list_button.hide()
        # Simple mode should not require knowing the .n5jobs storage model.
        for item in self._a2_step_groups['run'].findChildren(QLabel):
            if item.text() == 'Jobbliste (valgfritt):':
                item.setText('Lagret kontroll (valgfritt):')
        for item in self._a2_overview_page.findChildren(QLabel):
            if item.text() == 'Jobbliste (valgfritt)':
                item.setText('Lagret kontroll (valgfritt)')

    def _v022_refresh_selector(self, *, force=False):
        if not hasattr(self, 'v022_job_selector'):
            return
        workspace = self.api.workspace()
        jobs = list_job_labels(self.api)
        step = str(getattr(self, '_a2_current_step', 'source'))
        # A running/completed job can change status without changing the job
        # list or the selected job. Include those values in the refresh key.
        statuses = tuple((job.job_id, getattr(job, 'status', None),
                          getattr(job, 'progress', 0),
                          getattr(job, 'current_operation', 0))
                         for job in workspace.jobs)
        marker = (jobs, statuses, step, self._active_id, bool(self._v022_draft),
                  str(workspace.job_list_path or ''), self._v022_save_failed)
        if marker == self._v022_selector_signature and not force:
            return
        self._v022_selector_signature = marker

        # One extraction: Source and Work stay focused on their single task.
        # Offer adding a second extraction only on Run/Overview. Once there
        # are multiple jobs (or a second draft), the picker is available on
        # every step so the operator can safely switch between them.
        show = basic_selector_visible(len(jobs), step, new_draft=self._v022_draft)
        self.v022_selector_group.setVisible(show)
        self.v022_selector_group.setTitle(
            'Uttrekk i denne kontrollen' if len(jobs) > 1 or self._v022_draft
            else 'Uttrekk klart for kontroll')
        one_selected = (len(jobs) == 1 and not self._v022_draft and
                        self._active_id == jobs[0][0])
        self.v022_selector_caption.setVisible(not one_selected)
        self.v022_current_job_label.setVisible(one_selected)
        if one_selected:
            self.v022_current_job_label.setText(
                f'Aktivt uttrekk: {jobs[0][0]} · {jobs[0][1]}')
        selector = self.v022_job_selector
        selector.setVisible(bool(jobs) and not one_selected)
        selector.blockSignals(True)
        try:
            selector.clear()
            if self._v022_draft or not jobs:
                selector.addItem('Nytt uttrekk – ikke registrert', None)
            for job_id, name in jobs:
                selector.addItem(f'{job_id} · {name}', job_id)
            if not self._v022_draft and self._active_id:
                index = selector.findData(self._active_id)
                selector.setCurrentIndex(max(0, index))
            else:
                selector.setCurrentIndex(0)
        finally:
            selector.blockSignals(False)

        current = (next((job for job in workspace.jobs
                         if job.job_id == self._active_id), None)
                   if not self._v022_draft else None)
        if self._v022_draft and jobs:
            registration = (f'{len(jobs)} registrert. Nytt uttrekk er under '
                            'registrering – velg Source og Work.')
        elif current is not None:
            condition = basic_extraction_status(
                getattr(current, 'status', None),
                progress=getattr(current, 'progress', 0),
                current_operation=getattr(current, 'current_operation', 0))
            registration = (f'Status: {condition}.' if one_selected else
                            f'{len(jobs)} uttrekk registrert. '
                            f'Aktivt uttrekk: {current.job_id} – {condition}.')
        else:
            registration = f'{len(jobs)} registrert.'
        self.v022_registration_status.setText(registration)
        filepath = str(workspace.job_list_path or '')
        state = ('Lagring: Feilet – trykk «Lagre» for å prøve igjen.'
                 if filepath and self._v022_save_failed else
                 'Lagring: Lagret i ' + Path(filepath).name + ' (oppdateres automatisk).'
                 if filepath else
                 'Lagring: Ikke lagret til fil – trykk «Lagre» for å velge plassering.')
        self.v022_joblist_status.setText(state)
        self.v022_joblist_status.setToolTip(filepath or state)

        busy = self._worker is not None or self.api.running
        controls = getattr(self, '_selected_basic_controls', None)
        chosen = bool(controls()) if callable(controls) else True
        self.v022_new_job_button.setEnabled(
            not busy and not self._v022_draft and chosen)
        self.v022_new_job_button.setToolTip(
            'Velg minst én kontroll før du legger til et nytt uttrekk.'
            if not chosen else
            'Legg til et nytt uttrekk uten å starte kjøring. '
            'De registrerte uttrekkene beholdes.')
        self.v022_save_job_button.setEnabled(not busy)
        self.v022_save_list_button.setEnabled(not busy)
        selector.setEnabled(not busy)
        if getattr(self, '_v022_fit_ready', False):
            # Status can add/remove the selector and change natural height.
            # Scheduling is coalesced, so we never resize on every 500-ms tick.
            self._v022_schedule_auto_fit()

    def _a2_set_step(self, step):
        """Refresh contextual actions immediately on Next/Previous/tab clicks.

        The base constructor also calls this method before the new widgets
        exist; _v022_refresh_selector intentionally handles that case.
        """
        # Ignore interim resize events while the active Qt layout changes.
        self._v022_schedule_auto_fit()
        result = super()._a2_set_step(step)
        self._v022_refresh_selector()
        self._v022_schedule_auto_fit()
        if (getattr(self, '_v022_fit_ready', False)
                and hasattr(self, '_basic_page')):
            # Some Windows/Qt layouts settle one native event-loop turn after
            # the show/hide transition. Recheck once, without a resize loop.
            from PySide6.QtCore import QTimer
            QTimer.singleShot(45, self._v022_schedule_auto_fit)
        return result

    def _v022_save_joblist_to_existing_file(self, *, force=False):
        """Auto-persist to an *already chosen* job-list file; never invent a path."""
        path = self.api.workspace().job_list_path
        if not path:
            return True
        # The actual DWM API has no public `dirty` property. Persist every
        # completed registration to the selected file, including job selection.
        # Do not treat a Qt-only fake API attribute as a persistence contract.
        try:
            output = self.api.save_job_list()
        except (OSError, ValueError, RuntimeError) as exc:
            self._v022_save_failed = True
            QMessageBox.warning(self, 'Kontrollen ble ikke lagret',
                                'Uttrekket er registrert i minnet, men kunne ikke '
                                'lagres til fil:\n' + str(exc))
            return False
        self._remember_joblist(str(output))
        self._v022_save_failed = False
        return True

    def _v022_register_current(self, *, show_errors: bool = True) -> bool:
        if getattr(self, '_v022_loading_job', False):
            return True
        if self._worker is not None or self.api.running:
            if show_errors:
                QMessageBox.information(self, 'Pågående kontroll',
                                        'Endre uttrekkene etter at kjøringen er avsluttet.')
            return False
        source = self.basic_source_path.text().strip()
        work = self.basic_work_path.text().strip()
        if not source or not work:
            if show_errors:
                QMessageBox.information(self, 'Ufullstendig uttrekk',
                    'Velg både Source og Work før uttrekket kan registreres og lagres.')
            return False
        from app.basic_start_v0111_a1 import prepare_basic_plan
        try:
            plan = prepare_basic_plan(source, work, self.api.settings,
                                      controls=self._selected_basic_controls())
            approved = getattr(self, '_a3_work_approval', None)
            explicitly_approved = bool(approved and len(approved) >= 3 and
                                       same_path(approved[0], plan.source_extraction) and
                                       same_path(approved[1], plan.work_operations) and
                                       approved[2] in ('empty', 'unrelated'))
            outcome = register_basic_plan(
                self.api, plan, selected_job_id=self._active_id,
                create_new=bool(self._v022_draft), work_approved=explicitly_approved,
            )
        except (OSError, ValueError, RuntimeError) as exc:
            if show_errors:
                QMessageBox.warning(self, 'Uttrekket er ikke lagret', str(exc))
            return False
        # The active job ID is shared with Advanced; never reset the list.
        self._active_id = outcome.job_id
        self._basic_job_id = outcome.job_id
        self._v022_draft = False
        self._basic_selection_edited = False
        self._basic_legacy_layout = False
        # Keep the operator's *specific* Work approval, not an approval for an
        # arbitrary folder. Old Basic still checks this at Start control.
        # Metadata import may turn an originally empty Work into unknown_job.
        # Only the newly registered job, bound to the same Source/Work, can
        # allow that DWM-owned marker to be treated as same_job.
        old_approval = approved if explicitly_approved else None
        # Metadata are Work-only; original Source and imported XML are unchanged.
        if getattr(self, '_a2_pending_dirty', False):
            try:
                job = self._a2_matching_job()
                if job is not None:
                    self._a2_save_metadata(job)
            except (OSError, ValueError) as exc:
                QMessageBox.warning(self, 'Metadata krever lagring',
                                    'Uttrekket er opprettet, men DIAS-metadata '
                                    'må kontrolleres:\n' + str(exc))
                return False
        if not self._v022_save_joblist_to_existing_file():
            return False
        # The selected Work may now contain DWM metadata or even the saved
        # joblist. Refresh ONLY the operator-approved Source/Work token against
        # the final contents; the inherited runner still does its own preflight.
        if old_approval is not None:
            from app.basic_work_guard_v0113_a3 import inspect_work
            observed = inspect_work(plan.work_operations, plan.source_extraction)
            from app.basic_start_v0111_a1 import existing_basic_job
            known = existing_basic_job(self.api, plan)
            if known == outcome.job_id and observed.kind == 'unknown_job':
                approved_kind = 'same_job'
            elif observed.kind in ('empty', 'unrelated', 'same_job'):
                approved_kind = observed.kind
            else:
                approved_kind = None
            self._a3_work_approval = ((str(plan.source_extraction.resolve(strict=False)),
                                       str(plan.work_operations.resolve(strict=False)),
                                       approved_kind) if approved_kind else None)
        self._refresh(force=True)
        self._v022_refresh_selector(force=True)
        self._sync_basic_status()
        return True

    def _v022_save_selected_job(self, _checked=False):
        if not self._v022_register_current():
            return
        if not self.api.workspace().job_list_path:
            self._v022_save_joblist()

    def _v022_save_joblist(self, _checked=False):
        if not self._v022_register_current(show_errors=True):
            return
        # Explicit Save As, also for an already saved control. The ordinary
        # 'Lagre' action keeps using the current filename / first-time picker.
        saved = self._save_as()
        self._v022_save_failed = not bool(saved)
        self._v022_refresh_selector(force=True)

    def _v022_new_draft(self, _checked=False):
        if self._worker is not None or self.api.running:
            QMessageBox.information(self, 'Legg til uttrekk',
                                    'Avslutt kjøringen før du legger til et uttrekk.')
            return
        if not self._v022_draft and self._active_id:
            # Advanced may have a legitimate incomplete job draft. Keep that
            # shared job untouched while starting a separate Basic draft.
            if self.basic_source_path.text() and self.basic_work_path.text():
                if not self._v022_register_current():
                    return
        elif self._v022_draft and (self.basic_source_path.text() or
                                     self.basic_work_path.text()):
            answer = QMessageBox.question(
                self, 'Bytte utkast', 'Nåværende ufullstendige utkast '
                'er ikke registrert. Forkaste det og starte et nytt uttrekk?',
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No)
            if answer != QMessageBox.StandardButton.Yes:
                return
        self._v022_loading_job = True
        try:
            # Only reset Basic's *input form*; never api.new_job_list().
            self._v022_draft = True
            self._reset_basic_selection()
            self._a2_pending_values = {}
            self._a2_original = None
            self._a2_original_fields = {}
            self._a2_pending_dirty = False
            self._a3_manually_loaded_info = False
            self._a3_work_approval = None
            self._a3_auto_results_pending = False
            self.basic_dias_label.clear()
            self.basic_dias_note.setText('Nytt uttrekk: velg Source og Work. '
                                         'Andre uttrekk beholdes.')
        finally:
            self._v022_loading_job = False
        self._v022_refresh_selector(force=True)
        self._a2_set_step('source')

    def _a3_new_control(self):
        """Start an independent, empty control; preserve prior files/results.

        'Ny kontroll' is intentionally different from 'Legg til uttrekk'.
        This is an explicit new workspace, NEVER a deletion of an old .n5jobs
        or its Work. Both modes still use the same DWM application API.
        """
        if self._worker is not None or self.api.running:
            QMessageBox.information(
                self, 'Ny kontroll', 'Avslutt kjøringen før du starter en ny kontroll.')
            return False
        workspace = self.api.workspace()
        source = self.basic_source_path.text().strip()
        work = self.basic_work_path.text().strip()
        partial = bool(self._v022_draft and
                       (source or work or getattr(self, '_a2_pending_dirty', False)
                        or self.basic_dias_label.text().strip()))
        if workspace.jobs or partial:
            extra = ('Det ufullstendige uttrekksutkastet blir forkastet.\n'
                     if partial else '')
            decision = QMessageBox.question(
                self, 'Ny kontroll',
                f'Starte en helt ny kontroll med tomme felt?\n\n'
                f'{len(workspace.jobs)} uttrekk i gjeldende kontroll lukkes, '
                'men lagrede filer og resultater slettes ikke.\n'
                + extra,
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if decision != QMessageBox.StandardButton.Yes:
                return False
        # Store any completed edit first, but never attempt to save an
        # incomplete draft as an executable job. Such a draft is discarded
        # only after the operator has confirmed that decision above.
        if (not self._v022_draft and source and work
                and not self._basic_legacy_layout
                and (getattr(self, '_basic_selection_edited', False)
                     or getattr(self, '_a2_pending_dirty', False))):
            if not self._v022_register_current():
                return False
        workspace = self.api.workspace()
        if workspace.job_list_path:
            if not self._v022_save_joblist_to_existing_file(force=True):
                return False
        elif workspace.jobs:
            decision = QMessageBox.question(
                self, 'Lagre før ny kontroll?',
                'Denne kontrollen er ikke lagret til fil.\n'
                'Vil du lagre uttrekkene før du starter på nytt?',
                (QMessageBox.StandardButton.Save |
                 QMessageBox.StandardButton.Discard |
                 QMessageBox.StandardButton.Cancel),
                QMessageBox.StandardButton.Save,
            )
            if decision == QMessageBox.StandardButton.Cancel:
                return False
            if decision == QMessageBox.StandardButton.Save:
                # Call the existing Save As implementation, without our own
                # draft-registration override; all completed jobs are already
                # in the one canonical API. Cancelling keeps the current view.
                if not super()._save_as():
                    return False
            elif decision != QMessageBox.StandardButton.Discard:
                return False
        # New-list changes only the active in-memory workspace. It does not
        # unlink/delete an old list file, Source, Work or historical results.
        try:
            self.api.new_job_list()
        except (OSError, ValueError, RuntimeError) as exc:
            QMessageBox.warning(self, 'Kunne ikke starte ny kontroll', str(exc))
            return False
        self._v022_loading_job = True
        try:
            self._active_id = None
            self._basic_job_id = None
            self._v022_draft = True
            self._v022_save_failed = False
            self._render_key = None
            self._a8_run_context = None
            self._a8_live_job = None
            self.config.setValue('qt/skip_auto_reopen', True)
            self.config.setValue('qt/last_job_list', '')
            self._a2_pending_values = {}
            self._a2_original = None
            self._a2_original_fields = {}
            self._a2_pending_dirty = False
            self._a3_manually_loaded_info = False
            self._a3_work_approval = None
            self._a3_auto_results_pending = False
            self._reset_basic_selection()
            self.basic_dias_label.clear()
            self.basic_dias_note.setText('Ny kontroll: velg Source og Work.')
        finally:
            self._v022_loading_job = False
        self._refresh_recent_menu()
        self._refresh(force=True)
        self._v022_refresh_selector(force=True)
        self._a2_set_step('source')
        return True

    def _v022_choose_job(self, _index):
        if getattr(self, '_v022_loading_job', False):
            return
        selected = self.v022_job_selector.currentData()
        if selected is None:
            if not self._v022_draft:
                self._v022_new_draft()
            return
        if selected == self._active_id and not self._v022_draft:
            return
        if self._worker is not None or self.api.running:
            self._v022_refresh_selector(force=True)
            return
        if self._v022_draft and (self.basic_source_path.text() or
                                 self.basic_work_path.text()):
            if self.basic_source_path.text() and self.basic_work_path.text():
                if not self._v022_register_current():
                    self._v022_refresh_selector(force=True)
                    return
            else:
                answer = QMessageBox.question(
                    self, 'Ufullstendig uttrekksutkast',
                    'Uttrekket er ikke registrert. Forkaste utkastet og velge et annet uttrekk?',
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No)
                if answer != QMessageBox.StandardButton.Yes:
                    self._v022_refresh_selector(force=True)
                    return
        elif self._active_id and not self._v022_register_current():
            self._v022_refresh_selector(force=True)
            return
        self._v022_loading_job = True
        try:
            self.api.select_job(selected)
            self._active_id = selected
            self._basic_job_id = selected
            self._v022_draft = False
            self._a2_pending_dirty = False
            self._a3_work_approval = None
            self._load_basic_active_job()
            if not self._v022_save_joblist_to_existing_file(force=True):
                # Keep the new selection visible for retry, but flag explicitly
                # that the .n5jobs file did not record it.
                self._v022_save_failed = True
        except (OSError, ValueError, RuntimeError) as exc:
            QMessageBox.warning(self, 'Kunne ikke velge uttrekk', str(exc))
        finally:
            self._v022_loading_job = False
        self._refresh(force=True)
        self._v022_refresh_selector(force=True)
        self._a2_refresh_overview()
        self._sync_basic_status()

    def _a3_accept_source(self, folder):
        """Choosing a different Source starts a new job; never overwrites old."""
        old_source = self.basic_source_path.text().strip()
        if (not self._v022_draft and old_source and
                not same_path(old_source, folder)):
            # Persist prior metadata before the Source selector resets it.
            if self.basic_source_path.text() and self.basic_work_path.text():
                if not self._v022_register_current():
                    return
            self._v022_draft = True
        return super()._a3_accept_source(folder)

    def _a3_accept_work(self, folder):
        """The established guarded Work chooser remains authoritative."""
        super()._a3_accept_work(folder)
        if (not self._v022_loading_job and
                same_path(self.basic_work_path.text().strip(), folder)):
            # Auto-register the complete plan BEFORE 'Start kontroll'.
            self._v022_register_current()

    def _load_basic_active_job(self):
        loading = getattr(self, '_v022_loading_job', False)
        self._v022_loading_job = True
        try:
            # The former implementation refuses to read metadata if the
            # previous job has a pending edit. Switching already flushes it.
            super()._load_basic_active_job()
        finally:
            self._v022_loading_job = loading

    def _enter_basic(self):
        if self._basic_active:
            return
        self._v022_loading_job = True
        try:
            self._basic_selection_edited = False
            super()._enter_basic()
            self._v022_draft = not bool(self._active_id)
            self._a2_pending_dirty = False
            if self._active_id:
                self._load_basic_active_job()
        finally:
            self._v022_loading_job = False
        self._v022_refresh_selector(force=True)
        self._v022_schedule_auto_fit()
        if not self.api.workspace().jobs:
            self._a2_set_step('source')

    def _leave_basic(self):
        if not self._basic_active:
            return
        if self._v022_draft:
            source = self.basic_source_path.text().strip()
            work = self.basic_work_path.text().strip()
            if source and work:
                if not self._v022_register_current():
                    return
            elif source or work:
                decision = QMessageBox.question(
                    self, 'Ufullstendig uttrekksutkast',
                    'Et nytt uttrekk mangler Source eller Work og er ikke lagret. '
                    'Forkaste utkastet og åpne Avansert modus?',
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No)
                if decision != QMessageBox.StandardButton.Yes:
                    return
        elif not self._v022_register_current():
            return
        return super()._leave_basic()

    def _save(self) -> bool:
        if (getattr(self, '_basic_active', False) and
                not getattr(self, '_v022_loading_job', False) and
                (not self._v022_draft or self.basic_source_path.text() or
                 self.basic_work_path.text())):
            if not self._v022_register_current():
                return False
        result = super()._save()
        self._v022_refresh_selector(force=True)
        return result

    def _save_as(self) -> bool:
        if (getattr(self, '_basic_active', False) and
                not getattr(self, '_v022_loading_job', False) and
                (not self._v022_draft or self.basic_source_path.text() or
                 self.basic_work_path.text())):
            if not self._v022_register_current():
                return False
        result = super()._save_as()
        self._v022_refresh_selector(force=True)
        return result

    def _start_basic_control(self):
        if not self._v022_register_current():
            return
        # Existing super now sees an identical registered job and does not
        # offer to replace the open job list. Worker/preflight are unchanged.
        return super()._start_basic_control()

    def _open_path(self, path: str):
        result = super()._open_path(path)
        if hasattr(self, 'v022_job_selector'):
            self._v022_draft = not bool(self._active_id)
            self._v022_refresh_selector(force=True)
        return result

    def _new_list(self):
        result = super()._new_list()
        if hasattr(self, 'v022_job_selector'):
            self._v022_draft = True
            self._v022_refresh_selector(force=True)
            if not self.api.workspace().jobs and self._basic_active:
                self._a2_set_step('source')
        return result

    def _sync_basic_status(self):
        result = super()._sync_basic_status()
        self._v022_refresh_selector()
        return result
