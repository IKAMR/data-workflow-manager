# DWM v0.2.2-a3 – Avvik, kvalitetssikring og godkjenningsrapport

## Grunnlag og avgrensning

**Delta over GitHub `main` `b3ded0f7883cca55b376bb636fe2312ce0eebc8e`** (committet v0.2.2-a2).

Denne deltaen bygger videre på eksisterende v0.2.1-a12–a15-løsninger. Den lager **ikke** en ny Noark-testmotor, endrer ikke kildedata og gjeninnfører ingen Qt-vindus-/popup-timere. Intern applikasjons-/testversjon **`0.2.2-a1` beholdes** etter avtale. Utviklingstrinnet kalles **v0.2.2-a3** i Git.

## Ny arbeidsflyt

Fra **Avansert modus**: `Rapport → Avvik, kvalitetssikring og godkjenning…`.

Fra **Enkel modus**: velg riktig jobb og åpne **Oversikt → Avvik / KS / godkjenning…**.

Alternativt via eksisterende `Resultatvisninger → Faglig vurdering → Depotvurdering → Avvik / KS / godkjenning…`.

Det åpnes én dialog for aktiv jobb. `JOB-002` skal ikke stille seg om til `JOB-001` selv om begge heter `content` i opprinnelig GUI. Dialogen bruker original depotrapport og valgte Work som identifikasjon.

### 1. Dokumentere funn

Dialogen viser kildebaserte funn fra:

- Eksisterende DWM-depotvurderingspunkter og aktiv arkivdel (a12).
- Arkade 5 `ERROR`/`WARNING` med dokumenterte XML-filer og linjenumre (a12).
- DWM XPath-kontroller med ikke-OK status i lagret original depotrapport (a3).
- Historisk Arkade 5 RAF-220301 `Ikke gyldig`, **bare** når et entydig SHA-verifisert PRONOM-statistikkgrunnlag for samme Arkade-import er tilgjengelig (a3). Disse registreres som `REVIEW`, ikke som normative Noark-/filfeil.
- **Egne manuelle observasjoner** opprettet med knappen `+ Registrer manuelt avvik / observasjon` (a3). Et manuelt funn er **ikke** en maskinell test og får egen ID `MAN-<UUID>`.

Det vises antall funn, vurdert/ubehandlet, tekniske feilfunn, advarsler og manuelt registrerte funn. `Vis bare funn uten faglig vurdering` filtrerer den åpne listen.

For hvert funn kan kontrollør registrere eksisterende a13-status, begrunnelse/kommentar og velge **uavhengig** om kommentaren inngår i:

- kvalitetssikringsrapporten til arkivskaper,
- depotets godkjennings-/beslutningsutkast.

Eksisterende a13-statusene bevares: `Krever avklaring`, `Kontekst dokumentert`, `Akseptabelt avvik – faglig merknad, ikke godkjenning`, `Ikke relevant – begrunnet`.

### 2. Kildebinding og historikk

Manuelle observasjoner registreres som én uforanderlig JSON-hendelse per registrering under:

`<job-Work>/noark5_evidence/qa_manual_findings_v022_a3/<UUID>.json`

Vurderinger lagres i **eksisterende** append-only a13-register:

`<job-Work>/noark5_evidence/qa_review_events_v021_a13/<UUID>.json`

Begge er bundet til riktig `job_uid` og **SHA-256 for den originale depotrapporten**. Kildeversjonsbytte gjenbruker ikke gamle beslutninger eller manuelle funn som aktive funn. Originalrapporter, tidligere hendelser og Source endres ikke. En JSON-hash brukes til integritetskontroll av hendelser, ikke som elektronisk signatur.

### 3. Rapportpakken

Velg **en eksisterende overordnet eksportmappe**. GUI foreslår en ny katalog `noark5_a3_JOB_002_<dato_tid>`; den nye katalogen skal ikke finnes fra før. Mål må være atskilt fra Source, Work og AIP. Ved eksport skrives én komplett pakke atomisk, eller ingenting.

| Fil | Funksjon |
|---|---|
| `index.html` | Startside og lenker til dokumentene |
| `avviksregister.html` | **Alle** registrerte funn for valgt kildeversjon, også ubehandlede |
| `avviksregister.csv` | Regnearkvennlig avviksregister (formelbeskyttet CSV) |
| `avviksregister.json` | Strukturert oversikt over funn og behandlingsstatus |
| `rapporter/01-kvalitetssikring-arkivskaper.html` | **Utkast** til kvalitetssikringsrapport |
| `rapporter/02-depot-godkjenning-ferdigstilling.html` | **Utkast** til depotets godkjennings-/beslutningsrapport |
| `rapporter/rapportgrunnlag.json`, `funn.csv`, `evidensmanifest.json` | Eksisterende a12/a13 kilde- og avviksgrunnlag |
| `teknisk-detaljrapport/index.html` med vedlegg A–D | Eksisterende a20 Full-rapport, når aktiv jobb kan hentes fra DWM-rapport-API |
| `rapportpakke-manifest.json` | SHA-256 for alle publiserte filer |

