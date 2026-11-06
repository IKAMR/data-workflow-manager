"""v0.1.10-a3: Qt presentation themes. No business/storage role coupling.

Native Windows mode uses the Qt platform style/palette. Dark mode retains the
v0.1.9 appearance; light mode is a full contrasting palette. Accent choices
apply only to dark/light, never override native Windows colours.
"""
from __future__ import annotations

from typing import Mapping

from app.palette_presets_v0110_a3 import (
    palette_mode, palette_colors, custom_defaults, PALETTE_CHOICES,
)

THEME_CHOICES = {
    'system': 'Windows / systemfarger',
    'dark': 'Mørk (dagens)',
    'light': 'Lys',
}
ACCENT_CHOICES = {
    'system': 'Windows-standard (blå)',
    'blue': 'Blå',
    'green': 'Grønn',
    'purple': 'Lilla',
    'pink': 'Rosa',
    'slate': 'Nøytral gråblå',
}

DARK_STYLE = """
QMainWindow, QWidget { background-color: #10141c; color: #dce5f2; }
QMenuBar, QMenu, QToolBar, QStatusBar { background: #161c27; color: #e2e8f0; }
QMenuBar::item:selected, QMenu::item:selected { background: #29496c; }
QDockWidget { color: #dce5f2; font-weight: 600; }
QDockWidget::title { background: #202a39; padding: 7px 9px; text-align: left; }
QTreeWidget, QTableWidget, QPlainTextEdit, QTreeView, QTabWidget::pane {
  background: #151c28; color: #dce5f2; border: 1px solid #2b3748;
  selection-background-color: #315e95; selection-color: white;
  alternate-background-color: #1b2432;
}
QHeaderView::section { background: #202c3c; color: #dce5f2; padding: 7px; border: 0; }
QTabBar::tab { background: #1d2735; color: #b8c5d5; padding: 9px 15px; border: 1px solid #273545; }
QTabBar::tab:selected { background: #325a82; color: white; }
QPushButton { background: #26374b; color: #e8edf5; border: 1px solid #33485f;
  padding: 7px 12px; border-radius: 4px; }
QPushButton:hover { background: #365273; }
QToolButton { background: #26374b; color: #e8edf5; border: 1px solid #33485f; padding: 7px 12px; border-radius: 4px; }
QToolButton:hover { background: #365273; }
QPushButton:disabled { color: #697688; background: #1b2531; }
QLineEdit { background: #1b2634; color: #e2e8f0; border: 1px solid #405066;
  padding: 7px; border-radius: 4px; }
QLabel#subtle { color: #9aabbd; }
QSplitter::handle { background: #34445a; }
QScrollBar:vertical { background: #121923; width: 12px; }
QScrollBar::handle:vertical { background: #40526a; min-height: 22px; border-radius: 4px; }
"""

# The light theme is authored independently of the dark QSS.  The old
# dark-to-light colour substitution kept white selection text on pale backgrounds
# and made selected job rows unreadable.  Use distinct surfaces and a genuinely
# contrasting selection background instead.
LIGHT_STYLE = """
QMainWindow { background-color: #e8edf3; color: #243247; }
QWidget { background-color: #f3f6fb; color: #243247; }
QMenuBar, QMenu, QToolBar, QStatusBar {
  background-color: #dee7f0; color: #243247;
  border-bottom: 1px solid #b9c6d4;
}
QMenuBar::item:selected, QMenu::item:selected {
  background-color: #d5e6f5; color: #243247;
}
QDockWidget { background-color: #f8fafc; color: #243247; font-weight: 600; }
QDockWidget::title {
  background-color: #d7e1ed; color: #243247;
  padding: 7px 9px; text-align: left;
}
QTreeWidget, QTableWidget, QTreeView, QTableView, QListWidget, QListView,
QPlainTextEdit, QTextEdit {
  background-color: #f8fafc; color: #243247;
  border: 1px solid #b8c5d3;
  alternate-background-color: #e9eff6;
  gridline-color: #c4d0dc;
  selection-background-color: #2f6aa5;
  selection-color: #ffffff;
}
QTreeWidget::item:selected, QTableWidget::item:selected,
QTreeView::item:selected, QTableView::item:selected,
QListWidget::item:selected, QListView::item:selected {
  background-color: #2f6aa5; color: #ffffff;
}
QHeaderView::section {
  background-color: #dce5ef; color: #243247;
  padding: 7px; border: 1px solid #c0cddb;
}
QTabWidget::pane { background-color: #f8fafc; border: 1px solid #b8c5d3; }
QTabBar::tab {
  background-color: #dee7f0; color: #344961;
  padding: 9px 15px; border: 1px solid #b8c5d3;
}
QTabBar::tab:selected { background-color: #3976b3; color: #ffffff; }
QTabBar::tab:!selected:hover { background-color: #d5e6f5; }
QPushButton, QToolButton {
  background-color: #dbe5f0; color: #243247;
  border: 1px solid #aebdce; padding: 7px 12px; border-radius: 4px;
}
QPushButton:hover, QToolButton:hover { background-color: #d5e6f5; }
QPushButton:pressed, QToolButton:pressed { background-color: #bacbdc; }
QPushButton:disabled, QToolButton:disabled {
  background-color: #e8edf3; color: #51647b; border-color: #c7d1db;
}
QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox, QDateEdit {
  background-color: #ffffff; color: #243247;
  border: 1px solid #aab9ca; padding: 7px; border-radius: 4px;
  selection-background-color: #2f6aa5; selection-color: #ffffff;
}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus { border: 1px solid #2f6aa5; }
QComboBox QAbstractItemView { background-color: #ffffff; color: #243247;
  selection-background-color: #2f6aa5; selection-color: #ffffff; }
QLabel#subtle { color: #475d75; }
QSplitter::handle { background-color: #b7c5d3; }
QScrollBar:vertical { background-color: #e1e8f0; width: 12px; }
QScrollBar::handle:vertical {
  background-color: #9caec2; min-height: 22px; border-radius: 4px;
}
QScrollBar:horizontal { background-color: #e1e8f0; height: 12px; }
QScrollBar::handle:horizontal { background-color: #9caec2; min-width: 22px; }
"""


