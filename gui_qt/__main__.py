"""Qt desktop entry point with v0.2.4-a2 resume/reset and a1 fixes."""
from __future__ import annotations

import sys
import os


def _boot_phase(label: str) -> None:
    """Flush a short milestone only when explicitly diagnosing Windows startup."""
    if os.environ.get("DWM_CRASH_DIAG") == "1":
        sys.stderr.write("[DWM-BOOT] " + label + "\n")
        sys.stderr.flush()


def main() -> int:
    _boot_phase("01 Python launched, before Qt import: " + sys.version.split()[0])
    try:
        from PySide6.QtWidgets import QApplication, QMessageBox
    except ImportError:
        print('PySide6 mangler. Kj\u00f8r: py -m pip install -r requirements-gui.txt', file=sys.stderr)
        return 2
    _boot_phase("02 PySide6 imported, before DWM bootstrap")
    from gui_qt.bootstrap_v0113_a1 import install
    install()
    _boot_phase("03 Bootstrap installed, importing DWM GUI classes")
    from gui_qt.main_v020_a6 import DwmMainWindow as _StableDwmMainWindow
    from gui_qt.basic_multijob_v022_a1_2 import DwmMainWindow as _MultiJobDwmMainWindow
    from gui_qt.main_v022_a10 import DwmMainWindow as _A10DwmMainWindow
    from gui_qt.main_v022_a11 import DwmMainWindow as _A11DwmMainWindow
    from gui_qt.main_v022_a12 import DwmMainWindow as _A12DwmMainWindow
    from gui_qt.main_v023_a4 import DwmMainWindow
    from gui_qt.main_v024_a1 import DwmMainWindow as _A1Window
    from gui_qt.main_v024_a2 import DwmMainWindow as _A2Window
    DwmMainWindow = _A2Window
    if (not issubclass(DwmMainWindow, _StableDwmMainWindow)
            or not issubclass(DwmMainWindow, _MultiJobDwmMainWindow)
            or not issubclass(DwmMainWindow, _A10DwmMainWindow)
            or not issubclass(DwmMainWindow, _A11DwmMainWindow)
            or not issubclass(DwmMainWindow, _A12DwmMainWindow)):
        raise RuntimeError('Enkel flerjobbvisning m\u00e5 utvide det eksisterende Qt-hovedvinduet')
    from gui_qt.canonical_results_v0115_a3 import install_canonical_results_menu
    from gui_qt.start_shell_v020_a1 import install_setup_tab, install_start_navigation
    from gui_qt.production_home_v020_a2 import ProductionStartPage, install_integrated_home
    from gui_qt.depot_profile_v022_a1 import install_depot_profile_controls
    from app.workbench_api_v020_a2 import DwmWorkbenchAPI
    from app.workbench_api_v024_a2 import DwmWorkbenchAPI as _A2WorkbenchAPI
    DwmWorkbenchAPI = _A2WorkbenchAPI
    from gui_qt.appearance_v0110_a3 import apply_appearance
    from gui_qt.qt_startup_policy_v022_a1_14 import select_qt_startup_features

    _boot_phase("04 Imports complete, before QApplication")
    features = select_qt_startup_features(os.environ)
    _boot_phase(
        "Qt startup profile: "
        + ("SAFE" if features.safe_mode else "STABLE")
        + f", file_dialog_filter={int(features.dialog_filter)}"
        + f", popup_filter={int(features.popup_filter)}"
        + f", basic_auto_fit={int(features.basic_auto_fit)}"
    )
    application = QApplication(sys.argv)
    _boot_phase("05 QApplication created")
    application.setOrganizationName('IKAMR')
    application.setApplicationName('Data Workflow Manager')
    _boot_phase("06 Before DwmWorkbenchAPI construction")
    api = DwmWorkbenchAPI()
    _boot_phase("07 DwmWorkbenchAPI constructed")
    _boot_phase("08 Before applying appearance")
    apply_appearance(application, api.settings)
    _boot_phase("09 Appearance applied")
    if features.dialog_filter:
        from gui_qt.file_dialog_contrast_v022_a1_10 import install_file_dialog_navigation_contrast
        install_file_dialog_navigation_contrast(application)
    _boot_phase("10 File-dialog filter stage complete")
    install_setup_tab()
    from gui_qt.setup_reset_v022_a1_5 import install_setup_reset_actions
    install_setup_reset_actions()
    _boot_phase("11 Setup hooks installed, before main-window construction")
    window = DwmMainWindow(api)
    if not features.basic_auto_fit:
        window._v022_fit_ready = False
        fit_control = getattr(window, 'v022_fit_window_button', None)
        if fit_control is not None:
            fit_control.hide()
    _boot_phase("12 Main window constructed")
    install_canonical_results_menu(window)
    _boot_phase("13 Result navigation installed")
    window.v020_start_page_factory = ProductionStartPage
    install_start_navigation(window)
    _boot_phase("14 Start navigation installed")
    install_integrated_home(window)
    _boot_phase("15 Integrated home installed")
    if not install_depot_profile_controls(window):
        QMessageBox.warning(window, 'Depotprofil',
                            'Rapporteringsarbeidsflaten mangler. Depotprofil kan ikke \u00e5pnes.')
    if features.popup_filter:
        from gui_qt.combobox_popup_v020_a2 import install_dropdown_positioning
        install_dropdown_positioning(application, window)
    _boot_phase("16 Optional popup filter stage complete")
    _boot_phase("17 Before window.show")
    window.show()
    _boot_phase("18 window.show completed")
    if len(sys.argv) > 1:
        try:
            window.open_job_list(sys.argv[1])
        except Exception as exc:
            QMessageBox.warning(window, 'Kunne ikke \u00e5pne jobbliste', str(exc))
    _boot_phase("19 Entering Qt event loop")
    code = application.exec()
    _boot_phase("20 Qt event loop returned with code " + str(code))
    return code


if __name__ == '__main__':
    raise SystemExit(main())
