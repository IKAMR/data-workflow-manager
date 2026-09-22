@echo off

cd /d "%~dp0"
set "PYTHON_GIL=1"

REM ------------------------------------------------------------
REM LibreOffice-sjekk var tidligere brukt i oppsettet.
REM Den er ikke nodvendig i start.bat for Data Workflow Manager
REM sa lenge ingen aktive operasjoner krever LibreOffice.
REM ------------------------------------------------------------

REM Start Data Workflow Manager.
REM Bruker py-launcher som ogsa kontrolleres av install.bat.
py main.py
