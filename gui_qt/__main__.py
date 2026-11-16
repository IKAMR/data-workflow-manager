"""Qt desktop entry point with v0.2.2-a1 depot organization profiles."""
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
    from gui_qt.main_v020_a6 import DwmMainWindow
    from gui_qt.canonical_results_v0115_a3 import install_canonical_results_menu
    from gui_qt.start_shell_v020_a1 import install_setup_tab, install_start_navigation
    from gui_qt.production_home_v020_a2 import ProductionStartPage, install_integrated_home
    from gui_qt.depot_profile_v022_a1 import install_depot_profile_controls
    from app.workbench_api_v020_a2 import DwmWorkbenchAPI
    from gui_qt.appearance_v0110_a3 import apply_appearance
    from gui_qt.combobox_popup_v020_a2 import install_dropdown_positioning

    application = QApplication(sys.argv)
    application.setOrganizationName('IKAMR')
    application.setApplicationName('Data Workflow Manager')
    api = DwmWorkbenchAPI()
    apply_appearance(application, api.settings)
    install_setup_tab()
    window = DwmMainWindow(api)
    install_canonical_results_menu(window)
    window.v020_start_page_factory = ProductionStartPage
    install_start_navigation(window)
    install_integrated_home(window)
    if not install_depot_profile_controls(window):
        QMessageBox.warning(window, 'Depotprofil',
                            'Rapporteringsarbeidsflaten mangler. Depotprofil kan ikke åpnes.')
    install_dropdown_positioning(application, window)
    window.show()
    if len(sys.argv) > 1:
        try:
            window.open_job_list(sys.argv[1])
        except Exception as exc:
            QMessageBox.warning(window, 'Kunne ikke åpne jobbliste', str(exc))
    return application.exec()


if __name__ == '__main__':
    raise SystemExit(main())
