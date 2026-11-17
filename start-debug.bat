@echo off
setlocal EnableExtensions
cd /d "%~dp0"
set "DWM_DEBUG_LOG=%TEMP%\dwm-startup-debug.log"
set "DWM_CRASH_DIAG=1"
set "PYTHONFAULTHANDLER=1"
set "PYTHONUNBUFFERED=1"
echo Running DWM with Python fatal-error diagnostics.
echo Log: %DWM_DEBUG_LOG%
echo.
call "%~dp0start.bat" > "%DWM_DEBUG_LOG%" 2>&1
set "DWM_EXITCODE=%ERRORLEVEL%"
echo.
echo DWM exit code: %DWM_EXITCODE%
echo --- Last diagnostic output ---
powershell -NoProfile -Command "Get-Content -LiteralPath '%DWM_DEBUG_LOG%' -Tail 65" 2>nul
if errorlevel 1 type "%DWM_DEBUG_LOG%"
echo.
echo Full log: %DWM_DEBUG_LOG%
pause
exit /b %DWM_EXITCODE%
