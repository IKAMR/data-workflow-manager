# Noark 5 a11 – KDRS/Saxon og DWM/lxml, evidensbasert regresjon

Baseline: DWM v0.2.1-a10, commit `a698d1319b97bc5225e06ba7c19893251c53d1c2`.

Dette første a11-inkrementet sammenligner eksplisitt kartlagte måleverdier fra
KDRS/Saxon og DWM/lxml, og nekter å gi foreløpig MATCH uten identisk XML-bytehash. Filhash ved analyse er ikke bevis for hvilke byte som ble brukt da kjøringene fant sted.
Det **kjører ikke Saxon**, oversetter ikke XQuery og bekrefter ikke komplett
semantisk paritet for alle de 59 historiske KDRS-jobbene. Eksport fra
KDRS Query må normaliseres og dokumenteres før den kan brukes som sammenligningsgrunnlag.

Input er tre JSON-filer og samme XML-kildemappe. DWM-input er `index.json`
fra `noark5_workflow.analysis.xpath_test_engine.run_catalog` med tilhørende
`results/*.json`. KDRS-input skal ha `format_version: 1`, `engine: "Saxon"`,
`xml_sha256` (filnavn til SHA-256 av **originale byte**) og `jobs` (jobb-ID til
resultatfelter). KDRS-eksporten er et datagrunnlag, ikke noe som skal
påstås å være produsert automatisk av denne modulen.

Eksempel KDRS-data:

```json
{"format_version":1,"engine":"Saxon","xml_sha256":{"arkivstruktur.xml":"<sha256>"},"jobs":{"C01":{"archive_count":1}}}
```

Eksempel eksplisitt sammenligningskontrakt:

```json
{"format_version":1,"scope":"partial","comparisons":[{"job_id":"C01","test_id":"kdrs.c01","kdrs_path":"archive_count","dwm_path":"archive_count"}]}
```

Kjør fra repoets rot:

```powershell
py -m app.noark5_kdrs_parity_v021_a11 --dwm-index "C:\temp\dwm-xpath-run\index.json" --kdrs-results "C:\temp\kdrs-saxon-export.json" --mapping "C:\temp\kdrs-dwm-map.json" --xml-root "C:\path\to\samme\uttrekk" --output-dir "C:\temp\noark5-a11-qa"
```

Dette er en **illustrerende kommando med plassholdere**. Ingen full eksport eller
representativ sammenligningskontrakt følger med ennå. Manuell transformasjon
av KDRS-resultater skal kildeverifiseres, ikke gjettes fra navnelikhet.

Utdata: `noark5-a11-parity.json`, `.csv` og `noark5-a11-summary.md`.
`MATCH_PROVISIONAL` betyr foreløpig verdiidentitet på kartlagt felt,
`MISMATCH_PROVISIONAL` er en foreløpig målbar forskjell, `NOT_COMPARABLE` er manglende
eller ugyldig evidens. Alle normative dekningspåstander og global Saxon/lxml-
paritet forblir `false`.

## Før videre a11-arbeid

1. Kartlegg faktisk KDRS/Saxon eksportformat for Standard, U1 og U2.
2. Dokumenter eksakt XML-input og kjøringskonfigurasjon på begge sider.
3. Legg til verifiserte feltkartlegginger og kryssjekk komplekse verdityper.
4. Legg til versjonsspesifikke differanser og GUI-visning uten å endre eksisterende resultater.

## a11.3 – direkte import av originale KDRS Query-tekstresultater

`app.noark5_kdrs_text_import_v021_a11` leser nå de faktiske tekstformatene
skrevet av `IKAMR/KDRS_Query/src/KDRS_Query/Form1.cs`: vanlig resultatfil med
`Query result:`, `_clean.txt`, og separat `job_enabled=3`-fil for U01/U02.
Parseren skiller jobbseksjonene på originalt `=================================`,
og avviser duplikater, ødelagt struktur og ukjente kontroll-ID-er. Den baserer
seg på den kjente originalimplementasjonen, ikke på antatte CSV-kolonner.

### Bruk

For at DWM-kjøringen skal være sammenlignbar, må `index.json` være fra
`noark5_workflow.analysis.xpath_test_engine.run_catalog` med de originale
`results/`-filene intakt. Bruk faktiske stier i eksemplet under:

```powershell
py -m app.noark5_kdrs_text_import_v021_a11 `
  --dwm-root "C:\git\IKAMR\data-workflow-manager" `
  --xml-root "D:\noark5\mitt-uttrekk" `
  --noark-version 5.0 `
  --report "STANDARD=D:\kdrs-results\kdrs_query_results_mitt-uttrekk_clean.txt" `
  --report "U1=D:\kdrs-results\kdrs_query_results_mitt-uttrekk_U01.txt" `
  --report "U2=D:\kdrs-results\kdrs_query_results_mitt-uttrekk_U02.txt" `
  --dwm-index "D:\dwm-results\xpath\index.json" `
  --output-dir "C:\temp\noark5-a11.3-qa"
```

Kun `STANDARD=...` er også gyldig; legg til U1/U2 der resultatene finnes.
`--dwm-index` er valgfritt, men kreves for å sammenligne tall direkte. Sett
`--noark-version` til faktisk identifisert Noark 5-versjon for uttrekket.
Målmappen må være ny og ligge utenfor DWM-repo, originalt uttrekk og mappene
med originale KDRS-resultatfiler.

Importerens fire rapporter er:

- `noark5-a11-kdrs-import.json`: KDRS-resultatkandidater, proveniens, XML-
  hash ved **importtidspunktet**, referansehash og avvik; kompleks råtekst
  lagres ikke som kopi i JSON. Opprinnelig KDRS-rapport beholdes uendret.
- `noark5-a11-kdrs-map.json`: eksplisitte, kildesjekkede *foreløpige*
  koblingsrader til DWM for enkle `count(...)`-uttrykk; ikke full dekning.
- `noark5-a11-kdrs-inventory.csv`: alle importerte jobber med kildeprofil,
  mulig tallkobling og forklaring på avviste/ikke-mappede jobber.
- `noark5-a11-kdrs-import-summary.md`: antall, mangler og QA.

Når `--dwm-index` er oppgitt, produseres også de tre a11.1-rapportene
`noark5-a11-parity.json`, `noark5-a11-parity.csv` og
`noark5-a11-summary.md` i samme nye utmappe.

### Faglige og tekniske begrensninger

- Standard, U1 og U2 kan alle importeres. Foreløpig får **bare en avgrenset
  liste med direkte telleresultater i Standard** automatisk feltkobling.
  U1/U2, tabeller, tidsserier og spesialhandlere står som opaque/ikke mappet
  frem til faktisk kildelesing og sammenligning av strukturert output.
- Enkle telleresultater får bare kandidatstatus dersom KDRS-kildefilen i
  `docs/reference/kdrs-query/` og faktisk DWM-katalog har samme dokumenterte
  `count(...)`-uttrykk. KDRS-profil og oppgitt query-filnavn kontrolleres, og
  ved verbose format kontrolleres også innebygd original XPath-tekst.
- KDRS-rapporttekst dokumenterer **ikke** hvilke XML-byte eller hvilken Saxon-
  prosess som ble brukt historisk. SHA-256 som beregnes nå er etterfølgende
  evidens, ikke kjøringsattestasjon. Et foreløpig talltreff er derfor aldri
  normative kravsvar, godkjent paritet eller depotgodkjenning.
- Den opprinnelige C#-koden er undersøkt: `XpathRun.cs` bruker `Saxon.Api`,
  `Form1.cs` skriver tekstresultater. Importeren kjører fortsatt ikke Saxon
  og endrer ikke noen av disse kildefilene.
- Store XML-filer SHA-256-hashes nå strømmet i
  `app.noark5_kdrs_parity_v021_a11` (a11.3), uten full `read_bytes()`.

### Neste del av a11

Kjør på et faktisk uttrekk med Standard- og eventuelt U1/U2-tekstresultater;
undersøk importinventar og foreløpige avvik. Deretter utvides den eksplisitte
kvalitetssikrede mappingen til U1/U2 og øvrige beregninger. Historisk Saxon-
input og faktisk utførelse må attesteres hvis vi skal gå lenger enn
`MATCH_PROVISIONAL`. Kildekrav fra Noark 5 v3.1/4.0/5.0 er separate fra
KDRS-regresjonsresultatene.

For enkle verdikoblinger inneholder `noark5-a11-parity.csv` nå også
`kdrs_value` og `dwm_value` side om side, i tillegg til status og årsak.
KDRS-varianter `no-journal` og `no-offjournal` fra samme daterte
2026-kildesett støttes når referansefilen finnes i DWM-repoet.

