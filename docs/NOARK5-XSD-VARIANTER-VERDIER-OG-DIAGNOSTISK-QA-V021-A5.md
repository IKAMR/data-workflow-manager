# Noark 5 – XSD-varianter, verdier og diagnostisk QA

**Arbeidsgrunnlag:** DWM v0.2.1-a4, commit `0a258ee6919b59857b24285f859ccc3637c31c9f`.

**Intern autoritativ kilde:** `IKAMR/digital-archive-workflow` commit
`82bd59f23aafdc2386e317e5492941862c2bab9a`, under
`docs/kilder/noark/noark5/v{3.1,4.0,5.0}/`.

**Status:** Teknisk arbeidsgrunnlag. Ingen normativ godkjenning eller endring av
originale spesifikasjoner, XSD-er, DWM-standardverdier eller eksisterende
XPath-beregninger. Se bindende policy i `docs/NOARK-SOURCE-LIBRARY.md`.

## 1. Viderefør eksisterende XSD-register – ikke lag en ny fasit

DWM har allerede:

- `config/noark5/standards/noark5_xsd_signatures_v0114_a5.json`: 20 kjente
  rå SHA-256-signaturer for fem XSD-filer i hver av v3.0, v3.1, v4.0 og v5.0.
- `app/noark_xsd_version_v0114_a5.py`: identifikasjon av uttrekksversjon
  ut fra skjema/@version, namespace, kjente bytevarianter og kildeevidens.
- `app/noark_xsd_local_evidence_v0114_a6.py`: allerede etablert Work-lokal
  variantlogg `noark5_evidence/xsd_variants.json`, per jobb.

Nytt analyseverktøy: `app/noark_xsd_variant_qa_v021_a5.py`.
Det leser referanse-XSD direkte fra en **lokal utsjekking** av vår samling,
og kan sammenstille eksisterende Work-logger for eksplisitt utvalgte jobber.
Ingen rekursiv skanning av alle disker og ingen automatisk oppdatering av
referansesamlingen.

### Variantidentitet

| Klassifisering | Beslutningsgrunnlag | Tolkning |
| --- | --- | --- |
| `exact_reference_bytes` | Samme rå SHA-256 | Identisk byteinnhold med valgt intern referanse |
| `line_endings_only` | Ulik rå SHA-256, lik SHA-256 etter *kun* CRLF/LF/CR-normalisering | EOL-variant, behold begge rå SHA-256 |
| `content_variant_requires_qa` | Innholdsforskjell også etter EOL-normalisering | Ukjent/endret XSD; kan være lokal modifikasjon eller leverandørvariant |
| `declared_version_conflict` | Ulik `xs:schema/@version` | Versjonskonflikt, ikke velg automatisk |
| `namespace_conflict` | Ulik targetNamespace | Avvik, ikke automatisk ekvivalens |
| `authoritative_reference_missing` | Referansefil kan ikke leses | Ukjent, ikke godkjent |

**Viktig:** Den eksakte SHA-en er nødvendig for bevis for hva som faktisk ble
brukt. Normalisert SHA er sekundær likhetsindikasjon, **ikke** erstatter for
rå bytes, og er ikke et bevis på at hele Noark-spesifikasjonen er oppfylt.
Bruk korrekt originalt kilde-commit; aldri «nyeste» uten registrert QA.

## 2. M300 og M619 – direkte sammenligning av våre egne XSD-er

| Metadata | Noark 5 v3.1 XSD | v4.0 XSD | v5.0 XSD |
| --- | --- | --- | --- |
| M300 `dokumentmedium` | Enumeration, 3 verdier | Enumeration, 3 verdier | `minLength=1`, ingen enumeration |
| M619 `avskrivningsmaate` | Enumeration, 5 verdier | Enumeration, 7 verdier | `minLength=1`, ingen enumeration |

M619 i v3.1: `Besvart med brev`, `Besvart med e-post`, `Besvart på telefon`,
`Tatt til etterretning`, `Tatt til orientering`.

M619 i v4.0 har de samme fem samt `Besvart med notat` og `Saken ble avsluttet`.

**QA-åpent:** Bruker opplyser at Noark-spesifikasjonen åpner for lokale/custom
avskrivningsmåter også der v3.1/v4.0-XSD begrenser til en enumeration.
Dette må verifiseres **på eksakt side/kravtekst i interne PDF-/DOCX-filer** før
vi formulerer endelige normative regler. XSD-avvisning og mulig lovlig lokal
verdi skal dokumenteres separat. En modifisert XSD skal aldri merkes som
originalt godkjent skjema.

