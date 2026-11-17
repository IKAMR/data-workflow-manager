"""v0.2.2-a6: one workflow-order editor shared by Basic and Advanced Qt.

The per-job sequence remains owned by DwmWorkbenchAPI. Never edit Source,
Work evidence, saved job data, or an active workflow without the same API.
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QDialogButtonBox, QHBoxLayout, QLabel, QListWidget,
    QListWidgetItem, QMessageBox, QPushButton, QVBoxLayout,
)

from app.workflow_dependencies_v022_a7 import (
    dependency_label, dependency_links, validate_dependencies,
    arkade_last_with_dependencies,
)
from app.workflow_order_v022_a6 import (
    arkade_last_order, checked_order, move_operation, ordering_warnings,
)


class WorkflowOrderDialog(QDialog):
    """Reorder an existing per-job workflow without adding/removing operations."""

    def __init__(self, parent, *, job_id: str, operations):
        super().__init__(parent)
        self._labels = {op.operation_id: op.name for op in operations}
        self._original = tuple(op.operation_id for op in operations)
        checked_order(self._original, self._original)
        self._order = self._original
        self.setWindowTitle(f'Rekkefølge på deljobber – {job_id}')
        self.setMinimumSize(700, 550)
        self.setModal(True)

        layout = QVBoxLayout(self)
        intro = QLabel(
            f'Jobb: {job_id}. Flytt deljobber opp/ned eller bruk Arkade-forslaget. '
            'Rekkefølgen lagres bare for denne jobben; ingen kontroll kjøres nå.', self)
        intro.setWordWrap(True)
        layout.addWidget(intro)

        center = QHBoxLayout()
        self.list = QListWidget(self)
        self.list.setAlternatingRowColors(True)
        self.list.setObjectName('dwm_a6_workflow_order')
        center.addWidget(self.list, 1)
        buttons = QVBoxLayout()
        self.up = QPushButton('↑ Opp', self)
        self.down = QPushButton('↓ Ned', self)
        self.arkade_last = QPushButton('Arkade-testene sist', self)
        self.reset_order = QPushButton('Tilbakestill', self)
        for widget in (self.up, self.down, self.arkade_last, self.reset_order):
            buttons.addWidget(widget)
        buttons.addStretch(1)
        center.addLayout(buttons)
        layout.addLayout(center, 1)

        self.warnings = QLabel(self)
        self.warnings.setObjectName('dwm_a6_order_warning')
        self.warnings.setWordWrap(True)
        self.warnings.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(self.warnings)

        footer = QDialogButtonBox(self)
        self.apply_button = footer.addButton('Lagre rekkefølge', QDialogButtonBox.ButtonRole.AcceptRole)
        footer.addButton(QDialogButtonBox.StandardButton.Cancel)
        footer.accepted.connect(self.accept)
        footer.rejected.connect(self.reject)
        layout.addWidget(footer)

        self.up.clicked.connect(lambda: self._move(-1))
        self.down.clicked.connect(lambda: self._move(1))
        self.arkade_last.clicked.connect(self._arkade_last)
        self.reset_order.clicked.connect(self._reset)
        self.list.currentRowChanged.connect(self._update)
        self._fill(selected=0)

    def operation_ids(self) -> tuple[str, ...]:
        return checked_order(self._original, self._order)

    def _fill(self, *, selected: int) -> None:
        self.list.blockSignals(True)
        try:
            self.list.clear()
            for index, operation_id in enumerate(self._order, 1):
                item = QListWidgetItem(f'{index:02d}. [{dependency_label(operation_id)}] {self._labels[operation_id]}', self.list)
                item.setData(Qt.ItemDataRole.UserRole, operation_id)
                prerequisites = ', '.join(dependency_links(operation_id, self._order)) or 'Ingen'
                item.setToolTip(f'Operasjon: {operation_id}\nAvhengighetsnr.: {dependency_label(operation_id)}\nMaa komme etter: {prerequisites}')
            self.list.setCurrentRow(max(0, min(selected, self.list.count() - 1)))
        finally:
            self.list.blockSignals(False)
        self._update()

    def _update(self, *_args) -> None:
        index = self.list.currentRow()
        self.up.setEnabled(index > 0)
        self.down.setEnabled(0 <= index < len(self._order) - 1)
        self.arkade_last.setEnabled(any(op in self._order for op in
                                        ('arkade5_noark5_test', 'arkade5_pronom_analysis')))
        changed = self._order != self._original
        blockers = validate_dependencies(self._order)
        self.apply_button.setEnabled(changed and not blockers)
        notes = ordering_warnings(self._order)
        if blockers:
            self.warnings.setText('BLOKKERT - ugyldig avhengighetsrekkefolge:\n' + '\n'.join(blockers))
            return
        self.warnings.setText(
            ('Viktig om resultatgrunnlag:\n• ' + '\n• '.join(notes))
            if notes else
            'Resultatimport og depotrapport er ikke plassert foran relevante nye Arkade-resultater.'
        )

    def _move(self, offset: int) -> None:
        index = self.list.currentRow()
        if index < 0:
            return
        self._order = move_operation(self._order, index, offset)
        self._fill(selected=index + offset)

    def _arkade_last(self) -> None:
        chosen = self.list.currentItem()
        selected_id = chosen.data(Qt.ItemDataRole.UserRole) if chosen else None
        self._order = arkade_last_with_dependencies(self._order)
        self._fill(selected=self._order.index(selected_id) if selected_id in self._order else 0)

    def _reset(self) -> None:
        self._order = self._original
        self._fill(selected=0)


def open_active_job_order(window) -> bool:
    """Edit and persist the selected job, never another job or a running run."""
    if window._worker is not None or window.api.running:
        QMessageBox.information(window, 'Rekkefølge på deljobber',
                                'Avslutt pågående kjøring før du endrer deljobbrekkefølge.')
        return False

    # Basic must register the current Source/Work and checkbox membership
    # before an order is edited, otherwise registration can recreate a plan.
    if getattr(window, '_basic_active', False):
        register = getattr(window, '_v022_register_current', None)
        if callable(register) and not register():
            return False

    job_id = window._active_id
    if not job_id:
        QMessageBox.information(window, 'Rekkefølge på deljobber', 'Velg eller opprett en jobb først.')
        return False
    try:
        details = window.api.job_details(job_id)
        original = tuple(op.operation_id for op in details.operations)
        if not original:
            QMessageBox.information(window, 'Rekkefølge på deljobber',
                                    'Denne jobben har ingen deljobber å flytte.')
            return False
        dialog = WorkflowOrderDialog(window, job_id=job_id, operations=details.operations)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return False
        changed = dialog.operation_ids()
        if changed == original:
            return False
        failures = validate_dependencies(changed)
        if failures:
            raise ValueError('Avhengigheter blokkerer lagring: ' + '; '.join(failures))
        # The edit is per-job; if selection changes while a dialog is open,
        # refuse rather than applying the order to the wrong extraction.
        current = tuple(op.operation_id for op in window.api.job_details(job_id).operations)
        if current != original or window._active_id != job_id:
            raise ValueError('Jobbvalget eller kontrollene er endret. Åpne dialogen på nytt.')
        if window._worker is not None or window.api.running:
            raise ValueError('En kjøring er startet. Rekkefølgen kan ikke endres nå.')
        # Explicit consent to invalidate an existing execution cursor; the
        # workbench set_workflow performs the state transition authoritatively.
        job = details.job
        has_history = (job.status in ('Ferdig', 'Feil', 'Hoppet over', 'Venter ved kontrollpunkt')
                       or int(getattr(job, 'current_operation', 0) or 0) > 0)
        if has_history:
            answer = QMessageBox.question(
                window, 'Endre rekkefølge etter kjøring?',
                f'{job_id} har tidligere kjørt kontroller. Endring av rekkefølgen '
                'nullstiller jobbens kjørestatus og kontrollpunkt for en eventuell ny kjøring.\n\n'
                'Tidligere Work-resultater slettes ikke. Vil du fortsette?',
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No)
            if answer != QMessageBox.StandardButton.Yes:
                return False
        # Require a chosen joblist filename before mutation. The existing save
        # path is also where Basic/Advanced share job order between restarts.
        if not window.api.workspace().job_list_path and not window._save_as():
            return False
        window.api.set_workflow(job_id, changed)
        # Work-first persistence and .n5jobs index are handled by the API,
        # not by a second order store or direct JSON editing.
        path = window.api.save_job_list()
        window._remember_joblist(str(path))
        window._render_key = None
        window._refresh(force=True)
        if hasattr(window, '_v022_refresh_selector'):
            window._v022_refresh_selector(force=True)
        window.statusBar().showMessage(f'{job_id}: rekkefølge lagret ({len(changed)} deljobber)', 6500)
        return True
    except (OSError, ValueError, RuntimeError) as exc:
        QMessageBox.warning(window, 'Rekkefølge på deljobber', str(exc))
        return False
