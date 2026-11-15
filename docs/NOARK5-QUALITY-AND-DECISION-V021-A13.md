# DWM v0.2.1-a13 – faglige merknader, GUI og samlet rapportpakke

## Formål og status

a13 bygger **på committet a12** og viderefører **eksisterende a20-rapportmotor**.
Den erstatter verken tidligere rapportprofiler, a20-vedlegg A–D, faglig depotvurdering,
Arkade/KDRS-resultater, Noark 5-testkatalogen eller DIAS-pakkingen.

Første gjennomgående GUI-flyt for ett uttrekk:

1. `Resultatvisninger → Faglig vurdering → Visning: Depotvurdering`: velg uttrekk eller arkivdel med original depotrapport.
2. Klikk **KS / depot: vurder funn og lag rapporter…**.
3. Filtrer registrerte funn på ERROR/WARNING/REVIEW/NOTE/INFORMATION eller søketekst.
4. Velg funn, les test-ID, kildestatus, arkivdel/kontekst, XML-fil, linjer og evidenskilde.
5. Registrer **faglig status, kommentar og valg av rapportmottaker**; lagre med eksisterende DWM-brukerprofil.
6. Velg eventuelt a11s kildebundne KDRS-QA-JSON, og velg en **ny** eksportmappe.
7. Lag samlet pakke med **a12 KS-/depotutkast** og, når jobben er tilgjengelig via
   DWM-rapport-API, **a20 Full-rapport og vedlegg A–D**.

Det utføres ingen ny XPath, XSD, KDRS, Arkade eller Siegfried-kjøring.

## Arkitektur – ikke en konkurrerende rapportmotor

| Ansvar | Fortsatt autoritativ kode |
| --- | --- |
| DWM/Arkade/KDRS-funn og kildehash for én Work-jobb | `noark5_workflow/reporting/qa_decision_v021_a12.py` |
| Nytt append-only register over faglige merknader | `qa_review_v021_a13.py` |
| Felles eksportkoordinator – ingen ny teknisk renderer | `qa_decision_v021_a13.py` |
| Eksisterende Full-rapport, a20-visninger, årsfordeling og A–D | `report_service_a20.write_report_package` |
| Faglig depotvurdering/godkjenningshistorikk | Eksisterende `depot_assessment` / `depot_review` (uendret) |
| Visning og valgt rapportuttrekk | `gui_qt/qa_review_v021_a13.py`, installeres i `main_v020_a6.py` |

Den nye a13-eksporten bruker a12s publiseringsfunksjon for de to mottakertilpassede
utkastene. For samme jobb ber den deretter **felles a20-skriver** lage Full/alle
vedlegg i en **egen underkatalog**. Et øverste `index.html` linker til alle tre
visningene. Det kopieres ikke inn HTML fra a20 for å simulere vedleggene.

Eksporten skjer i én stagingkatalog utenfor Work og utenfor Source/AIP. Først når
alle etterspurte filer er ferdige, publiseres katalogen under nytt navn.
Eksisterende rapportmappe kan ikke overskrives. `rapportpakke-manifest.json`
registrerer SHA-256 for hvert generert dokument. En a20-feil publiserer ikke
en halvferdig a13-pakke.

## Versjonsbinding og vurderingshistorikk

- Hvert funn får stabil SHA-256-basert ID av **kilde, test-ID, rå melding, kontekst,
  XML-fil/linjer og rapportkildesti**. Samme test-ID alene er ikke nok.
- Hver kommentar lagres som **én uforanderlig JSON-hendelse** under
  `<Job-Work>/noark5_evidence/qa_review_events_v021_a13/<UUID>.json`.
  Den inneholder brukerprofil, tidspunkt, status, begrunnelse, valgt KS/depot-distribusjon,
  jobb-UUID og SHA-256 for **akkurat den originale depotrapportversjonen**.
- En ny kommentar erstatter ikke tidligere hendelser; den seneste er aktiv for
  samme funn på samme kildeversjon. Historiske hendelser vises ikke automatisk
  som gjeldende hvis depotrapporten har endret hash, eller funnet har endret innhold.
- `event_sha256` kontrolleres ved innlesing for å oppdage tilfeldige endringer.
  Dette er **ikke** en kryptografisk signatur eller manipulasjonssikkert langtidsarkiv.
- Bare kommentarer **eksplisitt valgt** til den aktuelle mottakeren vises i
  mottakerens HTML-rapport. En kommentar som ikke er valgt for noen mottaker,
  blir liggende i Work og **tas ikke med i eksportens JSON/CSV/HTML**.
- Det delte `rapportgrunnlag.json` og `funn.csv` inneholder kommentarer valgt til
  minst én mottaker; ikke send hele den samlede pakken til arkivskaper uten
  vurdering av innsyns-/distribusjonsbehov. Send i så fall bare relevant HTML.
- For begge rapporter gjelder: **faglig merknad != teknisk PASS != arkivskaperaksept
  != depotvedtak != AIP**. Alle dokumentene forblir `UTKAST`.

Faglig status er avgrenset til `requires_clarification`, `context_documented`,
`acceptable_deviation` og `not_relevant`. Valget `acceptable_deviation` betyr
**faglig merknad for et funn**, ikke et godkjent uttrekk. Formell beslutning skal
fortsatt registreres i eksisterende depotvurderingsflyt og journal/sak.

## Praktisk Windows-test (samme testuttrekk som a12)

Pakk deltaen **over committet v0.2.1-a12**, ikke i en egen alternativ kildekatalog.