**Hele XSD-enumeration-dekningen:** v3.1 har 17 M-typer med enumeration,
og v4.0 har 17. Av disse har DWM ni standardverdisett for hver versjon.
De åtte som ennå ikke er registrert for begge versjonene, er M056, M087,
M089, M450, M503, M506, M508 og M619. De ni registrerte har én bokstavelig
verdi-uoverensstemmelse: M300. I v5.0 har ingen M-typedefinisjoner fast
XSD-enumeration, men DWM har 18 faglige verdireferanser. Derfor må ikke
«ikke i DWM-verdisett» likestilles med en XSD-feil i v5.0.

**Tidligere QA-funn opprettholdes:** DWMs M300-standardverdisett bruker
`Fysisk arkiv` for v3.1/v4.0, mens begge referanse-XSD-er har `Fysisk medium`.
Forskjellen korrigeres ikke automatisk. For v5.0 har XSD ikke enumeration;
maskinelle standardverdier og en streng XSD-verdiliste er to forskjellige ting.

**DWM-kontroll i dag:** `F06` i `config/noark5/tests/xpath_catalog_2026_05_26.json`
teller/grupperer `avskrivningsmaate` (`method_counts`), men er **ikke**
versjonsspesifikk normativ verdikontroll. Original opptelling bevares.

## 3. Diagnostisk modifiserte XSD-er og sporbar klarering av feil

Opprett en *separat kopi* av skjema og dets avhengigheter; ikke endre original
XSD i `digital-archive-workflow` og ikke endre XML-uttrekket.
Valider **samme XML** to ganger:

1. Mot uendret originalt XSD-sett, med rå SHA-256 for alle XSD-avhengigheter.
2. Mot separat diagnostisk XSD-sett, med egne rå SHA-256 for alle XSD-er.

Registrer: XML-fil og SHA-256, begge XSD-settene, antall opprinnelige feil,
antall etter diagnostisk endring, identifiserte *forsvunne* feilmeldinger,
identifiserte *nye* feilmeldinger, XML-linje/kolonne/sti og feiltype.
Behold alltid første valideringsresultat uendret.

Eksempel på QA-evidens: `original_error_count=37`,
`diagnostic_error_count=4`, `error_occurrences_removed=34`,
`error_occurrences_introduced=1`. Et nettofall på 33 er **ikke** nok:
34 gamle feil forsvant, men én ny kom til. Dette er et illustrativt eksempel,
ikke resultat fra et konkret arkivuttrekk.

**Ingen automatisk godkjenning:** At diagnostisk XSD gir 0 feil betyr ikke
at arkivuttrekket er i samsvar med Noark 5. Det er et dokumentert eksperiment
som kan brukes ved faglig vurdering.

Den første sammenligningsfunksjonen er avgrenset til **små XML-eksempler
(64 MB)**. Stor/skalerbar depotvalidering må bygges på eksisterende
`noark5_workflow/analysis/xml_schema_validation.py` sin strømmebaserte motor;
dette verktøyet er foreløpig en sikker diagnostisk arbeidsflate, ikke en
erstatning for produksjonsvalideringen.

## 4. Logiske verdigrupper uten å skjule originalverdi

Lag en separat, **QA-godkjent** oversikt over verdier som representerer samme
begrep; ikke rediger original XML, eksisterende XSD eller DWM-verdiregistre
på grunnlag av tekstlikhet alene.

- `exact_reference_value`: eksakt literal i valgt versjonert referanse.
- `formatting_candidate_needs_qa`: forskjell i store/små bokstaver eller
  gjentatte mellomrom, men samme tekst etter forsiktig sammenligning.
- `similar_text_candidate_needs_qa`: mulig skrivefeil, bortfalt mellomrom,
  bokmål/nynorsk eller en annen frase. Aldri automatisk gyldig verdi.
- `operator_approved_alias`: kun hvis en **eksplisitt innsendt, allerede
  QA-godkjent** aliasliste sier dette. Alias er fremdeles ikke identisk med
  original XSD-enumeration, og den faktiske XSD-validiteten endres ikke.
- `unknown_needs_qa`: ingen sikker kandidat.

