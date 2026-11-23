# Noark 5 v0.2.1-a12 - kvalitetssikring og depotets beslutningsgrunnlag

## Endring og faglig avgrensning

Dette er en **ny, lesende rapportadapter** over allerede lagrede DWM-Work-resultater, ikke en ny rapportdatabase, en ny kontrollmotor eller en alternativ DIAS-/AIP-motor.

Adapteren oppretter to **atskilte utkast** fra samme kildebundne øyeblikksbilde:

1. **Kvalitetssikringsrapport til arkivskaper:** identifikasjon, kildeproveniens, DWM-hovedtall og arkivdeler, Arkade 5-funn (inkludert rapporterte XML-linjer), separate KDRS-tall, DWM-vurderingspunkter og konkrete spørsmål som arkivskaper må besvare.
2. **Depotets godkjennings-/ferdigstillingsrapport:** samme evidensgrunnlag, men med åpne faglige beslutningspunkter for retting, aksept med eventuelle avvik eller avvisning, formell beslutningsmyndighet, dato, saks-/journalreferanse og eventuell senere bevaring.

**Begge er utkast (`DRAFT_REVIEW_REQUIRED`).** Kjøringen godkjenner aldri noe uttrekk, registrerer aldri arkivskapers uttalelse eller depotvedtak, journalfører ikke og lager ikke AIP. Eksisterende manuelt registrert depotvurdering kan vises **kildebundet og tydelig adskilt**, men et slikt kildevedtak overføres aldri automatisk til a12-beslutning.

Den eksisterende kanoniske modellen, DWM-depotrapporten, Arkades normaliserte evidens og valgfrie a11-kvalitetssikringsresultater beholdes i sine egne kilder. DWM-, Arkade- og KDRS-tall summeres ikke sammen; ingen manglende verdi blir automatisk `0`.

## Kommando og Windows-prøving for 1525_004

Pakk deltaen over committet a11.6 fra forrige trinn. Fra repo-roten:

```powershell
.\test.bat

$base = "I:\arkiv-noark5\1525\1525_004_E-1525-2025-0001"
$work = "$base\repository_operations\dwm2\a03"
$kdrsQA = "C:\temp\noark5-a11-1525_004-qa\noark5-a11-practical-qa.json"

py -m noark5_workflow.reporting.qa_decision_v021_a12 `
  --work "$work" `
  --kdrs-qa "$kdrsQA" `
  --preflight

py -m noark5_workflow.reporting.qa_decision_v021_a12 `
  --work "$work" `
  --kdrs-qa "$kdrsQA" `
  --output-dir "C:\temp\noark5-a12-1525_004"
```

Målmappen må **ikke finnes fra før**. La være å oppgi `--kdrs-qa` dersom det eksplisitte a11-resultatet ikke skal inngå. Manglende KDRS-grunnlag blir `not_selected`, aldri null. Ved flere depotrapporter må `--depot-report` peke til én Work-relativ original `depot_validation_report.json`. Ved flere Arkade-kjøringer brukes `--arkade-evidence` med Work-relativ filsti.

DWM-versjonen er `0.2.1-a12`, distribusjonsversjon `0.2.1a12`. **Dette er en utviklingsdelta, ikke en release.**

## Rapportpakken

En vellykket kjøring publiserer samlet **seks filer** i ny målmappe:

| Fil | Ansvar |
| --- | --- |
| `index.html` | Startside som lenker til begge utkastene |
| `01-kvalitetssikring-arkivskaper.html` | Utkast for arkivskapers kontroll og uttalelse |
| `02-depot-godkjenning-ferdigstilling.html` | Utkast til depotets vurderings- og beslutningsgrunnlag |
| `rapportgrunnlag.json` | Kildesporbar modell med eksplisitte ukjente felt og uten automatisk beslutning |
| `funn.csv` | Kilde, test-ID, melding, kontekst og XML-linjer for manuelt arbeid; UTF-8 BOM, semikolon, beskyttelse mot Excel-formler |
| `evidensmanifest.json` | Hash for valgte kildefiler og publiserte rapportfiler |

Alle filene bygges i en lokal staging-mappe og publiseres sammen ved omdøping av katalogen. Eksisterende rapportmapper overskrives ikke. Originale Source-data, XML, tidligere DWM-rapporter og egne vurderings-/historikkfiler er kun lesegrunnlag. Stinavn knyttes til valgt Work, mens historiske kjøringsreferanser gjenfinnes via eksakt RUN-mappenavn for flyttbare disker.

## Sporbarhet og fail-closed-regler

