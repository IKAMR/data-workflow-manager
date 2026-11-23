# Noark 5 v0.2.1-a8 – kravkandidater, KDRS-dispatch og teknisk XSD-kontroll

**Kilde først:** `IKAMR/digital-archive-workflow`, `docs/kilder/noark/noark5/v3.1`, `/v4.0`, `/v5.0`.
Kilde-commit som er registrert i a7: `82bd59f23aafdc2386e317e5492941862c2bab9a`.
DWM-katalog: KDRS Query Standard/U1/U2 fra `IKAMR/KDRS_Query`; prosjektets originale
tekstkopier skal beholdes. GitHub-repositoriene eller originalkildene blir aldri endret av verktøyene.

## Hensikt og avgrensning

A7 kartla 15/15 identiske Noark 5-XSD-er og 25/26 tekstlesbare
spesifikasjonsdokumenter. Den gjenværende uleste filen er
`v5.0/spesifikasjoner/Noark 5 v 5 vedl2 Metadatakatalog objektsortert.docx`.
A7 registrerte 1 886 **nummererte tekstkandidater**, herunder datoer,
innholdsfortegnelser og henvisninger. Disse er **ikke** 1 886 bekreftede krav.

A8 introduserer tre forskjellige verktøy:

1. **Kravreview:** `app/noark5_requirement_review_v021_a8.py` leser a7-rapporten,
   original v3.1-XLSX og hovedstandardens PDF for v4.0 og v5.0 fra egen lokal
   kildesamling. Hvert funn lagres med Noark-versjon, originalordlyd eller
   *uttrykkelig avkortet PDF-linjekandidat*, dokumentnavn, rad/side/linje og
   kildens SHA-256. V3.1 XLSX gir egne kravtype-kolonner O/B/V og
   betingelsesnotater når de er til stede. PDF-tabeller krever fremdeles
   menneskelig kontroll av linjebrudd/kolonnerekkefølge og kravtype.
2. **KDRS-implementasjonsreview:** `app/noark5_kdrs_semantic_audit_v021_a8.py`
   kartlegger de 60 katalogtestene til de originale KDRS-blokkene og kontrollerer
   DWMs 15 spesialbehandler-kjøringsarter mot *faktisk* `_special`-dispatch i
   `noark5_workflow/analysis/xpath_test_engine.py` ved AST-inspeksjon. Katalogjobb-ID,
   originaluttrykkets hash, Python-motorens hash og leksikalsk uttrykkssporing
   registreres. **Det er ikke verifisert at Saxon og lxml beregner samme svar**.
3. **Teknisk XSD for opptil fem XML-filer:**
   `app/noark5_xsd_full_xml_v021_a8.py` tar eksplisitt Noark-versjon og
   validerer `arkivstruktur.xml`, `endringslogg.xml`, `loependeJournal.xml`
   og `offentligJournal.xml` mot hver sin versjonsspesifikke original-XSD.
   `metadatakatalog.xsd` er en *felles schemaimport*, ikke et femte XML-uttrekk.
   `arkivuttrekk.xml` testes separat mot en faktisk medfølgende `addml.xsd`
   dersom denne finnes. Denne ADDML-skjemaets normative identitet er **ikke**
   automatisk godkjent. Manglende XML gir `XML_FILE_NOT_PRESENT` (NOTE),
   ikke automatisk standardbrudd. Store filer over 256 MB får
   `SKIPPED_LARGE_XML` (WARNING); ingen falsk beståttstatus.

Alle funn bevarer opprinnelig tekst og original SHA. Ingen normativt krav eller
semantisk alias godkjennes av a8. M300 (`Fysisk medium` / `Fysisk arkiv`) og
M619-varianter krever fremdeles egen faglig QA.

## Kravreview – kjør på lokal originalsamling

Kjør fra rotmappen til `data-workflow-manager`:

```bat
py -m app.noark5_requirement_review_v021_a8 --a7-report "C:\temp\noark5-a7-qa-med-pdf\noark5-a7-matrix.json" --source-root "C:\git\IKAMR\digital-archive-workflow" --output-dir "C:\temp\noark5-a8-qa"
```

`--a7-report` er **de riktige** a7-filene fra PDF-lesekjøringen (25/26).
`--output-dir` må være ny og separat fra begge Git-repoene; det overskrives ikke.
Programmet viser framdrift ved åpning av standardenes PDF-sider.

