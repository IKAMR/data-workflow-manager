@echo off
cd /d "%~dp0"
set "PYTHON_GIL=1"
py main.py
exit /b %errorlevel%
