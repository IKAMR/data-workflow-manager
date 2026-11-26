"""Make the existing Advanced-mode history/status resize handle visible.

Only the vertical QSplitter inside Kjoereloep is styled. No widget geometry,
dock state, saved sizes, or other splitters are changed.
"""
from __future__ import annotations


def splitter_handle_css(dark: bool = False) -> str:
    border = '#667f9c' if dark else '#8296aa'
    hover = '#8eb9e5' if dark else '#4579a9'
    return (
        'QSplitter#dwm_a16_run_history_splitter::handle:vertical {'
        f'background-color: {border}; min-height: 5px; height: 5px;'
        ' border-top: 1px solid rgba(0,0,0,38);'
        ' border-bottom: 1px solid rgba(0,0,0,38);'
        '}'
        'QSplitter#dwm_a16_run_history_splitter::handle:vertical:hover {'
        f'background-color: {hover};'
        '}'
    )


def install_visible_run_history_splitter(window) -> bool:
    """Invoke after the main window has constructed its internal splitter."""
    splitter = getattr(window, 'run_history_splitter', None)
    if splitter is None:
        return False
    splitter.setObjectName('dwm_a16_run_history_splitter')
    splitter.setHandleWidth(6)
    # Styling only this widget avoids changing the window's other splitters.
    # Palette is intentionally neutral and contrasted in both light/dark GUI.
    splitter.setStyleSheet(splitter_handle_css())
    return True
