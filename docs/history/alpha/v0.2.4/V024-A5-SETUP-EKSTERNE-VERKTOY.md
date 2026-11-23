# DWM v0.2.4-a5 – automatisk oppstartskontroll av eksterne verktøy

## Mål

DWM kontrollerer tilgjengeligheten av Arkade 5 CLI og Siegfried ved vanlig
GUI-oppstart, **uten** å blokkere hovedvinduet, installere verktøy, starte
arkivtester eller endre eksisterende Source/Work/historikk.

### Hvilke steder søkes?

| Prioritet | Arkade 5 CLI | Siegfried (sf.exe) |
|---|---|---|
| 1 | Eksplisitt lagret Setup-sti | Eksplisitt lagret Setup-sti |
| 2 | Gyldig tidligere brukersti | Gyldig tidligere brukersti |
| 3 | Windows `PATH` | SIARD Workflow Managers delte Siegfried-mappe |
| 4 | `C:\Prog` | Windows `PATH` |
| 5 | `%ProgramFiles%` og `%ProgramFiles(x86)%` | `%ProgramFiles%` og `%ProgramFiles(x86)%` |
| 6 | `C:\Program Files`, `C:\Program Files (x86)`, `C:\Programfiler` | De samme mappene og `C:\Prog` |

Bare gjenkjennelige programfilnavn og **et begrenset antall kjente
undermapper** gjennomgås. Ingen rekursiv disk-, nettverks-, Source- eller
Work-skanning.

DWM kjenner både `arkade.bat`, `arkade5*.exe`,
`Arkivverket.Arkade.CLI.exe`, `Nasjonalarkivet.Arkade.CLI.exe` og `sf.exe`.

## Funksjon ved oppstart

1. Opprett hovedvinduet og åpne arbeidsflaten som før.
2. Start en separat, tidsbegrenset versjonskontroll i bakgrunnstråd (med
   eksisterende DWM-adapter for Arkade og `sf -version` for Siegfried).
3. Vis status, sti, versjon og (for Siegfried) PRONOM-signatur i
   **Setup → Eksterne verktøy → Automatisk oppstartskontroll**.
4. Lagre et brukerspesifikt kontrollresultat under
   `%LOCALAPPDATA%\IKAMR\DataWorkflowManager\external-tools-v1.json`.
5. Hvis en gyldig sti ble funnet og den tilsvarende `config.json`-verdien er
   **tom**, lagres programstien automatisk også som `arkade5_cli_path` eller
   `sf_executable`. En allerede valgt Setup-sti overskrives **aldri**.
6. Et neste DWM-katalogtre kan dermed finne den gamle programstien i den
   per-bruker-lagrede filen, kontrollere den på nytt og fylle tom Setup.

Lagring forutsetter at Workbench er ledig. Dersom jobb starter mens kontrollen
kjører, beholder vi kontrollresultatet og forsøker innstillingssynkronisering
ved neste oppstart. Ingen jobb- eller historikktilstand påvirkes.

**Viktig:** Lagret OK er historikk, ikke garanti. Ved ny oppstart kontrollerer
vi at programfilen fortsatt svarer; ved ordinær jobbstart gjelder dessuten
DWM sin eksisterende førkjøringskontroll.

## Arkade 5-versjon

Per 21. november 2026 er **2.13.1 (23.09.2026)** sist verifiserte publiserte
Arkade 5-utgave. I DWM vises dette som en **datert referanse**, ikke en
nettbasert automatisk versjonskontroll. Eldre installert versjon markeres,
men ingen automatisk nedlasting/oppdatering utføres.

Offisiell Arkade 5-nedlasting (gjelder *programvaren*, ikke Noark 5-standarder):
https://arkade.nasjonalarkivet.no/

DWM sin **Noark 5-standardkildepolicy** er uendret: normative Noark 5-kilder
skal henvises til versjonerte IKAMR-kopier i
`IKAMR/digital-archive-workflow`, ikke eksterne standardlenker.

## Start i sikker modus

`DWM_SAFE_MODE=1` deaktiverer den automatiske versjonsproben for å holde
feilsøking av Windows/Qt-oppstart minimal. Eksisterende Setup og manuelt
valgte stier beholdes, og status fra forrige kontroll kan fortsatt ses.

## Test på Windows

```powershell
py -c "from version import VERSION; print(VERSION)"
py -m unittest discover -s tests -p "test_v024_a5_*.py" -v
.\test.bat
```

Praktisk kontroll: start DWM med lagret Arkade/Siegfried; åpne Setup → Eksterne
verktøy og se begge programstier, versjoner og PRONOM-signatur. Prøv deretter
neste DWM-kopi med tom `config.json`; den skal gjenbruke stiene fra
`%LOCALAPPDATA%` etter ny kontroll. Endre en programsti manuelt og bekreft at
automatikken ikke overskriver den. Kontroller at kjøringen av eksisterende
`.n5jobs` ikke endres.

## Uendret

Arbeidsflytens 17 deljobber, XPath, Arkade-testene, Siegfried-identifikasjon,
Work, `.n5jobs`, evidens, rapporter og GUI-oppsett fra a4 er urørt.
