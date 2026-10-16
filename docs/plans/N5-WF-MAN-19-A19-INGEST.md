# DWM v0.1.7-a19 – Mottak / Ingest (samlet delta)

## Autoritativt utgangspunkt og installasjon

- Baseline: GitHub `main` på **v0.1.7-a18**, commit `c4da6ab5964320cc272666cd541688452a35483a`.
- Denne ZIP-en er **én samlet delta for a19**, som inneholder alle a19-, a19-fix1- og a19-fix2-endringene.
- **Installer bare denne ZIP-en over a18**. Ikke installer eldre a19-, a19-fix1- eller a19-fix2-ZIP-er i tillegg.
- ZIP-en inneholder kun nye/endrede filer relativt til a18 og skal pakkes ut i repo-roten.
- Versjonsfilen er `VERSION = "0.1.7-a19"`.
- Ingen Git-commit eller push er gjort av assistenten. Brukeren tester, committer og pusher.

## Funksjonsomfang

DWM-hovedknappen **Mottak / Ingest** åpner et nytt dialogvindu som ikke krever aktiv jobb.

### Mottak

- Valgfri `info.xml` for forslag til LABEL. LABEL må ha en verdi og kan redigeres.
- Gjeldende eierkommune (FFKK) er forskjellig fra en eventuell historisk arkivskaper i uttrekks-ID.
- Mottaksnummer etter mønster `E-FFKK-YYYY-nnnn`, redigerbart og foreslått ved skanning av eksisterende mottaksmapper på **valgt disk**.
- Velg disk/volum og eksisterende gruppemappe som `arkiv-karantene-01`, `arkiv-karantene-02` osv.
- Opprett en ny `E-...`-mottaksmappe (ingen sammenslåing med eksisterende mottak).

### Uttrekk

- Velg et eksisterende mottak under samme disk/gruppe.
- Ett eller flere uttrekk kan kobles til samme mottaksnummer.
- Uttrekksmappe: `YYYY-MM-DD_FFKK_nnn_E-FFKK-YYYY-nnnn`, på samme nivå som mottaksmappen.
- Tre sidestilte toppmapper etter ekstern profil: `content/` (`sip/`, `tar/`), `descriptive_metadata/`, `repository_operations/` (`abstract/`, `quarantine/`, `utilities/`).
- Ingen kopiering, endring eller utpakking av arkivinnhold. Ingen passord lagres av DWM.

### Depotspesifikk setup

`config/receiving_folder_profiles.json` inneholder både generiske mottaksprofiler og en `grouped_ingest`-utvidelse for IKAMR. Gruppert mappenavn, uttrekksmønster og undermapper styres av ekstern JSON, ikke av hardkodede IKAMR-stier.

### Sporbarhet

Opprettelse av mottak og uttrekk skrives som egne hendelser i `E-.../ingest.events.jsonl`, via DWM sin eksisterende `WorkflowEvent` og `GenericEventStoreSink`. Hendelsene inkluderer blant annet tid, bruker (der tilgjengelig), mottaksnummer, LABEL, eierkommune, uttrekks-ID, profil og målstier. Valgt `info.xml` kan SHA-256-identifiseres uten at filen endres. Dette er ikke en PREMIS- eller METS-oppdatering.

**Begrensning:** Nummerforslaget er basert på gruppemapper på valgt disk, ikke et felles mottaksregister på tvers av alle disker. Må kontrolleres mot depotets register før produksjonsbruk. Eksisterende mottaksmapper som mangler `ingest.events.jsonl` kan foreløpig ikke automatisk kobles til nye uttrekk uten egen migrerings-/adopsjonsflyt.

## Teststatus og test hos bruker

- 44 av 44 a19-fokustester er kjørt og bestått i isolert Python-miljø.
- Windows-GUI og full `test.bat` **er ikke kjørt av assistenten**.
- Kjør `test.bat` i repo-roten; kontroller `FAILED=0`, `ERRORS=0`.
- Start DWM; se `v0.1.7-a19`; åpne `Mottak / Ingest`.
- Bruk en testdisk med `arkiv-karantene-01`; opprett eksempel `E-1579-2026-0001`, deretter to uttrekk med `1548_001` og `1551_001`.
- Bekreft at mottak og uttrekk er søsken, at uttrekkene har profilmappene, og at mottaksloggen har tre hendelser.
- Bekreft at duplikat mottaksnummer og duplikat uttrekksmappe avvises.