**Distribusjon:** `avviksregister.*`, `rapportgrunnlag.json`, `funn.csv` og den komplette eksportpakken kan inneholde interne funn og kommentarer. **Ikke send hele pakken til arkivskaper ukritisk.** Send kun gjennomgått mottakertilpasset dokument og dokumentasjon som skal deles.

Manuelle observasjoner som ikke er særskilt valgt og kommentert for mottaker, løftes ikke automatisk inn i mottakertilpasset KS-/depottekst. Avviksregisteret viser dem som åpne oppfølgingspunkter. Kildekommentarer som eksplisitt ikke er valgt for noen rapport, blir i Work og eksporteres ikke som kommentar.

### 4. Hva «godkjenning» betyr

**Alle KS- og godkjenningsdokumenter i a3 er utkast.** Følgende krever fortsatt egen dokumentasjon og beslutning: arkivskapers svar, kontroll av restavvik, vurderingsmyndighet, begrunnelse, dato, journalreferanse, eventuelt vedtak og senere DIAS/AIP. Selv 58/58 DWM og 54/54 Arkade OK er ikke automatisk depotgodkjenning.

## Windows-prøving før commit

1. Pakk deltaen over arbeidskopien som samsvarer med GitHub a2. Ikke bland inn gamle ucommittede patcher.
2. Kjør `test.bat`. Den nye testen er `tests/test_v022_a3_qa_workflow.py`.
3. Start `start.bat` minst tre ganger, også på widescreen, før større faglig testing. Observer konsoll og oppstart.
4. Åpne jobblisten med `1525_004`, `1525_005`, `1525_006`. Velg **JOB-002** (1525_005).
5. Test **Avansert → Rapport → Avvik, kvalitetssikring og godkjenning…**. Verifiser at tittelen sier JOB-002.
6. Verifiser at DWM vurderingspunkter finnes. Sjekk om to historiske RAF/PRONOM-grupper vises; de vises kun når kildefilen er valgt og kildeverifisert. Ikke mistolk fravær som fravær av filformatfunn.
7. Registrer en manuell observasjon med `REVIEW` og konkret kontekst. Lukk og åpne dialogen på nytt. Funn og forfatter skal gjenfinnes.
8. Velg funnet, registrer kommentar `Krever avklaring`, velg `Ta med kommentaren i KS-rapport` og eventuelt depot. Lagre. Kontroller at antall ubehandlede reduseres.
9. Velg en overordnet mappe som `I:\arkiv-noark5\1525\Reports` og eksporter. **Ikke** velg Source eller Work. Kontrollér de to mottakertilpassede dokumentene, avviksregisteret og Full-rapporten med A–D.
10. Verifiser at `job.json`, original `depot_validation_report.json` og tidligere kjøringer er uendret. Lukk/åpne DWM og prøv **Enkel → Oversikt → Avvik / KS / godkjenning…**.
11. Test også JOB-001 (1525_004): N5.15 og N5.22 skal bevares som Arkade-funn, ikke overskrives av vurderinger.
12. Ved krasj: behold konsollutskrift og Windows-feilkode; ikke slå på de gamle Qt event-filtrene.

## Avgrensninger

- Ingen nye Noark-/Arkade-/XPath-kjøringer.
- Ingen automatisk godkjenning, arkivskapersvar, journalføring eller AIP-produksjon.
- PRONOM-vurdering mot den **aktive** institusjonelle formatprofilen er foreløpig separat i Resultatvisninger. a3 kan dokumentere kildeverifiserte **historiske RAF-klassifiseringer** og manuelle vurderinger, men påstår ikke at alle formatregler er automatisk vurdert.
- Detaljer fra eksterne data uten kildeintegritet eller entydig kobling blir ikke tatt med som bekreftede avvik.
- `qa_manual_findings` er et nytt tilleggsregister i Work, men tekniske funn og faglige vurderinger bruker fortsatt de eksisterende autoritative kildene. Ingen parallell Noark-motor eller beslutningsdatabase er laget.
- Lokal kontroll av de nye Python-modulene er gjort med 10 isolerte tester mot teststubber og kompilering. Hele GitHub-repoet, Windows GUI og `test.bat` må verifiseres i brukerens arbeidskopi før commit.
