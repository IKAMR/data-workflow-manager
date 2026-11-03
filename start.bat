@echo off
setlocal EnableExtensions
cd /d "%~dp0"
set "PYTHON_GIL=1"

REM PySide6 supports ordinary CPython on Windows, not Python 3.14t.
REM Use an explicit ordinary Python interpreter; never use the default py here.
set "QT_PY_FLAG="
for %%V in (3.14 3.13 3.12 3.11 3.10) do (
 if not defined QT_PY_FLAG (
  py -%%V -c "import sys,sysconfig; sys.exit(1 if sysconfig.get_config_var('Py_GIL_DISABLED') else 0)" >nul 2>&1
  if not errorlevel 1 set "QT_PY_FLAG=-%%V"
 )
)
if not defined QT_PY_FLAG (
 echo [FEIL] PySide6 krever vanlig Python, ikke Python 3.14t.
 echo Installer vanlig 64-bit Python 3.14 fra https://www.python.org/downloads/windows/
 echo Behold den eksisterende Python 3.14t-installasjonen.
 echo Kontroller installerte versjoner med: py -0p
 pause
 exit /b 2
)

py %QT_PY_FLAG% -c "from PySide6.QtWidgets import QApplication" >nul 2>&1
if errorlevel 1 (
 echo [FEIL] PySide6 mangler for Python %QT_PY_FLAG%.
 echo Kjor install.bat og velg GUI eller GUI + CLI.
 echo Gammelt GUI kan startes med start-legacy.bat.
 pause
 exit /b 2
)
py %QT_PY_FLAG% -m gui_qt %*
exit /b %errorlevel%
