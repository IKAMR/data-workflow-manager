"""Qt desktop entry point with v0.2.0-a1 startup navigation."""
from __future__ import annotations

import sys


def main() -> int:
    try:
        from PySide6.QtWidgets import QApplication, QMessageBox
    except ImportError:
        print('PySide6 mangler. Kjør: py -m pip install -r requirements-gui.txt', file=sys.stderr)
        return 2
    from gui_qt.bootstrap_v0113_a1 import install
    install()
    from gui_qt.basic_main_v0113_a2 import DwmMainWindow
    from gui_qt.canonical_results_v0115_a3 import install_canonical_results_menu
    from gui_qt.start_shell_v020_a1 import install_setup_tab, install_start_navigation
    from app.workbench_api_v0111_a2 import DwmWorkbenchAPI
    from gui_qt.appearance_v0110_a3 import apply_appearance

    application = QApplication(sys.argv)
    application.setOrganizationName('IKAMR')
    application.setApplicationName('Data Workflow Manager')
    api = DwmWorkbenchAPI()
    apply_appearance(application, api.settings)
    install_setup_tab()
    window = DwmMainWindow(api)
    install_canonical_results_menu(window)
    install_start_navigation(window)
    window.show()
    if len(sys.argv) > 1:
        try:
            window.open_job_list(sys.argv[1])
        except Exception as exc:
            QMessageBox.warning(window, 'Kunne ikke åpne jobbliste', str(exc))
    return application.exec()


if __name__ == '__main__':
    raise SystemExit(main())
