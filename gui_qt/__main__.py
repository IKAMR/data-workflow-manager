"""CLI entry point for the independent Qt desktop frontend."""
from __future__ import annotations

import sys


def main() -> int:
    try:
        from PySide6.QtWidgets import QApplication, QMessageBox
    except ImportError:
        print('PySide6 mangler. Kjør: py -m pip install -r requirements-gui.txt', file=sys.stderr)
        return 2
    from gui_qt.main_window import DwmMainWindow
    from app.workbench_api_v018_a3 import DwmWorkbenchAPI

    application = QApplication(sys.argv)
    application.setOrganizationName('IKAMR')
    application.setApplicationName('Data Workflow Manager')
    application.setStyle('Fusion')
    window = DwmMainWindow(DwmWorkbenchAPI())
    window.show()
    if len(sys.argv) > 1:
        try:
            window.open_job_list(sys.argv[1])
        except Exception as exc:
            QMessageBox.warning(window, 'Kunne ikke åpne jobbliste', str(exc))
    return application.exec()


if __name__ == '__main__':
    raise SystemExit(main())
