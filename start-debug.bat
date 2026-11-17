@echo off
setlocal EnableExtensions DisableDelayedExpansion
cd /d "%~dp0"
set "DWM_CRASH_DIAG=1"
set "PYTHONFAULTHANDLER=1"
set "PYTHONUNBUFFERED=1"

REM A separate file PER launch prevents a successful safe run from erasing
REM the diagnostic evidence of an earlier Windows access violation.
set "DWM_DEBUG_DIR=%TEMP%\dwm-startup-logs"
if not exist "%DWM_DEBUG_DIR%" mkdir "%DWM_DEBUG_DIR%"
if errorlevel 1 (
 echo [ERROR] Cannot create debug log directory: %DWM_DEBUG_DIR%
 pause
 exit /b 2
)
set "DWM_LOG_STAMP="
for /f %%T in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMdd_HHmmss_fff"') do set "DWM_LOG_STAMP=%%T"
if not defined DWM_LOG_STAMP set "DWM_LOG_STAMP=%RANDOM%"
set "DWM_DEBUG_LOG=%DWM_DEBUG_DIR%\dwm-startup-%DWM_LOG_STAMP%-%RANDOM%.log"

echo Running DWM with native-crash diagnostics.
echo Each run keeps its own log: %DWM_DEBUG_LOG%
echo.
call "%~dp0start.bat" > "%DWM_DEBUG_LOG%" 2>&1
set "DWM_EXITCODE=%ERRORLEVEL%"
echo.
echo DWM exit code: %DWM_EXITCODE%
echo --- Last diagnostic output ---
powershell -NoProfile -Command "Get-Content -LiteralPath '%DWM_DEBUG_LOG%' -Tail 80" 2>nul
if errorlevel 1 type "%DWM_DEBUG_LOG%"
echo.
echo Complete log: %DWM_DEBUG_LOG%
pause
exit /b %DWM_EXITCODE%