def theme_mode(settings: Mapping | None) -> str:
    raw = str((settings or {}).get('appearance_mode') or 'system').strip().lower()
    return raw if raw in THEME_CHOICES else 'system'


def accent_mode(settings: Mapping | None) -> str:
    raw = str((settings or {}).get('qt_accent_color') or 'system').strip().lower()
    return raw if raw in ACCENT_CHOICES else 'system'


def _accent_colors(mode: str, accent: str) -> tuple[str, str, str]:
    # main, selected tab background, hover background
    tones = {
        'system': ('#315e95', '#325a82', '#365273'),
        'blue': ('#316fb5', '#315f9d', '#355f8c'),
        'green': ('#328766', '#287351', '#346c57'),
        'purple': ('#7b5ab3', '#684a9e', '#625081'),
        'pink': ('#b3447c', '#a93576', '#915072'),
        'slate': ('#596d83', '#506178', '#4b5b71'),
    }
    if mode == 'dark':
        return tones[accent]
    # All light-theme selection/active-tab colours must support white text.
    # The third tone is a *light hover* colour, never a selected-row colour.
    light_tones = {
        'system': ('#2f6aa5', '#3976b3', '#d5e6f5'),
        'blue': ('#245c98', '#2863a2', '#dceafa'),
        'green': ('#1b694d', '#206d50', '#dcefe5'),
        'purple': ('#664898', '#6d4b9f', '#dcccf4'),
        'pink': ('#ad246a', '#9f235f', '#f8dbe8'),
        'slate': ('#455970', '#4b6079', '#dae3ed'),
    }
    return light_tones[accent]


def active_palette(settings: Mapping | None) -> dict[str, str] | None:
    """Return a full scheme when selected, else retain the legacy accent-only UI."""
    mode = theme_mode(settings)
    if mode == 'system':
        return None
    preset = palette_mode(settings)
    if preset == 'standard':
        return None
    custom = (settings or {}).get('qt_custom_colors')
    if preset == 'custom':
        try:
            return palette_colors(mode, 'custom', custom)
        except ValueError:
            # An externally corrupted settings file must never prevent startup.
            return palette_colors(mode, 'custom', custom_defaults(mode))
    palette = palette_colors(mode, preset)
    if preset == 'rose':
        # Preserve the readable fix4 Rosa selection colours for compatibility.
        palette['tab'] = '#a93576' if mode == 'dark' else '#9f235f'
    return palette