- `job.json` og `canonical-results.json` skal ha lik jobb-UUID (`job_uid`).
- Den originale `depot_validation_report.json` skal samsvare med valgt jobb og normal XPath-run; ved flere aktuelle rapporter stoppes kjøringen inntil én velges.
- DWM-masteres SHA-256 kontrollsjekkes mot kanonisk kildeangivelse.
- `canonical-external-analysis.json` skal tilhøre samme jobb og samme kanoniske kildeversjon; valgte Arkade-kildefiler sjekkes mot deklarert SHA-256.
- Hvis a11-rapport velges, må dens `dwm_index_sha256` matche det eksisterende XPath-resultatet i samme Work; **29 treff er fremdeles bare foreløpige** og aldri full Saxon/lxml-paritet.
- Arkivdelene identifiseres med original system-ID; tittel og rekkefølge er ikke primær identitet. Manglende/dupliserte ID-er avvises.
- Ubekreftet Noark-versjon, arkivskaper, arkiveier og provenance merkes ukjent; navnet hentet fra lagret Work-kildesti er **ikke identitetsbekreftelse**.
- Forsøk på å skrive under eksisterende Work-evidens, Source, symlinker og ugyldige Work-relative stier stoppes.

## Observasjon ved prøve med eksisterende 1525_004-data

Det anonymiserte verktøyet er prøvd mot de opplastede DWM-resultatene i `dwm2/a03` (eksisterende normal XPath-kjøring), med a11 `noark5-a11-practical-qa.json`:

- **4 arkivdeler**, hvorav én er oppført som **Aktiv periode**.
- **58** ordinære DWM XPath-tester med status OK i depotrapportens tekniske sammendrag.
- **54** Arkade 5 Noark-kontroller og **2 rapporterte feil**: `N5.15` (4 mapper under behandling) og `N5.22` (20 journalposter med journalstatus Journalført). Rapporter inneholder kildeangitte linjereferanser der Arkade har rapportert dem.
- **29 MATCH_PROVISIONAL**, 0 MISMATCH_PROVISIONAL, 21 NOT_COMPARABLE i det valgte a11-resultatet; U2 var ikke sammenlignbar i DWM-normalprofilen.
- **6 DWM-depotrapporterte vurderings-/informasjonsrader**. Dette tallet skal ikke summeres med Arkades to feil som om de var unike feil. Aktiv arkivdel vises i tillegg eksplisitt som eget faglig oppfølgingspunkt, ikke som en automatisk normativ feil.

En tidligere full KS-vurdering, journalføring eller depotgodkjenning kan **ikke utledes** fra dette materialet.

## Det a12 ikke gjør, og neste deloppgaver

Dette første a12-trinnet tilbyr **CLI og HTML/CSV/JSON**. De eksisterende eldre HTML-utkastene (`canonical_qa_report_v0115_a12.py`, `canonical_completion_v0115_a14.py`), GUI og felles a20-rapporttjeneste er **ikke** erstattet eller koplet om. A12 kan senere integreres i `Rapporter`/`Resultatvisninger` via den etablerte rapport- og arbeidsflytarkitekturen; unngå egen parallell rapportdatabase.

Før rapporter brukes som formelle dokumenter må det sikres et helt kontrollert beslutningsløp: kildeversjon/noark-XSD, arkivskapers signerte svar, vurdering av restavvik, faktisk depotvedtak med ansvar, dato og begrunnelse, journalføring, eksport til ønsket dokumentformat og etterfølgende dokumentert valg av bevaringsmateriale. Dette er **ikke** gjort av a12.

Utsatt: resterende KDRS Standard/U1/U2-resultatdekning, Arkades 54 tester mot konkrete DWM-kontroller, og parallell ressursstyrt kjøring. Ingen nye store XPath/Arkade-kjøringer kreves for å produsere de to utkastene.

## Test og levering

`tests/test_v021_a12_qa_decision.py`: isolerte enhetstester for kildesamsvar, eksakt kjøringsidentitet, rapportformat, ukjent/verifisert status, Excel-injeksjon, utrygge stier, ikke-overskriving, SHA-256 og CLI. Isolert test og prøving mot opplastet `dwm2/a03` er kjørt i utviklingsmiljø. **Full `test.bat` og visuell Windows/GUI-vurdering må gjennomføres av operatøren før commit.**

Faglige styringsdokumenter: `docs/reference/noark5/NOARK5-CONTROL-TO-PRESERVATION-ROADMAP.md`, `docs/NOARK5-DEPOT-PRESENTATION-AND-ASSESSMENT.md`, `docs/history/alpha/misc/REPORTING-ARCHITECTURE-A20.md`.
