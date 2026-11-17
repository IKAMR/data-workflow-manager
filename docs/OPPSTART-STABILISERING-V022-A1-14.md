# DWM v0.2.2-a1.14 – stabilisering av Qt-oppstart

## Kildegrunnlag

- Repositorium: `IKAMR/data-workflow-manager` (`main`).
- Gjeldende commit, verifisert på GitHub: `1d370a9ae5c32fd202eb65b14e5a0fc7ae8df340`.
- Tidligere kontrollpunkt: `b390bf93b676db15d9854597ca1d660b23f1d6d2`.
- Før endringen ble Git-blobhasshene for `gui_qt/__main__.py`, `start-debug.bat`,
  `start-safe.bat`, `gui_qt/basic_multijob_v022_a1_2.py` og a1.13-testene
  kontrollert mot GitHub. Ingen lokale, upubliserte kodeendringer antas.

## Bekreftet fra Windows-testen

- Normal oppstart har periodevis vist et nesten tomt/mørkt Qt-vindu.
- En tidligere kjøring ga Windows avslutningskode `-1073741819` (`0xC0000005`).
- `start-safe.bat` gjennomførte oppstart og normal avslutning med kode 0.
- Etter Safe Mode fungerte normal oppstart flere ganger, men problemet kom tilbake.
- Tre jobber (`JOB-001`/`JOB-002`/`JOB-003`) ble kjørt sekvensielt og fullførte
  10/10 deljobber og 100 % i GUI. Det innebærer ikke at alle faglige kontroller
  var avviksfrie.

**Native rotårsak er ikke bevist.** Det finnes ingen bevart krasjstakk for feilen.
Tiltaket nedenfor fjerner samtidig aktivering av nye, valgfrie Qt-koblinger
som Safe Mode tidligere slo av. Det er en kontrollert stabilitetsendring,
ikke en bevist retting av en bestemt Qt C++-feil.

## Risikopunkter kartlagt

1. `gui_qt/basic_multijob_v022_a1_2.py` opprettet a1.8/a1.9 en ny styring av
   `QMainWindow.resize()`/`move()` med 0/45/100 ms Qt-timere og `resizeEvent`.
   Den kjører ved siden av `window_positions_v0114_a1.py` sin etablerte
   gjenoppretting av vindusgeometri.
2. `gui_qt/file_dialog_contrast_v022_a1_10.py` installerer et globalt
   `QApplication`-hendelsesfilter og etterplanlagte Qt-operasjoner.
3. `gui_qt/combobox_popup_v020_a2.py` installerer også globalt
   `QApplication`-hendelsesfilter og tidsforsinkede popup-korreksjoner.
4. Oppstart reetablerer dessuten lagrede Qt-dokker og jobblisten før første
   brukerinteraksjon. Dette er eksisterende funksjon som ikke endres her.

## Endringer i denne deltaen

- **Normal `start.bat` bruker konservativ Qt-profil som standard**: ingen av
  de tre valgfrie funksjonene ovenfor startes automatisk.
- Den oppdaterte `gui_qt/__main__.py` styrer dette uten å skrive til `QSettings`,
  .n5jobs, Source eller Work. Opprettelse av API, felles jobbliste,
  kjøring og resultatnavigasjon er beholdt.
- `start-safe.bat` fungerer fortsatt som før og overstyrer også alle
  eksperimentelle aktiveringer.
- `start-debug.bat` oppretter **én ny loggfil per start** under
  `%TEMP%\dwm-startup-logs\` slik at en vellykket oppstart ikke erstatter
  eldre krasjevidens. Konsollen holdes åpen etter avslutning.
- Ny, Qt-uavhengig oppstartspolicy og regresjonstester beskytter mot at
  globale filtrene igjen blir aktivert ved en feil.
- a1.11 sin kolonneutvidelse for Arbeidsflyt forblir deaktivert.

De valgfrie funksjonene kan aktiveres **enkeltvis** i en separat
kommandoprosess ved å sette én av variablene til `1` før `start-debug.bat`:

- `DWM_ENABLE_QT_DIALOG_FILTER=1`
- `DWM_ENABLE_QT_POPUP_FILTER=1`
- `DWM_ENABLE_QT_BASIC_AUTOFIT=1`

Disse er bare for senere kontrollert feilsøking. IKKE aktiver under ordinær
arkivkontroll. `DWM_SAFE_MODE=1` overstyrer alle tre.

## Bevisst midlertidig funksjonstap

- Automatisk justering av hovedvinduets høyde etter stegene i Enkel modus er
  satt på pause. Vanlig manuell størrelse fungerer.
- Kontrastforbedringen i ikke-native fildialoger og den alternative
  posisjoneringen av nedtrekkslister er satt på pause.
- `Tilpass vindu` skjules når auto-fit er deaktivert, slik at en inaktiv
  knapp ikke fremstår som virksom. Øvrig GUI beholdes.

## Sikker Windows-verifikasjon

1. Pakk ut a1.14 over **commit `1d370a9...`**. Ikke bland med eldre deltaer.
2. Kjør `test.bat` og kontroller resultatet.
3. Kjør normal `start.bat`, lukk DWM normalt og gjenta noen ganger.
4. Åpne `1525_004-006_WebSak_v0.2.2-a1.n5jobs` og kontroller at alle tre
   jobbene fortsatt står `Ferdig` / `100 %` og har riktig Work-plassering.
   **Ikke start kjøringen på nytt.**
5. Bytt mellom Enkel og Avansert modus og åpne resultatvisningene.
6. Hvis det fortsatt blir blankt vindu eller krasj, bruk `start-debug.bat` og
   send den nye loggfilen under `%TEMP%\dwm-startup-logs\`.

**Kriterium for lukking:** Normal oppstart og gjenåpning fungerer stabilt på
operatørens Windows/PySide6-miljø. Dette kan ikke avgjøres av Qt-frie tester.

Ingen Git commit eller push er utført av denne deltaen.
