@echo off
chcp 65001 >nul
cd /d "%~dp0"
py tools\upgrade_v021_test_guards_v022_a1.py
if errorlevel 1 (
    echo [FEIL] Oppdatering av historiske versjonstester stoppet.
    pause
    exit /b 1
)
call test.bat
exit /b %ERRORLEVEL%
