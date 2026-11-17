# DWM v0.2.2-a3.1 - kompatibilitet med vanlig Noark 5-Work

## Problem

Den nye a3-dialogen brukte den eldre a12/a13-rapportmotoren. Denne forventet
`noark5_evidence/canonical-results.json`, som er en valgfri, eksplisitt
resultatprojeksjon og **ikke** blir opprettet av standard arbeidsflyt med 10
Noark 5-operasjoner. JOB-002 og JOB-003 feilet derfor ved oppstart av
avviks-/KS-dialogen selv om den ordinare kjøringen var fullfort.

## Endring

- Den nye `qa_work_snapshot_v022_a3.py` leser **allerede lagret** Work og
  genererer det samme a12-rapportgrunnlagets struktur i minnet.
- Jobbidentitet kontrolleres fra `job.json` med `job_uid` og `job_id`.
- Valgt `depot_validation_report.json` kontrolleres mot jobben og mot
  kjoreidentiteten i lagret XPath `master-results.json`.
- Test-ID og status avstemmes mot XPath-master. Ulike kjoreversjoner skal ikke
  blandes uten at et avvik meldes eksplisitt.
- Arkade-importen hentes fra **rapportens eksplisitte importreferanse**,
  kontrolleres mot importmanifest, bevart original og SHA-256.
- Historisk PRONOM/RAF-220301 verifiseres som egen kilde og beholdes atskilt
  fra normative Noark-kontroller.
- Hvis en gyldig `canonical-results.json` allerede finnes, brukes fortsatt
  den etablerte a12-losen. Kilden blir aldri bygget pa nytt eller kopiert fra
  en annen jobb i denne rettelsen.
- `noark5_evidence` opprettes **bare ved en eksplisitt lagrehandling** for
  faglig merknad eller manuell observasjon. Ingen kanonisk datafil skrives.
- Ingen endringer i Source, gamle resultater, versjonsstreng, Qt-oppstart,
  popup-filtre eller den ordinare 10-trinns arbeidsflyten.

## Testresultater i utviklingsmiljoet

- Python kompilering av endrede filer: bestatt.
- 8 isolerte regresjonstester med eksisterende a12/a13-grensesnitt simulert:
  bestatt. Testene dekker Work uten evidensmappen, rapportversjonsbinding,
  korrekt Arkade/PRONOM-opphav, avvisning av endret kildefil, manuell
  registrering og rapporteksport.
- Praktisk, lesende kontroll mot brukerens ekte output-ZIP-er:
  JOB-001/1525_004, JOB-002/1525_005 og JOB-003/1525_006: bestatt.
- JOB-002: 3 arkivdeler, 54 Arkade-tester, 2 historiske RAF-vurderinger
  (x-fmt/62 og fmt/50), riktig jobbidentitet, og ingen paakrevd kanonisk fil.
- Opprettelse av manuell observasjon testet pa en lokal **kopi** av Work,
  ikke pa brukerens originale data.
- Windows/PySide6 og full regresjonssuite ble ikke kjort i dette miljoet.

## Test i DWM

1. Pakk ut denne ZIP-en over **allerede installert a3** i repo-roten.
2. Start DWM og velg eksisterende jobb **JOB-002 (1525_005)**.
3. Bruk **Rapport -> Avvik, kvalitetssikring og godkjenning**.
4. Se etter eksisterende DWM-funn og begge RAF-vurderinger. Kontroller at
   toppteksten fortsatt viser **JOB-002** og at ingen ny analyse blir startet.
5. Registrer en manuell observasjon, lukk og apne dialogen igjen. Den skal
   fremdeles finnes i **JOB-002 sin egen Work-mappe**.
6. Lag en KS-/depotrapportpakke, og kontroller at begge dokumenter er utkast.
7. Kontroller at vanlig jobbstatus og `depot_validation_report.json` er uendret.

Denne ZIP-en er en **delta over v0.2.2-a3**, ikke en selvstendig DWM-installasjon.
