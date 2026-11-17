@echo off
setlocal EnableExtensions
cd /d "%~dp0"
set "DWM_SAFE_MODE=1"
echo SAFE MODE: optional file dialog/popup filters and automatic window resizing are off.
echo No job lists or work files will be modified by this setting.
call "%~dp0start-debug.bat"
exit /b %ERRORLEVEL%