## a11.4 – U1-/U2-tall og arkivdelsikker sammenligning

Dette er **delta over a11.3**. Ingen ny appversjon: `version.py` og
`pyproject.toml` forblir `0.2.1-a11` / `0.2.1a11` fra a11.2.

### Nye sammenlignbare kandidatverdier

- **U01 – hele uttrekket:** 21 eksplisitte `count(...)`-vitner fra historisk
  KDRS U1-kilde, kartlagt mot eksisterende `kdrs.u01`-resultatfelter i DWM.
  Blant annet arkiv, arkivskaper, arkivdeler, klasser, mapper, registreringer,
  dokumentbeskrivelser, dokumentobjekter og utvalgte relasjons-/bevaringsfelt.
- **U02 – per arkivdel:** 14 eksplisitte `count(...)`-vitner fra historisk
  KDRS U2-kilde, kartlagt mot eksisterende `kdrs.u02`-resultater per
  arkivdel. Det gjelder blant annet klasser, mapper, registreringer,
  dokumentobjekter, korrespondanseparter og bevaringsrelaterte forekomster.
  U2 krever `--dwm-index` med **utført** `kdrs.u02`-regresjonstest.
- Koblingene er verifisert mot **ordlyd og XPath-uttrykk i de to faktiske
  2026-05-26-kildefilene** i `IKAMR/KDRS_Query`, `master` commit
  `a68d809ee04c8aceb75976c668bf9746e26d67cb`. Referansefilene i DWM
  under `docs/reference/kdrs-query/` brukes ved kjøring, og deres faktiske
  SHA-256 registreres i importen.

**Sikkerhet:** U2 deles først opp dersom *alle* `Arkivdel <nr>: <tittel>`-
markører er entydige, i riktig rekkefølge og samsvarer med faktiske
`archive_part.index` og `archive_part.title` i DWMs allerede lagrede U02-
resultat. For hver kartlagt måleverdi sammenholder selve sammenligningsmotoren
også DWM- og KDRS-identitetsoppføringen. System-ID er kun dokumentert av DWM,
ikke historisk U2, og kan derfor ikke brukes som Saxon-identitetsbevis.
Manglende/tvetydig tittel, feil rekkefølge eller ufullstendig DWM U02-resultat
gir ingen U2-koblinger. Dette er en bevisst *fail-closed*-begrensning.

### Kjøring

Samme kommandolinje som i a11.3 gjelder; det er ingen nye CLI-argumenter:

```powershell
py -m app.noark5_kdrs_text_import_v021_a11 `
  --dwm-root "C:\git\IKAMR\data-workflow-manager" `
  --xml-root "D:\noark5\uttrekk" `
  --noark-version 5.0 `
  --report "STANDARD=D:\kdrs\kdrs_query_results_uttrekk_clean.txt" `
  --report "U1=D:\kdrs\kdrs_query_results_uttrekk_U01.txt" `
  --report "U2=D:\kdrs\kdrs_query_results_uttrekk_U02.txt" `
  --dwm-index "D:\dwm\xpath-regresjon\index.json" `
  --output-dir "C:\temp\noark5-a11.4-qa"
```

Filnavnene og stiene over er **eksempler**. DWM-indeksen må peke på resultatene
fra det samme uttrekket og faktisk inneholde `kdrs.u01` og `kdrs.u02` dersom
begge skal sammenlignes. Dersom en av disse mangler, blir den tilhørende delen
ikke sammenlignbar; det er **ikke** et nullresultat og ikke en feil i uttrekket.
`--report U1=` og `--report U2=` er valgfrie; ingen tung XPath-kjøring startes
automatisk av importeren.

`noark5-a11-parity.csv` inneholder nå profil (`STANDARD`, `U1`, `U2`),
arkivdelens indeks/tittel for U2, resultatstatus, årsak og begge verdiene.
`noark5-a11-parity.json` har `summary.by_profile`. Inventaret viser antall
kartlagte metrikker per jobb. KDRS-resultatene og Source endres ikke.

Den samme store XML-filen SHA-256-leses **maksimalt én gang per fysisk sti i
en rapportkjøring**, i stedet for én gang per sammenligningsrad. Dette
fjerner unødvendig gjentatt I/O ved mange arkivdeler.

### Grenser før a11 kan avsluttes

- **Ingen faktisk sammenligning på depotets reelle KDRS-resultater er kjørt
  av denne leveransen.** Automatiserte tester bruker eksplisitte syntetiske
  KDRS-tekstutdrag med to arkivdeler.