```powershell
.\test.bat

$work = "I:\arkiv-noark5\1525\1525_004_E-1525-2025-0001\repository_operations\dwm2\a03"
$qa = "C:\temp\noark5-a11-1525_004-qa\noark5-a11-practical-qa.json"

py -m noark5_workflow.reporting.qa_decision_v021_a13 `
  --work "$work" `
  --kdrs-qa "$qa" `
  --preflight
```

**GUI-prøven er den viktigste:** Start DWM, velg `1525_004`, åpne
`Resultatvisninger → Faglig vurdering → Visning: Depotvurdering`, velg uttrekk, åpne a13-dialogen.

1. Filtrer på `ERROR`, velg `N5.15`; kontroller at arkivdel 4, 4 mapper under
   behandling og dokumenterte `arkivstruktur.xml`-linjer vises.
2. Registrer en faglig kommentar, f.eks. behov for bekreftelse fra arkivskaper;
   velg **begge** rapporter. Bekreft at status og kommentaren gjenfinnes etter
   dialogen lukkes og åpnes på nytt.
3. Registrer en ny kommentar på `N5.22`, velg **kun depotrapport**.
4. Velg a11 QA-JSON hvis den skal med; den kan ikke automatisk godkjennes
   som full Saxon/lxml-paritet.
5. Eksporter til en **ny mappe**, med aktiv jobb via DWM-rapport-API.
   Kontroller at pakken har `rapporter/01-...`, `rapporter/02-...`,
   `teknisk-detaljrapport/index.html` og a20s A–D-vedlegg.
6. Verifiser at N5.15-kommentaren er med i begge mottakerrapporter, mens
   N5.22-kommentaren bare finnes i depotutkastet (og i eksportens strukturerte
   grunnlag med utvalgsflagg).
7. Kontroller at tidligere `Rapport valgte`, Enkel/Medium/Full og a20s eksport
   fremdeles fungerer, og at original `depot_validation_report.json` er uendret.

## CLI – avgrensning

Følgende lager en ny pakke med a12 KS-/depotutkast og valgte faglige merknader:

```powershell
py -m noark5_workflow.reporting.qa_decision_v021_a13 `
  --work "$work" `
  --kdrs-qa "$qa" `
  --output-dir "C:\temp\noark5-a13-1525_004-test"
```

**CLI har ikke a20-jobbobjektet fra brukerens aktive DWM-jobbliste**, og
inkluderer derfor ikke a20 Full-rapport. Den manglende delen er tydelig
merket på indeksfilen. Bruk GUI-eksporten for den **kombinerte** pakken;
a20s eksisterende separat eksportdialog er fortsatt tilgjengelig for
samlerapporter og flere jobber.

## Hva a13 ikke implementerer

- Ingen fullstendig sjekklistemotor eller påtvungen utfylling av sjekklisten.
  `sjekkliste.docx` og `sjekkliste-mets.docx` forblir referansemateriale.
- Ingen nye normative Noark 5-regler, ingen automatisk semantisk verdigodkjenning;
  historiske 3.1/4.0/5.0-registre og framtidig Noark 4-migreringskontekst
  bygges videre på separat.
- Ingen automatisk innhenting av arkivskapers svar, journalføring, formelle
  depotvedtak eller DIAS AIP-pakking.
- Ingen revidering av alle a20/Arkade/KDRS-testdefinisjoner.
- GUI-sammenstilling for **ett** uttrekk; gammel a20 samlerapport for flere
  jobber forblir hos eksisterende `Rapport valgte`.

## Beslutning fra praktisk a13-test – N5.22 og framtidig gjenbruk

- **N5.22 er korrekt rapportert av Arkade 5.** I uttrekket `1525_004`
  finnes 20 journalposter med journalstatus `Journalført` i arkivdel 4.
  Statusen er en gyldig M053-verdi generelt, men journalposter som
  avleveres skal etter Noark 5 v5.0 ha status `Arkivert` eller `Utgår`.
  `ERROR` skal derfor beholdes som reelt avvik; «aktiv arkivdel» er ikke
  en begrunnelse for å oppheve testutfallet.
- Under a13-testen velges `Krever avklaring`, og en konkret avvikskommentar
  knyttes til N5.22. Dette endrer ikke teknisk status eller originalt uttrekk.
- Senere skal DWM kunne foreslå **forhåndsdefinerte, gjenbrukbare tekster og
  arbeidsmåter for hyppige avvik** (med versjon, kildekrav og evidens), som
  fagpersonen kan tilpasse. Dette er dokumentert i `docs/TODO-ROADMAP.md` og
  **ikke en del av a13-implementasjonen**.
- Mulige GUI-forbedringer (senere): egne, synlige knapper for
  `Periodevurdering`/`Depotvurdering` og bedre automatisk vindusstørrelse.

## Teststatus ved utvikling

- Isolerte a12 + a13-regresjonstester: **27 bestått** ved utvikling,
  inkludert sporbar kildeversjon, append-only historikk, valgte kommentarer,
  HTML-escaping, fail-closed kildebytte, a20-kall og atomisk pakket eksport.
- Faktiske lagrede `1525_004/dwm2/a03`-resultater: a13 preflight, CLI-eksport
  og eksempel med registrert brukermerknad på N5.15 kontrollert i utviklingsmiljø.
- Den fulle **Windows GUI/Qt-sesjonen og `test.bat` kan ikke kjøres her**.
  Kjør begge før commit. Hvis a20 Full-rapport feiler, send feilmeldingen;
  en ufullstendig a13-pakke skal ikke publiseres.

Referanser: `docs/REPORTING-ARCHITECTURE-A20.md`,
`docs/NOARK5-QUALITY-AND-DECISION-V021-A12.md`,
`docs/NOARK5-CONTROL-TO-PRESERVATION-ROADMAP.md`,
`docs/NOARK5-DEPOT-PRESENTATION-AND-ASSESSMENT.md`.
