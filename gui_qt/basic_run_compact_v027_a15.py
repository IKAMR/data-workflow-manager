"""Compact, responsive Simple run step; existing widgets and callbacks retained.

Only the presentation is changed. No second workflow state, run loop, or timer.
The ordinary 500-ms Basic status timer also refreshes the auxiliary status.
"""
from __future__ import annotations

import re

from PySide6.QtCore import QEvent, QObject, Qt
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QBoxLayout, QGroupBox, QHBoxLayout, QLabel, QToolButton, QVBoxLayout,
)

from app.aftercare_v027_a15 import aftercare_summary


class _ResponsiveRunPanels(QObject):
    def __init__(self, host, panels: QBoxLayout):
        super().__init__(host)
        self.panels = panels

    def eventFilter(self, watched, event):
        if event.type() == QEvent.Type.Resize:
            direction = (QBoxLayout.Direction.TopToBottom if watched.width() < 720
                         else QBoxLayout.Direction.LeftToRight)
            if self.panels.direction() != direction:
                self.panels.setDirection(direction)
        return False


def _move_from_layout(layout, widget, target):
    if widget is None:
        return False
    # Only remove the actual layout item. Never delete/re-create a checkbox or
    # disconnect its signals; persistent Qt settings and API references remain.
    index = layout.indexOf(widget)
    if index < 0:
        return False
    layout.takeAt(index)
    widget.setParent(target)
    target.layout().addWidget(widget)
    widget.show()
    return True


def _move_nested_widget(layout, widget, target_layout):
    for i in range(layout.count()):
        item = layout.itemAt(i)
        child = item.layout()
        if child is not None and child.indexOf(widget) >= 0:
            child.removeWidget(widget)
            target_layout.addWidget(widget)
            return True
    return False


def _refresh_simple_run(window):
    status_label = getattr(window, '_a15_aftercare_status', None)
    if status_label is None:
        return
    job_id = getattr(window, '_active_id', None)
    if job_id:
        try:
            job = window.api._require_job(job_id)
            message = aftercare_summary(job)
            state = job.status.value if hasattr(job.status, 'value') else str(job.status)
        except (AttributeError, KeyError, RuntimeError, ValueError):
            message, state = '', ''
    else:
        message, state = '', ''
    status_label.setText(message)
    status_label.setVisible(bool(message))
    # Basic's old overview showed only "3 av 4"; list the actual families.
    overview = getattr(window, '_a2_overview_labels', {}).get('Valg')
    if overview is not None:
        checks = getattr(window, 'basic_option_checks', {})
        captions = (('dwm', 'DWM'), ('siegfried', 'Siegfried'),
                    ('arkade_noark5', 'Arkade Noark 5'),
                    ('arkade_pronom', 'Arkade PRONOM'))
        chosen = [label for key, label in captions
                  if key in checks and checks[key].isChecked()]
        if chosen:
            summary = f'{len(chosen)} av 4: ' + ', '.join(chosen)
            if overview.text() != summary:
                overview.setText(summary)
    busy = bool(getattr(window, '_worker', None) is not None
                or window.api.running)
    for name in ('a10_basic_all_button', 'v025_a3_basic_button'):
        button = getattr(window, name, None)
        if button is not None:
            match = re.search(r'\((\d+)\)', button.text())
            count = int(match.group(1)) if match else 0
            button.setVisible(count > 0)
    run = getattr(window, 'basic_run_button', None)
    if run is not None:
        run.setVisible(state != 'Ferdig' and not busy)
    stop = getattr(window, 'basic_stop_button', None)
    if stop is not None:
        stop.setVisible(busy)
    extra = getattr(window, 'a14_basic_button', None)
    if extra is not None:
        extra.setEnabled(not busy)
    menu = getattr(window, '_a15_more_actions', {})
    if 'rerun' in menu and run is not None:
        menu['rerun'].setEnabled(state == 'Ferdig' and not busy)


