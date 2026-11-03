@echo off
cd /d "%~dp0"
set "PYTHON_GIL=1"
REM Classic v0.1.7 CustomTkinter layout, without v0.1.8-a2 EmbeddedJobsMixin.
py -m gui.legacy_runtime_v018_a4
exit /b %errorlevel%
