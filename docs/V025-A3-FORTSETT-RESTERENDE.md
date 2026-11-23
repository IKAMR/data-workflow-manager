# Data Workflow Manager v0.2.5-a3 – Fortsett og kjør resterende

## Ny samlet handling i Enkel og Avansert modus

**Fortsett og kjør resterende (N)** viser antallet jobber som kan fullføres i
én sekvens fra den åpne `.n5jobs`-jobblisten. Handlingen er tilgjengelig i
**Kjør**-menyen/verktøylinjen og i Enkel modus ved «Kjør alle klare».

Ved bekreftelse opprettes **én kø** gjennom DWMs eksisterende `_start_worker`
og `DwmWorkbenchAPI.run_job` – ingen ny kjører, ingen endring av jobb-ID,
Source eller Work.

- `Ferdig` – hopp over, ingen ny kjøring.
- `Feil` – fortsett ved feilet deljobb med verifisert Work-historikk.
- `Venter ved kontrollpunkt` – fortsett fra faktisk kontrollpunkt.
- `Klar` med gyldig delvis kjøremarkør – fortsett uten å kjøre fullførte deljobber på nytt.
- `Klar`, 0 % og nullmarkør – start fra første deljobb.
- `Hoppet over`, frakoblet, kjørende eller ukjent/inkonsistent status – blokkér hele forespørselen og forklar hvorfor. Ingen automatisk nullstilling.

Eksempel: JOB-001 Ferdig, JOB-002 Feil ved 5/17, JOB-003 Klar 0/17
fører til **JOB-002 Fortsett fra 6/17 → JOB-003 Start fra 1/17**.
JOB-001, de fem fullførte deljobbene i JOB-002 og tidligere
Siegfried-/PRONOM-resultater endres ikke.

## Sikkerhetskrav

1. Én samlet bekreftelse viser rekkefølgen og startpunkt per jobb.
2. Alle jobbstatuser vurderes på nytt rett før køen sendes til den eksisterende
   worker. Eksisterende preflight/Work-godkjenning kjøres for alle jobber.
3. Sekvensen stopper når en jobb får teknisk feil, avbrytes, mangler status
   **eller venter ved et kontrollpunkt**. Neste jobb starter bare etter
   status **Ferdig**; en vellykket checkpoint-pause er ikke fullføring.
4. Fortsettelse bruker `continue_waiting=True` og eksisterende API-policy,
   slik at den verifiserte markøren bevares. Nye 0 %-jobber bruker vanlig
   `run_job` uten `allow_rerun=True`.
5. Ingen omkjøring av ferdige jobber, endring i kildedata, sletting av Work
   eller overskriving av dokumentert tidligere kjøre-/resultathistorikk.

## QA

- `py -m unittest discover -s tests -p "test_v025_a3*.py" -v`
- `test.bat`
- Praktisk Windows/Qt: tre jobber med ferdig/feil/ny; feil ved deljobb 6/17,
  ny jobb 0/17; og kontrollpunkt som stopper hele køen.

**Grunnlag:** `a281-300` etter A170/A180-integrasjonen (v0.2.5-a1).
**Versjon:** `0.2.5-a3` / distribusjon `0.2.5a3`.

## Leveringsform

Dette er en delta-ZIP med komplette erstatningsfiler. Kontroll ved avslutning av hver jobb er lagt i v0.2.5-a3-vinduklassen; original `gui_qt/main_window.py` beholdes urørt. Ingen patchskript, og eksisterende `docs/test-results/` overskrives ikke.
