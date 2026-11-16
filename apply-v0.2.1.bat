@echo off
cd /d "%~dp0"
py apply-v0.2.1.py
if errorlevel 1 (
    echo [FEIL] Release-oppdatering stoppet. Sjekk meldingen over.
    pause
    exit /b 1
)
echo [OK] Release-oppdatering anvendt. Kjor deretter test.bat.
pause
