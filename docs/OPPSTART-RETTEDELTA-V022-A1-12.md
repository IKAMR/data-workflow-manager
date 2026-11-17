# DWM v0.2.2-a1.12 – oppstartsretting etter a1.11

## Bakgrunn

Operatøren melder at DWM ikke starter etter installasjon av a1.11. A1.11 koblet
`install_editable_workflow_columns(window)` direkte til oppstarten, før
`window.show()`. En ikke-håndtert Python/Qt-feil i denne koblingen kan hindre
GUI-et fra å vises. Uten konsollens feilmelding er rotårsaken ikke bekreftet.

## Endringer

- `gui_qt/__main__.py` er satt tilbake til den sist kjente fungerende a1.10-
  oppstarten. Det er **kun** den nye a1.11-kolonneinstallasjonen som er fjernet.
- Den eksisterende `gui_qt/workflow_columns_v022_a1_11.py` forblir på disk,
  men aktiveres **ikke**. Manuelt justerbare kolonner fra a1.11 er derfor
  midlertidig deaktivert.
- Oppdaterer a1.11-startuptest og legger til separat regresjonstest.
- `start-debug.bat` kjører vanlig `start.bat`, beholder vinduet etter feil og
  skriver `%TEMP%\dwm-startup-debug.log` for feilsøking.

## Installasjon

1. Pakk ut ZIP-en **over v0.2.2-a1.11** i DWM-roten.
2. Start med `start.bat` (eller `start-debug.bat` dersom det fortsatt feiler).
3. Kontroller at `1525_004-006_WebSak_v0.2.2-a1.n5jobs` kan åpnes og at alle
   JOB-001, JOB-002 og JOB-003 er synlige.
4. Kjør `test.bat` etter at programmet starter.

Ingen endring av `.n5jobs`, Source, Work, AIP, kjøringshistorikk eller globale
innstillinger; ingen commit/push. Det finnes ennå ingen faktisk Windows/Qt-
verifikasjon av denne hotfixen.
