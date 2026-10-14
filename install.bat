@echo off
setlocal EnableExtensions
chcp 65001 >nul
cd /d "%~dp0"

set "PYTHON_GIL=1"

set "APP_DIR=%LOCALAPPDATA%\Programs\Noark5WorkflowManager"
set "N5WF_BIN=%APP_DIR%\bin"
set "N5WF_LAUNCHER=%N5WF_BIN%\n5wf.cmd"
set "STATE_FILE=%APP_DIR%\install-state.json"
set "MODE=%~1"
set "CURRENT_GUI=0"
set "CURRENT_CLI=0"

call :read_state

if /I "%MODE%"=="all" goto mode_ok
if /I "%MODE%"=="gui" goto mode_ok
if /I "%MODE%"=="cli" goto mode_ok
if not "%MODE%"=="" goto usage

echo Noark 5 Workflow Manager - installasjon
echo.
echo Registrert status:
echo   Core: %CURRENT_CORE%
echo   GUI:  %CURRENT_GUI%
echo   CLI:  %CURRENT_CLI%
echo.
echo   1. GUI + CLI
echo   2. GUI
echo   3. CLI
echo   4. Avbryt
echo.
set /p "CHOICE=Velg 1-4: "
if "%CHOICE%"=="1" set "MODE=all"
if "%CHOICE%"=="2" set "MODE=gui"
if "%CHOICE%"=="3" set "MODE=cli"
if "%CHOICE%"=="4" exit /b 0
if not defined MODE (
 echo [FEIL] Ugyldig valg.
 pause
 exit /b 2
)

:mode_ok
echo.
echo Installerer profil: %MODE%
echo.
echo Sjekker Python...
py --version >nul 2>&1
if errorlevel 1 (
 echo [FEIL] Python launcher "py" ble ikke funnet.
 pause
 exit /b 1
)
echo [OK] Python funnet via py launcher.

echo.
echo Installerer felles Core-avhengigheter...
py -m pip install --disable-pip-version-check --user -r requirements-core.txt
if errorlevel 1 goto install_error

set "NEW_GUI=%CURRENT_GUI%"
set "NEW_CLI=%CURRENT_CLI%"

if /I "%MODE%"=="gui" set "NEW_GUI=1"
if /I "%MODE%"=="cli" set "NEW_CLI=1"
if /I "%MODE%"=="all" (
 set "NEW_GUI=1"
 set "NEW_CLI=1"
)

if /I "%MODE%"=="gui" call :install_gui
if /I "%MODE%"=="all" call :install_gui
if errorlevel 1 goto install_error

if /I "%MODE%"=="cli" call :install_cli
if /I "%MODE%"=="all" call :install_cli
if errorlevel 1 goto install_error

call :write_state
if errorlevel 1 (
 echo [FEIL] Klarte ikke aa skrive installasjonsstatus.
 pause
 exit /b 1
)

echo.
echo [OK] Installasjon fullfoert: %MODE%
echo Registrert status:
echo   Core: 1
echo   GUI:  %NEW_GUI%
echo   CLI:  %NEW_CLI%
if "%NEW_GUI%"=="1" echo GUI startes med start.bat
if "%NEW_CLI%"=="1" echo Lukk gamle terminaler, aapne en ny og test: n5wf --version
echo.
pause
exit /b 0

:install_gui
echo.
echo Installerer GUI-avhengigheter...
py -m pip install --disable-pip-version-check --user -r requirements-gui.txt
if errorlevel 1 exit /b 1
echo.
echo Installerer PDF-avhengigheter for rapporteksport...
py -m pip install --disable-pip-version-check --user reportlab beautifulsoup4
if errorlevel 1 exit /b 1
echo [OK] PDF-avhengigheter installert.
exit /b 0

:install_cli
echo.
echo Installerer CLI-pakken...
py -m pip install --disable-pip-version-check --user --no-deps -e .
if errorlevel 1 exit /b 1

if not exist "%N5WF_BIN%" mkdir "%N5WF_BIN%"
> "%N5WF_LAUNCHER%" echo @echo off
>> "%N5WF_LAUNCHER%" echo set "PYTHON_GIL=1"
>> "%N5WF_LAUNCHER%" echo py -m noark5_workflow.cli %%*
>> "%N5WF_LAUNCHER%" echo exit /b %%errorlevel%%
if not exist "%N5WF_LAUNCHER%" exit /b 1

call "%N5WF_LAUNCHER%" --version
if errorlevel 1 exit /b 1

echo [OK] n5wf-launcher virker.

powershell -NoProfile -ExecutionPolicy Bypass -Command "$bin='%N5WF_BIN%'; $p=[Environment]::GetEnvironmentVariable('Path','User'); if($null -eq $p){$p=''}; $parts=@(); foreach($item in $p.Split(';')){if(-not [string]::IsNullOrWhiteSpace($item)){$parts += $item.Trim()}}; $found=$false; foreach($item in $parts){if([string]::Equals($item.TrimEnd('\'),$bin.TrimEnd('\'),[StringComparison]::OrdinalIgnoreCase)){$found=$true}}; if(-not $found){$new=if($p.Trim()){$p.TrimEnd(';')+';'+$bin}else{$bin}; [Environment]::SetEnvironmentVariable('Path',$new,'User'); Write-Host '[OK] Launcher-mappen er lagt til i bruker-PATH.'}else{Write-Host '[OK] Launcher-mappen finnes allerede i bruker-PATH.'}"
exit /b %errorlevel%

:read_state
if exist "%STATE_FILE%" (
 for /f "tokens=1,2" %%A in ('powershell -NoProfile -Command "$s=ConvertFrom-Json -InputObject (Get-Content -Raw -LiteralPath '%STATE_FILE%'); $g=if($s.gui){1}else{0}; $c=if($s.cli){1}else{0}; Write-Output ($g.ToString()+' '+$c.ToString())"') do (
  set "CURRENT_GUI=%%A"
  set "CURRENT_CLI=%%B"
 )
) else (
 rem Migrering fra a7: eksisterende launcher betyr at CLI allerede er installert.
 if exist "%N5WF_LAUNCHER%" set "CURRENT_CLI=1"
)
set "CURRENT_CORE=0"
if "%CURRENT_GUI%"=="1" set "CURRENT_CORE=1"
if "%CURRENT_CLI%"=="1" set "CURRENT_CORE=1"
exit /b 0

:write_state
if not exist "%APP_DIR%" mkdir "%APP_DIR%"
for /f "delims=" %%V in ('py -c "from version import VERSION; print(VERSION)"') do set "CURRENT_VERSION=%%V"
if not defined CURRENT_VERSION set "CURRENT_VERSION=unknown"
powershell -NoProfile -ExecutionPolicy Bypass -Command "$state=[ordered]@{version='%CURRENT_VERSION%'; core=$true; gui=('%NEW_GUI%' -eq '1'); cli=('%NEW_CLI%' -eq '1')}; $json=ConvertTo-Json -InputObject $state; Set-Content -Encoding UTF8 -LiteralPath '%STATE_FILE%' -Value $json"
exit /b %errorlevel%

:install_error
echo.
echo [FEIL] Installasjonen feilet. Eksisterende installasjonsstatus er ikke endret.
pause
exit /b 1

:usage
echo Bruk: install.bat [all^|gui^|cli]
exit /b 2
