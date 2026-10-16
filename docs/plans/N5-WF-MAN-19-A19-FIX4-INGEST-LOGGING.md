> **Historisk dokument – OBS:** Beskrivelsen av `E-.../repository_operations/`
> på mottaksnivå ble **rettet i a19-fix5**. Gjeldende struktur er flat E-mappe
> med `ingest.events.jsonl` og `depot-log.txt` direkte i roten.
> Se `N5-WF-MAN-19-A19-FIX5-FLATT-MOTTAK.md`.

# N5 WF Man 19 - a19-fix4: lagrede mottaksprofiler og depotlogg

Dato: 2026-10-15. **Gjelder a19 med fix3 installert.** Denne deltaen er IKKE
en reinstallasjon av a18 eller hele a19. App-versjon er fortsatt `0.1.7-a19`.

## Fast arbeidsregel

Lever delta-ZIP kun med endrede/nye repo-filer; bruker tester med `test.bat`,
og committer/pusher selv. Endringer bygges på sist bekreftede a19-fix3,
ikke gamle a18-deltaer. Ikke påstå full Windows-test uten faktisk kjøring.

## Mottak / Ingest - gjenbrukbare brukerprofiler

Tre nye knapper i gruppert mottaksdialog:

- **Åpne profil**: velg en `.json`-fil som er lagret av DWM.
- **Lagre profil**: lagre over den åpne brukerprofilen. Uten aktiv fil åpnes
  `Lagre som ny profil`.
- **Lagre som ny profil**: velg plassering og navn, uten å overskrive eksisterende
  profil ved et uhell.

Profilen lagrer bare depot-setupfil, valgt mappeprofil-ID, disk, karantenegruppe,
gjeldende eierkommune og standardhandling (Mottak/Uttrekk). Den lagrer **ikke**
LABEL, info.xml, mottaksnummer, uttrekks-ID, dato eller hemmeligheter. Disse må
velges på nytt for hver ny levering. Sist åpnede brukerprofil kan åpnes
automatisk ved neste oppstart fra `last_ingest_user_profile_file` i lokale
innstillinger. Profilformat har `file_type=dwm-ingest-user-profile` og versjon 1.

**To uavhengige konfigurasjonslag**: Depotets mappeprofiler (struktur) ligger
fortsatt i ekstern `receiving_folder_profiles.json`, mens en lagret brukerprofil
beskriver de gjeldende valgene i dialogen. Profilfilen endrer ikke
mappestrukturen i depotets setup.

## Logging fra første opprettelsesoperasjon

- Eksisterende `E-.../ingest.events.jsonl` er fortsatt opprinnelig append-only
  hendelsesgrunnlag for mottaks- og uttrekksopprettelser.
- Ved **opprettelse av mottak** opprettes også
  `E-.../repository_operations/depot-log.txt`. Her lagres lesbare hendelsesdata:
  tidspunkt, hendelses-ID, utførende, resultat, mottaksnummer, LABEL,
  eierkommune, profil, mottaksmappe, kilder og SHA-256 av valgt `info.xml`.
- Ved **opprettelse av uttrekk** føyes handlingen til mottakets TXT-logg, og
  `YYYY-MM-DD_FFKK_nnn_E-.../repository_operations/` mottar:
  `depot-log.txt` og `ingest.events.jsonl` med opprinnelig mottakshendelse og
  uttrekkets nye hendelse. Originale hendelses-ID-er beholdes for senere
  import/aggregering og deduplisering.
- Eldre mottak med gyldig JSONL, men uten TXT-logg, får lesbar historikk
  rekonstruert fra eksisterende kanoniske JSONL første gang et uttrekk
  opprettes i fix4. Ingen opprinnelig logg overskrives.
- En feil etter at JSONL er skrevet bevarer mottaks-/uttrekksmappene og
  feiler synlig, slik at hendelser ikke forsvinner ved tilbakerulling.
- Ingen arkivfiler blir kopiert eller pakket ut; ingen passordlogg opprettes.

Dette er en første operasjonslogg for **opprettelse av mottaks- og uttrekksmapper**.
Andre operasjoner (faktisk filoverføring, kontrollsum, antivirus, manuell
vurdering osv.) må i senere versjoner sende hendelser gjennom samme modell.
Dette er ikke PREMIS, som kan genereres senere fra relevante hendelser.

## Test

54/54 fokustester for a19 (inkl. 8 nye fix4-tester) bestått på Linux/isolert
Python. Windows-GUI og full `test.bat` må kjøres av bruker. Også i full test
kan to eldre symlink-tester hoppes over ved manglende Windows-rettigheter.

### Akseptansetest for to uttrekk

1. Installer kun a19-fix4 over a19-fix3; kjør `test.bat`.
2. Åpne Mottak/Ingest og velg IKAMR-karanteneprofil. Klikk **Lagre som ny profil**;
   kontroller at profilfilen kan åpnes med **Åpne profil**. Mottaksnummer og LABEL
   skal ikke gjenbrukes fra forrige levering.
3. Opprett ett **testmottak** under testdisken, for eksempel
   `E-1579-2026-0001`. Kontroller `repository_operations/depot-log.txt`.
4. Opprett uttrekkene `1548_001` og `1551_001` mot samme mottak, som to
   søskenmapper på nivået til mottaket.
5. Kontroller at mottakets `ingest.events.jsonl` har 3 hendelser, og at
   mottakets depotlogg har 3 lesbare oppføringer.
6. Kontroller at **hver** uttrekksmappe har egen `repository_operations/depot-log.txt`
   og `ingest.events.jsonl` med 2 hendelser (opprinnelig mottak + eget uttrekk).
7. Kontroller at de to uttrekkene ikke har kopier av hverandres hendelser.
8. Kontroller at bruk av allerede eksisterende mottaks-/uttrekksmappe blir avvist.

**Begrensning:** Nummerforslag skanner kun valgt disk, ikke alle IKAMR-disker.
Mottaksnummer må kontrolleres mot depotregisteret. Fullt depotlivsløp,
import/aggregering av senere workflowhendelser og PREMIS gjenstår.
