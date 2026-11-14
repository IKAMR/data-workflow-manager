"""a5: integrated production status and saved-history page in the Qt window.

Read-only evidence. The resume marker is a GUI preference, not a completed
stage, an execution checkpoint, or an audit log.
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox, QFrame, QGridLayout, QHBoxLayout, QLabel, QProgressBar, QPushButton,
    QScrollArea, QVBoxLayout, QWidget,
)

from app.production_progress_v020_a5 import (
    STAGE_NAMES, project_pipeline, resume_section, stable_job_key,
)


def active_job_context(window):
    """Use the active workbench JobView, not a new app-side job instance."""
    active_id = getattr(window, '_active_id', None)
    if not active_id:
        return None, ''
    try:
        workspace = window.api.workspace()
        job = next((item for item in workspace.jobs if item.job_id == active_id), None)
        if job is None:
            return None, ''
        info = window.api.work_job_info(active_id)
        uid = str(info.get('job_uid') or '')
        key = stable_job_key(active_id, job_uid=uid,
                             job_list_path=workspace.job_list_path or '')
        return job, key
    except (AttributeError, KeyError, OSError, RuntimeError, ValueError):
        return None, ''


def saved_section_for_window(window) -> str:
    _, key = active_job_context(window)
    return resume_section(
        current_key=key,
        stored_key=str(window.config.value('qt/v020_last_area_job_key', '') or ''),
        stored_section=str(window.config.value('qt/v020_last_area', '') or ''),
    )


class ProductionProgressPage(QWidget):
    def __init__(self, window):
        super().__init__(window)
        self.window = window
        self.setObjectName('v020_a5_progress_page')
        outer = QVBoxLayout(self)
        outer.setContentsMargins(5, 5, 5, 5)
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        outer.addWidget(scroll)
        body = QWidget(scroll)
        scroll.setWidget(body)
        content = QVBoxLayout(body)
        content.setContentsMargins(20, 14, 20, 18)
        content.setSpacing(13)
        header = QHBoxLayout()
        title = QLabel('Produksjonsstatus og historikk', body)
        title.setStyleSheet('font-size: 22px; font-weight: 600;')
        header.addWidget(title, 1)
        back = QPushButton('Til Startside', body)
        back.clicked.connect(lambda: window.v020_integrated_home())
        header.addWidget(back)
        content.addLayout(header)
        self.summary = QLabel('Velg en jobb i Kontroll f\u00f8rst.', body)
        self.summary.setObjectName('v020_a5_summary')
        self.summary.setWordWrap(True)
        self.summary.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        content.addWidget(self.summary)
        self.progress = QProgressBar(body)
        self.progress.setObjectName('v020_a5_control_progress')
        self.progress.setRange(0, 100)
        self.progress.setFormat('Kontroll (lagret jobbstatus): %p %')
        content.addWidget(self.progress)
        self.distinction = QLabel(
            'Kontrollfremdrift er ikke fremdriften for hele produksjonslinjen. '
            'Teknisk fullf\u00f8rt er ikke faglig akseptert, og en evidenskandidat '
            'er ikke en verifisert DIAS AIP.', body,
        )
        self.distinction.setWordWrap(True)
        content.addWidget(self.distinction)
        content.addWidget(QLabel('Arbeidsomr\u00e5der – dokumentert status', body))
        self.stage_grid = QGridLayout()
        self.stage_grid.setSpacing(9)
        self.stage_labels = {}
        for i, (key, title) in enumerate(STAGE_NAMES):
            card = QFrame(body)
            card.setObjectName('v020_a5_stage_' + key)
            card.setFrameShape(QFrame.Shape.StyledPanel)
            layout = QVBoxLayout(card)
            layout.setSpacing(6)
            headline = QHBoxLayout()
            name = QLabel(f'{i + 1}. {title}', card)
            name.setStyleSheet('font-weight: 600;')
            headline.addWidget(name, 1)
            button = QPushButton('G\u00e5 til', card)
            button.setEnabled(key in ('ingest', 'antivirus', 'workspace', 'control', 'report', 'preserve'))
            if button.isEnabled():
                button.clicked.connect(lambda _checked=False, area=key: self._open_area(area))
            headline.addWidget(button)
            layout.addLayout(headline)
            status = QLabel(card)
            status.setObjectName('v020_a5_status_' + key)
            status.setWordWrap(True)
            layout.addWidget(status)
            detail = QLabel(card)
            detail.setObjectName('v020_a5_detail_' + key)
            detail.setWordWrap(True)
            detail.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            layout.addWidget(detail)
            self.stage_labels[key] = (status, detail, button)
            self.stage_grid.addWidget(card, i // 2, i % 2)
        self.stage_grid.setColumnStretch(0, 1)
        self.stage_grid.setColumnStretch(1, 1)
        content.addLayout(self.stage_grid)
        history_row = QHBoxLayout()
        history_row.addWidget(QLabel('Lagrede hendelser i Work:', body))
        self.history_filter = QComboBox(body)
        self.history_filter.setObjectName('v020_a5_history_filter')
        self.history_filter.addItem('Alle arbeidsomr\u00e5der', '')
        for key, title in STAGE_NAMES:
            self.history_filter.addItem(title, key)
        self.history_filter.currentIndexChanged.connect(self._render_history)
        history_row.addWidget(self.history_filter)
        history_row.addStretch(1)
        self.resume = QPushButton('Fortsett sist', body)
        self.resume.setObjectName('v020_a5_resume')
        self.resume.setToolTip('Gå tilbake til siste arbeidsområde for den aktive jobben.')
        self.resume.clicked.connect(lambda: window.v020_resume_area())
        history_row.addWidget(self.resume)
        self.refresh_button = QPushButton('Oppdater status', body)
        self.refresh_button.setObjectName('v020_a6_status_refresh')
        self.refresh_button.clicked.connect(self.refresh)
        history_row.addWidget(self.refresh_button)
        content.addLayout(history_row)
        self._events = ()
        self.history = QLabel(body)
        self.history.setObjectName('v020_a5_history')
        self.history.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.history.setWordWrap(True)
        content.addWidget(self.history)
        self.notes = QLabel(body)
        self.notes.setObjectName('v020_a5_notes')
        self.notes.setWordWrap(True)
        content.addWidget(self.notes)
        content.addStretch(1)

    def _open_area(self, area):
        self.window.v020_open_area(area)

    def _render_history(self, *_unused):
        chosen = self.history_filter.currentData()
        events = [event for event in self._events if not chosen or event.stage == chosen]
        self.history.setText('\n'.join(
            f'{event.at}  |  {dict(STAGE_NAMES).get(event.stage, event.stage)}  |  '
            f'{event.kind}' + (f' \u2013 {event.detail}' if event.detail else '')
            for event in events[:25]
        ) if events else 'Ingen lagrede hendelser for dette arbeidsomr\u00e5det.')

    def refresh(self):
        from app.production_review_v020_a4 import inspect_production_evidence
        job, _key = active_job_context(self.window)
        uid = ''
        if job is not None:
            try:
                uid = str(self.window.api.work_job_info(job.job_id).get('job_uid') or '')
            except (AttributeError, KeyError, OSError, RuntimeError, ValueError):
                pass
        try:
            evidence = inspect_production_evidence(job)
            projection = project_pipeline(job, evidence=evidence, job_uid=uid)
        except (OSError, ValueError, RuntimeError, TypeError) as exc:
            projection = project_pipeline(None)
            self.notes.setText('Kunne ikke lese jobbstatus: ' + str(exc))
        else:
            self.notes.setText(' | '.join(projection.notes[:6]) if projection.notes else
                               'Ingen nye merknader. Dette inneb\u00e6rer ikke godkjenning.')
        self.summary.setText(
            (f'{projection.job_id} – {projection.job_name} | Lagret jobbstatus: '
             f'{projection.job_status or "Ukjent"} | Teknisk rapportstatus: '
             f'{projection.technical_status} | Faglig depotstatus: '
             f'{projection.professional_status}') if projection.has_job
            else 'Ingen aktiv jobb valgt. \u00c5pne en jobbliste og velg en jobb i Kontroll.'
        )
        self.progress.setValue(projection.operation_percent)
        self.progress.setEnabled(projection.has_job)
        for stage in projection.stages:
            status, detail, button = self.stage_labels[stage.key]
            status.setText(stage.label)
            detail.setText(stage.detail)
            button.setEnabled(projection.has_job and stage.key in (
                'ingest', 'antivirus', 'workspace', 'control', 'report', 'preserve'))
        self._events = projection.events
        self._render_history()
        area = saved_section_for_window(self.window)
        self.resume.setEnabled(bool(area))
        self.resume.setText('Fortsett sist')
        self.resume.setToolTip(
            'Fortsett i ' + dict(STAGE_NAMES).get(area, area)
            if area else 'Ingen tidligere arbeidsområde registrert for denne jobben.'
        )
