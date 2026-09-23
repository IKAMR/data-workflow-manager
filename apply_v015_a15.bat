
@echo off
chcp 65001 >nul
echo Bruker v0.1.5-a15 delta for Arkade 5 v2.13.1...
where py >nul 2>&1
if %errorlevel% equ 0 (
    py tools\apply_v015_a15.py
) else (
    python tools\apply_v015_a15.py
)
if %errorlevel% neq 0 (
    echo [FEIL] Klarte ikke bruke a15-delta.
    exit /b 1
)
echo [OK] a15-delta brukt.
