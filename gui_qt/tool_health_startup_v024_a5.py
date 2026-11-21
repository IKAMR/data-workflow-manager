"""Nonblocking startup tool status; all GUI/settings mutations on Qt main thread."""
from __future__ import annotations

from queue import Empty, Queue
from threading import Thread

from app.tool_health_v024_a5 import check_both_tools, persist_discovered_paths


def schedule_tool_check(window, api, *, on_done=None) -> bool:
    """Start one bounded background check; no automatic installs/network I/O."""
    from PySide6.QtCore import QTimer

    if getattr(api, '_v024_a5_probe_running', False):
        return False
    api._v024_a5_probe_running = True
    results: Queue = Queue(maxsize=1)
    snapshot = dict(api.settings)
    timer = QTimer(window)
    timer.setInterval(150)
    window._v024_a5_tool_probe_timer = timer  # keep Qt object alive

    def execute():
        try:
            checks = check_both_tools(snapshot)
            results.put((checks, ''))
        except Exception as exc:
            results.put((None, str(exc)))

    def update():
        try:
            checks, error = results.get_nowait()
        except Empty:
            return
        timer.stop()
        timer.deleteLater()
        api._v024_a5_probe_running = False
        if checks is not None:
            api._v024_a5_tool_health = checks
            # Persist automatically discovered paths *only when currently unset*.
            # Never touch Source, Work, .n5jobs, evidence or ongoing job state.
            persist_discovered_paths(api, checks)
            ok = [name for name, status in checks.items() if status.usable]
            summary = f'Verktøy kontrollert: {len(ok)}/2 klare. Se Setup → Eksterne verktøy.'
        else:
            summary = 'Verktøykontroll kunne ikke fullføres: ' + error[:180]
        try:
            if hasattr(window, 'statusBar'):
                window.statusBar().showMessage(summary, 12000)
            # Also refresh an already-open modal Setup dialog if the startup
            # check completed while the operator was viewing its tool section.
            if hasattr(window, 'findChildren'):
                from PySide6.QtWidgets import QDialog
                for dialog in window.findChildren(QDialog):
                    refresh = getattr(dialog, '_v024_a5_refresh_health', None)
                    if callable(refresh):
                        refresh()
            if on_done is not None:
                on_done(checks)
        except RuntimeError:
            pass  # window/dialog closed during async probe

    timer.timeout.connect(update)
    timer.start()
    Thread(target=execute, name='dwm-a5-tool-health', daemon=True).start()
    return True