def _coordinated_css(c: Mapping[str, str]) -> str:
    """Apply the whole composition to controls, not only selection highlights."""
    return f"""
QMainWindow {{ background-color: {c['window']}; color: {c['text']}; }}
QWidget {{ background-color: {c['widget']}; color: {c['text']}; }}
QMenuBar, QMenu, QToolBar, QStatusBar {{ background-color: {c['header']}; color: {c['text']}; border-bottom: 1px solid {c['border']}; }}
QMenuBar::item:selected, QMenu::item:selected {{ background-color: {c['hover']}; color: {c['text']}; }}
QDockWidget {{ background-color: {c['surface']}; color: {c['text']}; }}
QDockWidget::title {{ background-color: {c['dock']}; color: {c['text']}; padding: 7px 9px; text-align: left; }}
QTreeWidget, QTableWidget, QTreeView, QTableView, QListWidget, QListView, QPlainTextEdit, QTextEdit {{
  background-color: {c['surface']}; color: {c['text']}; border: 1px solid {c['border']};
  alternate-background-color: {c['alternate']}; gridline-color: {c['border']};
  selection-background-color: {c['accent']}; selection-color: {c['selected_text']};
}}
QTreeWidget::item:selected, QTableWidget::item:selected, QTreeView::item:selected, QTableView::item:selected,
QListWidget::item:selected, QListView::item:selected {{ background-color: {c['accent']}; color: {c['selected_text']}; }}
QHeaderView::section {{ background-color: {c['header']}; color: {c['text']}; padding: 7px; border: 1px solid {c['border']}; }}
QTabWidget::pane {{ background-color: {c['surface']}; border: 1px solid {c['border']}; }}
QTabBar::tab {{ background-color: {c['header']}; color: {c['text']}; padding: 9px 15px; border: 1px solid {c['border']}; }}
QTabBar::tab:selected {{ background: {c['tab']}; color: {c['selected_text']}; }}
QTabBar::tab:!selected:hover {{ background-color: {c['hover']}; color: {c['text']}; }}
QPushButton, QToolButton {{ background-color: {c['button']}; color: {c['text']}; border: 1px solid {c['border']}; padding: 7px 12px; border-radius: 4px; }}
QPushButton:hover, QToolButton:hover {{ background-color: {c['hover']}; color: {c['text']}; }}
QPushButton:pressed, QToolButton:pressed {{ background-color: {c['chosen']}; color: {c['text']}; }}
QPushButton:disabled, QToolButton:disabled {{ background-color: {c['widget']}; color: {c['subtle']}; border-color: {c['border']}; }}
QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox, QDateEdit {{
  background-color: {c['input']}; color: {c['text']}; border: 1px solid {c['border']}; padding: 7px; border-radius: 4px;
  selection-background-color: {c['accent']}; selection-color: {c['selected_text']};
}}
QComboBox QAbstractItemView {{ background-color: {c['input']}; color: {c['text']}; selection-background-color: {c['accent']}; selection-color: {c['selected_text']}; }}
QLabel#subtle, QLabel#dwmProfileNote, QLabel#dwmSecondary {{ color: {c['subtle']}; }}
QSplitter::handle {{ background-color: {c['border']}; }}
QScrollBar:vertical {{ background-color: {c['widget']}; width: 12px; }}
QScrollBar::handle:vertical {{ background-color: {c['border']}; min-height: 22px; border-radius: 4px; }}
QScrollBar:horizontal {{ background-color: {c['widget']}; height: 12px; }}
QScrollBar::handle:horizontal {{ background-color: {c['border']}; min-width: 22px; }}
QFrame#dwmSetupInfo, QFrame#dwmProfileSummary, QFrame#dwmStorageProfileCard {{ background-color: {c['panel']}; border: 1px solid {c['border']}; border-radius: 6px; }}
QFrame#dwmStorageProfileCard[chosen="true"] {{ background-color: {c['chosen']}; border: 2px solid {c['accent']}; }}
QFrame#dwmStorageProfileCard QLabel, QFrame#dwmStorageProfileCard QRadioButton,
QFrame#dwmSetupInfo QLabel, QFrame#dwmProfileSummary QLabel {{ background-color: transparent; }}
QWidget#DwmSafeDockTitle {{ background-color: {c['dock']}; }}
QWidget#DwmSafeDockTitle QLabel {{ color: {c['text']}; background-color: transparent; font-weight: 600; }}
QLabel#dwmRecommendation {{ color: {c['accent']}; font-weight: 600; font-size: 10px; }}
"""