def install_compact_simple_run(window) -> None:
    if getattr(window, '_a15_compact_installed', False):
        return
    group = getattr(window, '_a2_step_groups', {}).get('run')
    if group is None or group.layout() is None:
        return
    layout = group.layout()
    checks = getattr(window, 'basic_option_checks', {})
    if not all(key in checks for key in
               ('dwm', 'siegfried', 'arkade_noark5', 'arkade_pronom')):
        return
    autos = [getattr(window, key, None) for key in
             ('_a3_auto_results', '_a3_auto_details', '_a3_auto_log')]
    if any(widget is None for widget in autos):
        return
    first_at = layout.indexOf(checks['dwm'])
    if first_at < 0:
        return
    window._a15_compact_installed = True
    group.setTitle('3. Velg kontroller og kj\u00f8r')
    layout.setSpacing(6)

    # The existing run-profile chooser moves to the heading; the advanced
    # actions are accessible but do not consume three separate rows.
    heading = QHBoxLayout()
    title = QLabel('Kontroller og kj\u00f8ring', group)
    title.setStyleSheet('font-weight: 600;')
    heading.addWidget(title)
    heading.addStretch(1)
    profile = getattr(window, 'a8_basic_profiles_button', None)
    if profile is not None and layout.indexOf(profile) >= 0:
        layout.removeWidget(profile)
        heading.addWidget(profile)
    more = QToolButton(group)
    more.setText('Flere valg\u2026')
    more.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
    from PySide6.QtWidgets import QMenu
    popup = QMenu(more)
    more.setMenu(popup)
    window._a15_more_actions = {}
    for name, label in (
        ('a6_basic_order_button', 'Endre rekkef\u00f8lge p\u00e5 deljobber\u2026'),
        ('a7_prepare_button', 'Legg til a7-etterbehandling\u2026'),
    ):
        button = getattr(window, name, None)
        if button is not None:
            action = popup.addAction(label)
            action.triggered.connect(lambda _checked=False, b=button: b.click())
            layout.removeWidget(button)
            button.hide()
            window._a15_more_actions[name] = action
    rerun = popup.addAction('Kj\u00f8r hovedkontrollen p\u00e5 nytt\u2026')
    rerun.triggered.connect(lambda: window.basic_run_button.click())
    window._a15_more_actions['rerun'] = rerun
    heading.addWidget(more)
    layout.insertLayout(0, heading)

    old_caption = next((widget for widget in group.findChildren(QLabel)
                        if widget.text() == 'Velg kontroller:'), None)
    if old_caption is not None:
        layout.removeWidget(old_caption)
        old_caption.hide()
    old_auto_caption = getattr(window, '_a3_auto_views_heading', None)
    if old_auto_caption is not None:
        layout.removeWidget(old_auto_caption)
        old_auto_caption.hide()

    left = QGroupBox('Kontroller som skal kj\u00f8res', group)
    left.setObjectName('a15_controls_panel')
    left_layout = QVBoxLayout(left)
    left_layout.setSpacing(4)
    right = QGroupBox('Automatisk \u00e5pning av vinduer', group)
    right.setObjectName('a15_auto_windows_panel')
    right_layout = QVBoxLayout(right)
    right_layout.setSpacing(4)
    for key in ('dwm', 'siegfried', 'arkade_noark5', 'arkade_pronom'):
        _move_from_layout(layout, checks[key], left)
    for widget in autos:
        _move_from_layout(layout, widget, right)
    right_layout.addStretch(1)
    panels = QBoxLayout(QBoxLayout.Direction.LeftToRight)
    panels.setSpacing(8)
    panels.addWidget(left, 1)
    panels.addWidget(right, 1)
    # The old index is invalid after moving widgets out of the layout.
    # Anchor the panels immediately before the (hidden) control description,
    # so the two columns remain ABOVE the run/status controls.
    description = getattr(window, 'basic_workflow_description', None)
    anchor = layout.indexOf(description) if description is not None else -1
    layout.insertLayout(anchor if anchor >= 0 else min(2, layout.count()), panels)
    controller = _ResponsiveRunPanels(group, panels)
    group.installEventFilter(controller)
    window._a15_responsive_panels = controller
    panels.setDirection(QBoxLayout.Direction.TopToBottom if group.width() < 720
                        else QBoxLayout.Direction.LeftToRight)

    # Move result actions into a compact status row while keeping their
    # original buttons, callbacks and enable/disable logic unchanged.
    results = QHBoxLayout()
    for name in ('basic_results_button', 'basic_details_button'):
        widget = getattr(window, name, None)
        if widget is not None:
            _move_nested_widget(layout, widget, results)
    ks = getattr(window, 'a12_ks_basic_button', None)
    if ks is not None and layout.indexOf(ks) >= 0:
        layout.removeWidget(ks)
        results.addWidget(ks)
    status_at = layout.indexOf(window.basic_progress)
    if status_at >= 0:
        layout.insertLayout(status_at + 1, results)

    # Put the two usual batch actions and the addition/repair action together.
    # All-ready/continue disappear when they have zero eligible jobs.
    actions = QHBoxLayout()
    actions.setSpacing(7)
    for name in ('a10_basic_all_button', 'v025_a3_basic_button',
                 'a14_basic_button'):
        button = getattr(window, name, None)
        if button is not None and layout.indexOf(button) >= 0:
            layout.removeWidget(button)
            actions.addWidget(button, 1)
    status = QLabel('', group)
    status.setObjectName('a15_aftercare_status')
    status.setWordWrap(True)
    status.setTextInteractionFlags(
        Qt.TextInteractionFlag.TextSelectableByMouse)
    window._a15_aftercare_status = status
    layout.addWidget(status)
    layout.addLayout(actions)

    # No extra timer: use the established Basic status heartbeat.
    timer = getattr(window, '_basic_timer', None)
    if timer is not None:
        timer.timeout.connect(lambda: _refresh_simple_run(window))
    _refresh_simple_run(window)
