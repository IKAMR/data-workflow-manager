"""CLI entry point for the independent Qt desktop frontend."""
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
    from app.workbench_api_v0111_a2 import DwmWorkbenchAPI
    from gui_qt.appearance_v0110_a3 import apply_appearance

    application = QApplication(sys.argv)
    application.setOrganizationName('IKAMR')
    application.setApplicationName('Data Workflow Manager')
    api = DwmWorkbenchAPI()
    apply_appearance(application, api.settings)
    window = DwmMainWindow(api)
    install_canonical_results_menu(window)
    window.show()
    if len(sys.argv) > 1:
        try:
            window.open_job_list(sys.argv[1])
        except Exception as exc:
            QMessageBox.warning(window, 'Kunne ikke åpne jobbliste', str(exc))
    return application.exec()


if __name__ == '__main__':
    raise SystemExit(main())