## Bevar utviklingsavtalen i nye tråder

Utvikle fra siste **faktiske** commit på `main`; lever én delta-ZIP per utviklingstrinn, med bare repoets nye/endrede filer og tydelig baseline; ikke git-commit eller git-push; brukeren tester, committer og pusher. Når en bruker ber om neste funksjon, skal tidligere ukommitterte mellomdeltar konsolideres til ett installerbart trinn når det er praktisk mulig.

## Andre registrerte oppgaver (ikke inkludert her)

- LABEL i alle GUI-/rapportvisninger.
- Bredden på `JOB-nnn`-kolonner i rapporter.
- Periodevurderingsstatus i eldre rapportdeler.
- Nedre splitter i hovedvinduets venstre panel.
- Felles sentralt mottaksnummerregister og senere faktisk mottak/kopiering/kontrollsummer.

## v0.1.7-a19-fix3 – Windows-stier og GUI-regresjonstest (2026-10-15)

Denne rettelsen skal pakkes ut **direkte over samlet a19**, og erstatter ikke
samlet a19-delta fra den siste committede a18 (commit `c4da6ab`).
Programversjonen er fortsatt `0.1.7-a19`.

- `app/receiving_folders.py`: `resolve_receiving_base()` bruker fortsatt
  `Path.resolve(strict=True)` for eksistens-/containmentkontroll, men returnerer
  valgt *leksikalsk* sti. Windows kan ellers utvide `TORBJO~1.AAS` til
  `torbjorn.aasen` og få like mapper til å se ulike ut ved `Path`-sammenligning.
- `app/grouped_ingest.py`: `resolve_group()` bruker kanoniske stier til
  sikkerhetskontroll (inkludert krav til direkte barn av disken), men bygger
  resten av mottaks-/uttrekksstiene konsekvent fra den valgte disken. Den
  følger ikke gruppesymlinker.
- `tests/test_v017_a4_6_gui_integration.py`: den eldre testen kontrollerer
  nå både at entrypoint bruker `a4_7_runtime`, og at denne arver `a4_6_runtime`.
  Endringen fjerner ingen faktisk GUI-baselinekontroll.
- Testene dekker videre korrekt sti-retensjon via katalogalias når plattformen
  tillater dette.

**Teststatus ved levering:** 46/46 fokustester for a19 mottak, og 1/1
relevant GUI-entrypoint-test, bestått i isolert Python-miljø.
Full `test.bat` med hele repositoryet er **ikke** kjørt av assistenten.
Kjør `test.bat` i Windows og kontroller `FAILED=0` og `ERRORS=0`.

Arbeidsregel: Én delta per steg, kun endrede repo-filer; ikke commit/push fra
assistentens side. Brukeren tester, committer og pusher.

## v0.1.7-a19-fix4 – lagrede brukerprofiler og depotlogg (2026-10-15)

Se `docs/plans/N5-WF-MAN-19-A19-FIX4-INGEST-LOGGING.md` for eksakt
funksjonskontrakt, loggplassering, akseptansetester og åpne oppgaver.
Dette er en liten delta direkte over a19-fix3 (ikke a18).

## v0.1.7-a19-fix5 – rettet flat mottaksmappe (2026-10-15)

**Autoritativ oppdatering:** `Mottak` oppretter KUN én E-...-mappe.
`ingest.events.jsonl` og `depot-log.txt` er direkte filer i denne, og ingen
`repository_operations/` opprettes der. Denne mappen avventer manuell
nedlasting av krypterte filer. `Uttrekk` er separat og får eget mappetre med
`repository_operations/` som før. Se
`docs/plans/N5-WF-MAN-19-A19-FIX5-FLATT-MOTTAK.md`.
Alle eldre motstridende a19/fix4-beskrivelser av mottaksstruktur er erstattet.