- Rå Standard/U1/U2 kan inneholde tabeller, distribusjoner, datoer, fri tekst
  og spesialregler som foreløpig **ikke** er koblet til enkeltverdier. 21 og
  14 er antall *tilrettelagte tellesammenligninger*, ikke antall godkjente
  Noark-krav, og heller ikke alle U1/U2-felter.
- KDRS/Saxon-kjøringen var historisk. Verken importert tekst, originalt
  kildekodenavn, nåværende XML-hash eller likt tall dokumenterer historiske
  input-byte, runtime eller full semantisk paritet. Resultatstatus er fortsatt
  **`MATCH_PROVISIONAL`, `MISMATCH_PROVISIONAL`, `NOT_COMPARABLE`**.
- Bare en stabil, fullstendig DWM-resultatindeks med riktig test-ID/status,
  kildefil og arkivdelsidentitet kan brukes for U2; dersom flere enn 20 000
  arkivdelsmålinger vil bli kartlagt, avslås automatisk U2-kobling framfor
  delvis kartlegging uten forklaring.
- For å lukke a11 gjenstår reell prøving mot kjente uttrekk, vurdering av
  alle avvik og eventuelt sterkere kjøringsattestasjon. Arkade 5 Noark-tester,
  flertrådet/multiprosessor-kjøring, kvalitetssikrings- og godkjenningsrapport
  ligger i egne, dokumenterte planpunkter og utvides ikke her.

### a11.4-tester

`tests/test_v021_a11_u1u2.py` verifiserer parser, kildevitner,
arkivdelsidentitet, manglende data, avvikende tittel/rekkefølge, manipulert
kobling, korrekt import/eksport, fortsatt ikke-attestert resultat og at
samme XML-fil ikke hashes for hver U2-rad. Hele Windows-`test.bat` skal
kjøres av bruker etter innlegging av a11.4.

## a11.5 – samlet praktisk QA-kjøring for et valgt Noark 5-uttrekk

Delta **v0.2.1-a11.5** viderefører den grønne a11.4-implementasjonen.
Applikasjonsversjonen forblir `0.2.1-a11`. Nye filer:
`app/noark5_kdrs_practical_qa_v021_a11.py` og
`tests/test_v021_a11_practical_qa.py`; dette dokumentet er endret.

### Hva den nye kommandoen gjør

1. Finner originale `kdrs_query_results_*.txt` i **én valgt katalog** uten
   rekursiv skanning. Klassifiserer filene som `STANDARD`, `U1` eller `U2`
   etter faktiske jobb-ID-er, *ikke* ved å stole på filnavnets postfix.
2. Nekter vilkårlig valg dersom flere filer kan være samme profil. Bruk da
   eksplisitte `--report STANDARD=...`, `--report U1=...`, `--report U2=...`
   i stedet for `--kdrs-dir`.
3. Leser DWM-resultatet fra `--dwm-index` **eller** fra `index.json` i
   `--dwm-run-dir`. Begge viser til **allerede materialiserte** resultatfiler;
   ingen ny tung DWM-/Saxon-kjøring startes.
4. `--preflight` leser rapportmetadata, opprinnelige jobb-ID-er, DWM-
   resultatstatuser og XML-filenes tilstedeværelse/størrelse uten å lese
   XML-byte eller beregne SHA-256 av XML. Manglende U1/U2-regresjonsresultat
   er WARNING, manglende nødvendig XML er FEIL.
5. Ved full kjøring brukes de eksisterende a11.3/a11.4-modulene uendret til
   kildekontroll, strømmet SHA-256 og resultatavstemming. Alle **9 filene**
   bygges i en egen midlertidig katalog ved siden av angitt output-katalog
   og publiseres først når hele pakken er ferdig. Kilde, DWM Work-resultater
   og historiske KDRS-rapporter endres aldri.
6. To nye overordnede rapporter:
   `noark5-a11-practical-qa.json` og `noark5-a11-practical-qa.md`. Disse
   viser valgt Noark-versjon, profiler, antall importerte jobber, antall
   kartlagte resultater, foreløpige treff/avvik/ikke sammenlignbare rader,
   import- og kilde-QA og hva som må gjennomgås manuelt.

### Windows – først forhåndskontroll