def stylesheet_for(settings: Mapping | None) -> str:
    mode = theme_mode(settings)
    if mode == 'system':
        return ''  # native Qt/Windows appearance; do not force dark colours
    accent = accent_mode(settings)
    css = DARK_STYLE if mode == 'dark' else LIGHT_STYLE
    selected, tab, hover = _accent_colors(mode, accent)
    default_selected, default_tab, default_hover = _accent_colors(mode, 'system')
    css = (css.replace(default_selected, selected)
           .replace(default_tab, tab)
           .replace(default_hover, hover))
    if mode == 'dark':
        panel, border, chosen, secondary, badge = '#192638', '#334d68', '#243b56', '#bbcadc', '#b7d9fb'
        dock, text = '#202a39', '#dce5f2'
        sel_text = 'white'
    else:
        panel, border, chosen, secondary, badge = '#e3ebf4', '#acbecf', '#d6e4f2', '#405770', '#245b91'
        dock, text = '#d7e1ed', '#243247'
        sel_text = '#ffffff'
    return css + """
QFrame#dwmSetupInfo, QFrame#dwmProfileSummary {
  background-color: %(panel)s; border: 1px solid %(border)s; border-radius: 6px;
}
QFrame#dwmStorageProfileCard {
  background-color: %(panel)s; border: 1px solid %(border)s; border-radius: 7px;
}
QFrame#dwmStorageProfileCard[chosen="true"] {
  background-color: %(chosen)s; border: 2px solid %(selected)s;
}
QFrame#dwmStorageProfileCard QLabel, QFrame#dwmStorageProfileCard QRadioButton,
QFrame#dwmSetupInfo QLabel, QFrame#dwmProfileSummary QLabel {
  background-color: transparent;
}
QWidget#DwmSafeDockTitle { background-color: %(dock)s; }
QWidget#DwmSafeDockTitle QLabel { color: %(text)s; background-color: transparent; font-weight: 600; }
QLabel#dwmRecommendation { color: %(badge)s; font-weight: 600; font-size: 10px; }
QLabel#dwmProfileNote, QLabel#dwmSecondary { color: %(secondary)s; }
QTabBar::tab:selected { background: %(tab)s; color: %(sel_text)s; }
QTreeWidget::item:selected, QTableWidget::item:selected { color: %(sel_text)s; }
""" % dict(panel=panel, border=border, chosen=chosen, selected=selected,
           badge=badge, secondary=secondary, tab=tab, sel_text=sel_text,
           dock=dock, text=text) + (_coordinated_css(active_palette(settings)) if active_palette(settings) else '')


def apply_appearance(application, settings: Mapping | None) -> None:
    """Apply a saved selection immediately; Qt is imported only at runtime."""
    from PySide6.QtGui import QColor, QPalette
    from PySide6.QtWidgets import QStyleFactory
    mode = theme_mode(settings)
    if not hasattr(application, '_dwm_native_palette'):
        application._dwm_native_palette = QPalette(application.palette())
        application._dwm_native_style = application.style().objectName()
    if mode == 'system':
        native_style = application._dwm_native_style
        if native_style and native_style.casefold() in {x.casefold() for x in QStyleFactory.keys()}:
            application.setStyle(native_style)
        application.setPalette(QPalette(application._dwm_native_palette))
        application.setStyleSheet('')
        return
    application.setStyle('Fusion')
    palette = QPalette()
    colors = {
        'dark': {'window': '#10141c', 'text': '#dce5f2', 'base': '#151c28',
                 'alternate': '#1b2432', 'button': '#26374b', 'placeholder': '#9aabbd'},
        'light': {'window': '#e8edf3', 'text': '#243247', 'base': '#f8fafc',
                  'alternate': '#e9eff6', 'button': '#dbe5f0', 'placeholder': '#51647b'},
    }[mode]
    accent, _, _ = _accent_colors(mode, accent_mode(settings))
    active = active_palette(settings)
    if active:
        colors = {
            'window': active['window'], 'text': active['text'],
            'base': active['surface'], 'alternate': active['alternate'],
            'button': active['button'], 'placeholder': active['placeholder'],
        }
        accent = active['accent']
    fg = active['selected_text'] if active else '#ffffff'
    for role, value in (
        (QPalette.ColorRole.Window, colors['window']),
        (QPalette.ColorRole.WindowText, colors['text']),
        (QPalette.ColorRole.Base, colors['base']),
        (QPalette.ColorRole.AlternateBase, colors['alternate']),
        (QPalette.ColorRole.Text, colors['text']),
        (QPalette.ColorRole.Button, colors['button']),
        (QPalette.ColorRole.ButtonText, colors['text']),
        (QPalette.ColorRole.Highlight, accent),
        (QPalette.ColorRole.HighlightedText, fg),
        (QPalette.ColorRole.ToolTipBase, colors['base']),
        (QPalette.ColorRole.ToolTipText, colors['text']),
        (QPalette.ColorRole.PlaceholderText, colors['placeholder']),
    ):
        palette.setColor(role, QColor(value))
    application.setPalette(palette)
    application.setStyleSheet(stylesheet_for(settings))