Eksempler for menneskelig QA (observerte formuleringer oppgitt av bruker):

| Originalverdi | Mulig logisk verdi | Foreløpig status |
| --- | --- | --- |
| `Besvart i Telefon` | `Besvart på telefon` | Kandidat – ulik ordlyd |
| `Elektronkskarkiv` | `Elektronisk arkiv` | Kandidat – skrivefeil og manglende mellomrom |
| `utgåande dokument` | `Utgående dokument` | Kandidat – bokmål/nynorsk, ikke automatisk ekvivalens |
| `elektronisk   ARKIV` | `Elektronisk arkiv` | Kandidat – mellomrom/versalisering |

Råform og antall forekomster bevares; en logisk, godkjent gruppering kan
**komme i tillegg** som egen rapportkolonne. Krav- og XSD-validitet beholdes
som separate felt.

## 5. Lokal, skrivebeskyttet kartlegging

Krever `lxml`, allerede brukt av DWM, og en lokal utsjekking av
`IKAMR/digital-archive-workflow`.

Eksempel på Windows (tilpass Work- og Source-stiene):

```bat
py -m app.noark_xsd_variant_qa_v021_a5 ^
  --reference-root "C:\git\IKAMR\digital-archive-workflow" ^
  --schema "D:\eksempeluttrekk\schemas\arkivstruktur.xsd" ^
  --work-root "D:\DWM-Work" ^
  --output "D:\DWM-Work\noark5-xsd-variant-qa.json"
```

Verktøyet forsøker å identifisere referanse-repoets faktiske Git HEAD. Dersom
`--source-commit` oppgis og ikke stemmer med utsjekkingen, avvises kjøringen.
Når Git-revisjonen ikke kan leses, markeres kildecommiten som uverifisert.

For opptelling av tidligere observerte XSD-varianter, legg til eksplisitt
`--work-ledger "D:\DWM-Work\Jobb1"` per jobb. Dette leser **eksisterende**
`Jobb1\noark5_evidence\xsd_variants.json`, uten å skrive om observasjonene.

For diagnostisk sammenligning kan følgende valg legges til:

```bat
--diagnostic-xml "D:\eksempeluttrekk\arkivstruktur.xml" ^
--diagnostic-original-schema "D:\original-schemas\arkivstruktur.xsd" ^
--diagnostic-modified-schema "D:\diagnostic-schemas\arkivstruktur.xsd"
```

Legg `metadatakatalog.xsd` ved siden av **hvert** hovedskjema dersom
hovedskjemaet importerer det. Programmet hasher begge skjemaene; endringen
kan ligge i `metadatakatalog.xsd`, selv om `arkivstruktur.xsd` er identisk.

Bruk alltid et etablert Work-område, **ikke** Source, til rapporten. Programmet
har sperrer mot å plassere output i referanse- eller XSD-mappen.

Med `--dwm-root "C:\git\IKAMR\data-workflow-manager"` kan DWM-registeret
sammenholdes automatisk med **alle** enumerationene for de tre versjonene.
Rapporten viser antall kildedefinisjoner, manglende oppføringer og eksakte
verdiavvik. Ingen registre skrives om.

## 6. Avgrensninger og videre QA

- Ingen av kilderepoets PDF-, DOCX- eller XLSX-dokumenter er endret.
- Full normativ kontroll av lokalt definerte M619-verdier mot den **eksakte
  standardteksten** er fremdeles åpen. XSD alene svarer ikke på dette.
- Ingen QA-godkjente aliaspar er opprettet; alle eksemplene er kandidater.
- Ingen automatisk korrigering av leverandørverdi eller XSD-fil.
- Ingen GUI-integrasjon eller generell produksjonsvalidering av store uttrekk.
- Ingen sentral depotdatabase er opprettet. Eksisterende Work-ledger beholdes;
  verktøyet kan aggregere **eksplisitt utvalgte** jobber i en lokal rapport.
- Full krav-for-krav-gjennomgang av hoveddokumentene for 3.1, 4.0 og 5.0
  gjenstår, som dokumentert i `docs/NOARK5-REPO-VS-SPEC-QA-2026-11-15.md`.

**Neste implementering:** Bruke den versjonerte varianten, faglig godkjente
verdigrupper og diagnostisk XSD-evidens i DWMs kanoniske resultatmodell, uten
å gjøre endret XSD eller tekstnormalisering til en bestått normativ test.