Bytt ut **eksempelstiene** med ett faktisk Noark 5-uttrekk og den tilhørende
historiske KDRS-kjøringen. `--dwm-run-dir` må være den eksisterende DWM-
XPath-kjøremappen hvor `index.json` ligger. For U1/U2 kreves det at DWM har
kjørt regresjonsprofilen som materialiserer `kdrs.u01` / `kdrs.u02`.

```powershell
py -m app.noark5_kdrs_practical_qa_v021_a11 `
  --dwm-root "C:\git\IKAMR\data-workflow-manager" `
  --xml-root "D:\noark5\uttrekk" `
  --kdrs-dir "D:\kdrs\uttrekk" `
  --dwm-run-dir "D:\dwm\xpath-regresjon" `
  --noark-version 5.0 `
  --preflight
```

Kontroller at de tre rapportprofilene hører til **samme uttrekk**, og at
XML-filene og forventede DWM-resultatene faktisk finnes. Dette steget
oppretter ingen rapportmappe og hashes ikke store XML-filer.

### Windows – komplett rapportpakke

Når forhåndskontrollen er tilfredsstillende, kjør samme kommando uten
`--preflight` og med **ny, tom/ikke-eksisterende** output-sti:

```powershell
py -m app.noark5_kdrs_practical_qa_v021_a11 `
  --dwm-root "C:\git\IKAMR\data-workflow-manager" `
  --xml-root "D:\noark5\uttrekk" `
  --kdrs-dir "D:\kdrs\uttrekk" `
  --dwm-run-dir "D:\dwm\xpath-regresjon" `
  --noark-version 5.0 `
  --output-dir "C:\temp\noark5-a11.5-qa"
```

Har KDRS-katalogen resultater fra flere kjøringer, velg filene eksplisitt:

```powershell
py -m app.noark5_kdrs_practical_qa_v021_a11 `
  --dwm-root "C:\git\IKAMR\data-workflow-manager" `
  --xml-root "D:\noark5\uttrekk" `
  --report "STANDARD=D:\kdrs\kdrs_query_results_uttrekk_clean.txt" `
  --report "U1=D:\kdrs\kdrs_query_results_uttrekk_U01.txt" `
  --report "U2=D:\kdrs\kdrs_query_results_uttrekk_U02.txt" `
  --dwm-index "D:\dwm\xpath-regresjon\index.json" `
  --noark-version 5.0 `
  --preflight
```

Standard alene er også gyldig. U1/U2-koblinger som ikke finnes i eksisterende
DWM-regresjonsresultater får status **NOT_COMPARABLE**, aldri null eller OK.

### Tolkning og videre arbeid

- `MATCH_PROVISIONAL`: de eksplisitt kartlagte verdiene samsvarer på angitt
  kontrollgrunnlag; ikke en normativ samsvarserklæring.
- `MISMATCH_PROVISIONAL`: forskjell som skal undersøkes med kilde-XML,
  XPath-kilde og DWM/KDRS-resultatene side om side.
- `NOT_COMPARABLE`: nødvendig input, test, identitet eller resultat mangler;
  dette er ikke «bestått» og skal ikke omregnes til null.
- Full QA-kjøring som skriver rapporter kan returnere exit-kode 0 også når
  et avvik er registrert. Exit-koden betyr **vellykket rapportgenerering**,
  ikke bestått Noark 5-validering. Se rapportens `review_status`.
- SHA-256 for nåværende XML-innhold kan ikke bevise hvilke byte KDRS/Saxon
  brukte historisk. `whole_saxon_lxml_parity_verified=false` og
  `normative_noark_conformance_verified=false` beholdes alltid.
- Dersom `--preflight` viser flere kandidater, feil XML-rot eller manglende
  DWM-regresjonsresultater, skal brukeren avklare kildevalg og kjøring **før**
  avvikene tolkes. Ikke start automatisk tung reanalyse.

Før a11 kan ferdigstilles, må minst ett **faktisk IKAMR-uttrekk** prøves med
Standard/U1/U2 og dokumenterte kontrollresultater. Alle foreløpige avvik må
vurderes og kildegrunnlag/versjon/profil journalføres. Dette er et eget teknisk
QA-grunnlag før kommende kvalitetssikringsrapport til arkivskaper og depotets
Godkjennings-/ferdigstillingsrapport.

Arkade 5 Noark-tester og flertrådet/multiprosessorkjøring er fremdeles utsatt
og registrert i `docs/TODO-ROADMAP.md`; de blir ikke implementert som en
bivirkning av a11.5.
