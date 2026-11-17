# v0.2.2-a1.2 – felles jobbliste for Enkel og Avansert modus

## Problem og bekreftet bakgrunn

I `N5 WF Man 1547-01` ble `.n5jobs` kontrollert: filen hadde
`"jobs": []` og `"active_job_id": null`. Det forklarer hvorfor
Avansert viste 0/0 selv om Enkel viste en lagret jobbliste.
Enkel opprettet tidligere jobb først ved **Start kontroll**, og
**Ny kontroll** kunne opprette en helt ny jobbliste og miste oversikten.

## Oppførsel i a1.2

Én felles `DwmWorkbenchAPI`, én jobbmodell og én `.n5jobs` i begge visninger.
Ingen ny kjøre- eller Work-motor:

- **Enkel modus får en jobbvelger**: eksisterende JOB-001, JOB-002 osv.
- **Legg til jobb** starter bare et nytt tomt jobbskjema. Ingen andre jobber
  fjernes. Den gamle «Ny kontroll»-handlingen er erstattet i Enkel modus.
- Når **Source og Work** er valgt og bekreftet gjennom eksisterende Work-guard,
  registreres jobben umiddelbart med sine kontrollvalg. Den får JOB-ID og
  status **Klar** selv om kontrollen aldri er startet.
- Finnes en åpen jobbliste med filsti, lagres alle jobbene automatisk i den.
  Ved diskfeil vises advarsel, og modusbytte blokkeres til endringen kan lagres.
- Har listen ennå ikke filsti, opprettes jobben i felles arbeidsmodell.
  Bruk **Lagre jobbliste…** én gang for å velge `.n5jobs`.
- **Lagre jobb** er en tydelig manuell mulighet. Registrering skjer ellers
  automatisk etter Work-valget, slik at knappen ikke er obligatorisk.
- Jobbvelgeren kan brukes for å åpne og endre kontrollvalg for hver jobb.
  Bytte mellom jobbene bevarer den felles jobbidentiteten og metadataene i Work.
- **Start kontroll** kjører bare valgt jobb og bruker fortsatt ordinær
  preflight og worker. **Kjør klare jobber** i Avansert modus bruker den
  eksisterende sekvensielle batchmotoren.
- Source/Work for en eksisterende jobb overskrives aldri ved å velge et nytt
  uttrekk. Det opprettes et nytt jobbutkast.

## Grenseflater og sikkerhet

- Ingen automatisk jobbkjøring eller automatisk AIP-pakking.
- Hver jobb må ha egen Work-mappe. To ustartede jobber i samme Work blir avvist
  også før en Work-manifestfil finnes på disk.
- Mappene kontrolleres med eksisterende `prepare_basic_plan` og
  `inspect_work`; eksisterende data eller ukjent jobbidentitet overtas ikke.
- Arkade 5/Siegfried-installasjonen kontrolleres fortsatt **før kjøring**,
  ikke som en forutsetning for å lagre jobbdefinisjonen.
- Det gjøres ikke omstrukturering av gammel `.n5jobs`, gamle Work-områder
  eller eksisterende XML-arkivuttrekk.
- «Ny jobbliste» i Avansert modus er fortsatt en separat, bevisst handling.

## Test i Windows – uten å kjøre kontrollene

1. Installer delta direkte over **v0.2.2-a1.1**.
2. Kjør `test.bat`. Programversjon er fortsatt `0.2.2-a1`.
3. Åpne eller opprett én `.n5jobs` i Enkel modus.
4. Velg Source 1547_003 og Work 003. Bekreft Work; kontroller at
   **JOB-001** vises i jobbvelgeren uten at «Start kontroll» ble trykket.
5. Om jobblisten mangler filnavn, trykk **Lagre jobbliste…** og velg en fil.
6. Trykk **Legg til jobb**, velg Source 1547_005 og Work 005.
   Se **JOB-002** i samme liste.
7. Gjenta med Source 1547_007 og Work 007 → **JOB-003**.
8. Bytt mellom de tre i jobbvelgeren og sjekk Source, Work og kontroller.
9. Bytt til **Avansert modus**; alle tre jobber skal være synlige.
10. Lukk og åpne samme `.n5jobs` på nytt. Alle tre jobber skal fortsatt
    være der, med egne Source-/Work-stier og uten at kontroller er kjørt.
11. **Valgfritt etterpå:** Kjør samlet med **Kjør klare jobber** i Avansert.

**Må ikke committes før brukerens fullstendige `test.bat` og Qt-visning er grønne.**

## Testgrunnlag

15 nye, målrettede tester for registrering, 3-jobb lagre/gjenåpne,
Work-kollisjoner, kontrollvalg, rollback, GUI-klassekobling og simulert
Qt-handlingsflyt. I tillegg består 20 eksisterende a1-depotprofil- og
versjonstester i isolert kontroll. Full prosjekt-testpakke og ekte PySide6-GUI
kan ikke kjøres i dette Linux-miljøet uten komplett Windows-repo/installasjon.
