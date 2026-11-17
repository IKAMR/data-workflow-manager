"""Qt desktop entry point with a1 depot profiles and a1.2 shared multi-job Basic."""
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
        print('PySide6 mangler. Kjør: py -m pip install -r requirements-gui.txt', file=sys.stderr)
        return 2
    _boot_phase("02 PySide6 imported, before DWM bootstrap")
    from gui_qt.bootstrap_v0113_a1 import install
    install()
    _boot_phase("03 Bootstrap installed, importing DWM GUI classes")
    from gui_qt.main_v020_a6 import DwmMainWindow as _StableDwmMainWindow
    from gui_qt.basic_multijob_v022_a1_2 import DwmMainWindow
    if not issubclass(DwmMainWindow, _StableDwmMainWindow):
        raise RuntimeError('Enkel flerjobbvisning må utvide det eksisterende Qt-hovedvinduet')
    from gui_qt.canonical_results_v0115_a3 import install_canonical_results_menu
    from gui_qt.start_shell_v020_a1 import install_setup_tab, install_start_navigation
    from gui_qt.production_home_v020_a2 import ProductionStartPage, install_integrated_home
    from gui_qt.depot_profile_v022_a1 import install_depot_profile_controls
    from app.workbench_api_v020_a2 import DwmWorkbenchAPI
    from gui_qt.appearance_v0110_a3 import apply_appearance
    from gui_qt.combobox_popup_v020_a2 import install_dropdown_positioning
    from gui_qt.file_dialog_contrast_v022_a1_10 import install_file_dialog_navigation_contrast

    _boot_phase("04 Imports complete, before QApplication")
    safe_mode = os.environ.get("DWM_SAFE_MODE") == "1"
    if safe_mode:
        _boot_phase("SAFE mode: skip optional global GUI filters and automatic resizing")
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
    if not safe_mode:
        install_file_dialog_navigation_contrast(application)
    _boot_phase("10 File-dialog filter stage complete")
    install_setup_tab()
    from gui_qt.setup_reset_v022_a1_5 import install_setup_reset_actions
    install_setup_reset_actions()
    _boot_phase("11 Setup hooks installed, before main-window construction")
    window = DwmMainWindow(api)
    if safe_mode:
        # Avoid optional timer-based window resizing without saving a setting.
        window._v022_fit_ready = False
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
                            'Rapporteringsarbeidsflaten mangler. Depotprofil kan ikke åpnes.')
    if not safe_mode:
        install_dropdown_positioning(application, window)
    _boot_phase("16 Optional popup filter stage complete")
    _boot_phase("17 Before window.show")
    window.show()
    _boot_phase("18 window.show completed")
    if len(sys.argv) > 1:
        try:
            window.open_job_list(sys.argv[1])
        except Exception as exc:
            QMessageBox.warning(window, 'Kunne ikke åpne jobbliste', str(exc))
    _boot_phase("19 Entering Qt event loop")
    code = application.exec()
    _boot_phase("20 Qt event loop returned with code " + str(code))
    return code


if __name__ == '__main__':
    raise SystemExit(main())
