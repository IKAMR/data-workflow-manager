@echo off
chcp 65001 >nul

set "PYTHON_GIL=1"
set "APP_VERSION=?"
for /f "delims=" %%V in ('py -c "from version import VERSION; print(VERSION)"') do set "APP_VERSION=%%V"

title Noark 5 Workflow Manager v%APP_VERSION% - Tester
mode con: cols=140 lines=45

if exist "docs\test-results\.last-test-summary.txt" del /q "docs\test-results\.last-test-summary.txt" >nul 2>&1

echo.
echo ========================================
echo   Noark 5 Workflow Manager - Tester
echo   Versjon: %APP_VERSION%
echo ========================================
echo.

py tests\run_tests.py
set "EXITCODE=%ERRORLEVEL%"

echo.
if "%EXITCODE%"=="0" (
    echo [OK] Alle tester bestatt.
) else (
    echo [FEIL] En eller flere tester feilet.
)

set "TOTAL=?"
set "PASSED=?"
set "FAILED=?"
set "ERRORS=?"
set "SKIPPED=?"
if exist "docs\test-results\.last-test-summary.txt" (
    for /f "usebackq tokens=1,* delims==" %%A in ("docs\test-results\.last-test-summary.txt") do (
        if "%%A"=="TOTAL" set "TOTAL=%%B"
        if "%%A"=="PASSED" set "PASSED=%%B"
        if "%%A"=="FAILED" set "FAILED=%%B"
        if "%%A"=="ERRORS" set "ERRORS=%%B"
        if "%%A"=="SKIPPED" set "SKIPPED=%%B"
    )
)

echo.
echo ========================================
echo   Testoppsummering v%APP_VERSION%
echo ========================================
echo   Tester kjort:        %TOTAL%
echo   Bestatt:             %PASSED%
echo   Feilet:              %FAILED%
echo   Feil under kjoring:  %ERRORS%
echo   Hoppet over:         %SKIPPED%
echo ========================================
echo.
echo   Rapport: docs\test-results\v%APP_VERSION%.md
echo.
pause
exit /b %EXITCODE%