Genererte filer:

- `noark5-a8-requirements.json`: registrerte krav, XLSX-radkandidater,
  PDF-linjekandidater og øvrige talltreff – **fire forskjellige kildetyper**.
- `noark5-a8-requirements.csv`: søkbar QA-matrise med kilden og tekniske
  XPath-kandidater, beskyttet mot CSV-formelkjøring.
- `noark5-a8-kdrs.csv`: alle KDRS-/DWM-jobbene med teknisk dispatch,
  originalkilde og behov for semantisk kontroll.
- `noark5-a8-docx-diagnostics.json`: forklaring for kilde-DOCX uten tekstnoder
  (tegninger/embedded parts/altChunk), uten OCR eller falsk PDF-ekvivalens.
- `noark5-a8-summary.md`: korte oppsummeringstall og QA-sperrer.

### GUI

Åpne **«Vis alle XPath-kontroller...»** fra resultatoversikten. Fanen
**«Krav- og KDRS-review a8»** har *Krav og kildekandidater* og
*KDRS Standard/U1/U2 – teknisk QA*. Importer den nye
`noark5-a8-requirements.json` manuelt. Filtrer på Noark-versjon,
**FEIL/WARNING/NOTE**, kildeklasse og søkeord. Dette er en leseflate, ikke
et grensesnitt for å endre originaldokumenter eller godkjenne normative krav.

## Teknisk XML/XSD-validering – egen valgfri analyse

Eksempel med **eksplisitt valgt** Noark 5 v5.0. Bytt til faktisk rotmappe
med de fem XML-filene for det uttrekket som skal undersøkes:

```bat
py -m app.noark5_xsd_full_xml_v021_a8 --extraction-root "D:\arkiv\uttrekk" --source-root "C:\git\IKAMR\digital-archive-workflow" --noark-version 5.0 --output "C:\temp\noark5-a8-xml-xsd.json"
```

Programmet skriver ikke til uttrekket eller kildesamlingen, og krever at
rapporten legges utenfor disse. Før bruk kontrolleres SHA-256 for de originale
XSD-filene mot **baade** lokalt kildemanifest og DWMs pinnede XSD-signaturregister,
inkludert lokale schemaimports. Etter en XSD-feil vises antall og
originalmeldinger (opp til 250 eksempler per fil). XML/XSD-gyldighet er ikke
lik oppfyllelse av *alle* Noark 5-krav; fravær av valideringsfeil skal ikke
brukes som normativ godkjenning.

**Ressursgrenser:** maksimum 256 MB per XML; dette er en diagnostisk
lxml-variant, ikke streamingskalerbar fullavleveringskontroll. Ingen
leverandørtilpassede XSD-filer byttes inn uten eksplisitt diagnostisk QA.

## Installasjon og testing

`install.bat` installerer alle avhengighetene via `requirements-core.txt`:
`lxml`, `psutil` og `pypdf`. GUI-installering omfatter PySide6 og ReportLab.
**Ingen manuell `pip install` kreves** for a8.

Kjør `test.bat` på Windows etter utpakking av deltaen. Målrettede tester:

```bat
py -m unittest discover -s tests -p "test_v021_a*.py"
```

## QA-gjeld

- Gjennomgå *hele* normteksten med korrekte PDF-tabellkolonner,
  versjonsstatus og betingelser. Opptelling av tekniske kandidater er ikke
  opptelling av normative krav.
- Identifiser hvilke standardkrav som faktisk kan kontrolleres i en statisk
  arkivavlevering, og opprett **kildeverifiserte** DWM-kontroller for disse.
- Sammenlign samtlige KDRS/Saxon Standard/U1/U2-svar mot DWMs lxml/Python-
  svar på *identiske* uttrekk før påstand om semantisk paritet.
- Avklar hvorfor DOCX-katalogen v5.0 ikke gir tekstnoder; PDF-versjonen er
  tekstlest, men innholdet er ikke bevist identisk med DOCX-filen.
- Utfør faktisk fullskala XSD-evaluering mot relevante uttrekk der uttrekk
  er større enn den diagnostiske grensen, med eksplisitte ressurs-/jobbrammer.
