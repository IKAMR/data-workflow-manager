# Noark 5 a7: kildebasert XSD- og kravmatrise

**DWM:** v0.2.1-a7, basert på pushet a6 `c6e491f862b6e4edaacdd6f53cf4cf035e116b97`.

**Intern autoritativ kildesamling:** `IKAMR/digital-archive-workflow`, katalog
`docs/kilder/noark/noark5/v{3.1,4.0,5.0}/`, referanse-commit
`82bd59f23aafdc2386e317e5492941862c2bab9a`. KDRS Query Standard/U1/U2
kommer fra `IKAMR/KDRS_Query`. Hver versjon holdes adskilt. Les `AGENTS.md`
og `docs/NOARK-SOURCE-LIBRARY.md` før nye Noark-endringer.

## 1. Implementert i a7

- `app/noark5_requirement_matrix_v021_a7.py` bygger én **read-only**
  deknings-/QA-matrise fra originalt lokalt kilderepo og DWM a6. Den viderefører
  `app/noark5_spec_xsd_trace_v021_a6.py`, de 64 uendrede menings-ID-ene og
  alle KDRS-kandidatkoblinger uten å omskrive dem.
- Registrerer **15 av 15 XSD-er** (fem per Noark 5 v3.1, 4.0 og 5.0) med
  SHA-256 fra kilderepoet, DWM-signaturene og `SOURCE-MANIFEST.json`. Skiller
  `identical_bytes`, `matches_original_after_restoring_crlf`, og reell
  `hash_mismatch_qa` (FEIL i **kilde-QA**, ikke arkivuttrekk).
- Lager én rad per annotert M-typedefinisjon med **versjon, M-ID, XSD-typenavn,
  restriksjoner, linje, elementdeklarasjonskandidater, DWM-registrering,
  XPath-kandidater og eksplisitte standardverdikontroller**. Beholder
  XSD-versjonsdifferanser, herunder M300 og M619.
- Leser **lokale** PDF-, DOCX- og XLSX-spesifikasjonsfiler når tilgjengelige.
  Registrerer kildesti, rå SHA-256, PDF-side eller dokument-/regnearkkoordinat,
  korte tekstutdrag og M-ID-treff. Nummererte tekstledd indekseres separat som
  **kandidater**, ikke som normative krav. Uleselige dokumenter og manglende
  tekstlag markeres tydelig. Det utføres ikke automatisk OCR.
- Viser **seks allerede registrerte v5.0-krav**, og eventuelle krav fra v3.1/v4.0
  dersom de etter faglig kildekontroll blir innført i DWM. Det opprettes ikke
  nye «verifiserte krav» automatisk fra XSD, en tittel eller en tekststreng.
- Qt-dialogen for XPath har nå fanen **«Kravmatrise og XSD»**. Den leser en
  eksplisitt valgt, ferdig generert JSON-rapport, med Noark-versjonsvalg,
  fellessøk, FEIL/WARNING/NOTE-filter og detaljvisning. Ingen bakgrunnsskanning
  eller skriving til Source/Work er knyttet til GUI-visningen.
- Rapportene lagres **kun** der operatøren eksplisitt velger en separat
  resultatmappe. Ingen overskriving av eksisterende rapporter.

## 2. Kjøre mot vår faktiske, lokale kildesamling

Fra DWM-repoet på Windows, etter å ha pakket ut a7-deltaen:

```bat
py -m app.noark5_requirement_matrix_v021_a7 --dwm-root "C:\git\IKAMR\data-workflow-manager" --source-root "C:\git\IKAMR\digital-archive-workflow" --output-dir "C:\temp\noark5-a7-qa"
```

Hvis den lokale kopien av `digital-archive-workflow` er låst til den
kontrollerte referansecommiten, kan du i tillegg sende
`--source-commit 82bd59f23aafdc2386e317e5492941862c2bab9a`.
Hvis HEAD er forskjellig, vil kjøringen avvises. Uten `--source-commit` blir
kildecommiten fremdeles registrert og eventuelt avvik mot a6-registeret
markert som QA.

Resultatmappen inneholder:

1. `noark5-a7-matrix.json` – full, maskinlesbar kilde-/kravmatrise og QA-funn.
2. `noark5-a7-summary.md` – kompakt, maskinelt generert status.
3. `noark5-a7-metadata.csv` – en rad per annotert XSD-M-type/versjon.
4. `noark5-a7-requirements.csv` – eksisterende, registrerte krav per versjon.

Åpne `Resultatvisninger` → XPath-dialogen → «Kravmatrise og XSD» →
**«Åpne generert a7 QA-matrise (.json)...»**, og velg `noark5-a7-matrix.json`.
Velg Noark-versjon og QA-status øverst i dialogen.

For rask teknisk kildesjekk uten å forsøke tekstuttrekk:

```bat
py -m app.noark5_requirement_matrix_v021_a7 --source-root "C:\git\IKAMR\digital-archive-workflow" --output-dir "C:\temp\noark5-a7-qa-uten-dokumenttekst" --skip-document-text
```

PDF-tekstuttrekk krever `pymupdf` eller `pypdf`; ellers blir filene merket
**ikke lest**. `DOCX` og `XLSX` leses med deres XML-format. En DOCX-paragraf
kan **ikke** likestilles med en trykt side i PDF. Originalene er urørt.

## 3. Betydningen av FEIL / WARNING / NOTE

Disse er **kilde- og implementasjons-QA**, ikke hendelser fra en bestemt
XSD-/XPath-validering av et depotuttrekk:

| QA-status | Eksempel | Hva statusen IKKE innebærer |
| --- | --- | --- |
| FEIL | Ukjent XSD-innhold mot kildemanifest; kilde- eller signaturkonflikt | Ikke automatisk FEIL i selve arkivuttrekket |
| WARNING | M300 standardverdiregister avviker fra teknisk XSD, M-ID mangler i DWM-register, eller et uttrekkskontrollerbart krav har ingen verifisert kontroll | Ikke fastslått Noark-regelbrudd |
| NOTE | Bare leksikalsk XPath-treff, ingen XPath-kandidat eller et funksjonskrav som ikke kan kontrolleres fra statisk uttrekk | Ikke bestått normativ test |

**XSD-verdi ≠ normativt akseptabel verdi ≠ semantisk menings-ID.**
M619 «Besvart på telefon» og «Besvart i telefon» kan fortsatt ha samme
semantiske ID og ulike resultater mot v3.1/v4.0 XSD. M300 «Fysisk medium»
versus DWM «Fysisk arkiv» er fortsatt åpen QA-N5-001.

## 4. Dokumentgrunnlag og grenser

Denne implementasjonen **kan** undersøke hele den lokale versjonerte
PDF-/DOCX-/XLSX-kildesamlingen via CLI og gi nøyaktige tekst-/kildepekere.
I dette utviklingsmiljøet var binære originaldokumenter i kilderepoet ikke
nedlastbare for lokal verifisering, og disse er derfor **ikke fullstendig
faglig gjennomgått**. Kode og feiltilfeller er testet med syntetiske XSD-,
DOCX-, XLSX- og PDF-fixturer. Det er ikke produsert en fullstendig, godkjent
normativ kravmatrise.

Teksttreff i hovedspesifikasjon eller vedlegg er **bare kandidater**, ikke
bevis for at en normativ plikt er korrekt tolket, at egendefinerte verdier er
tillatt, eller at KDRS/Saxon og lxml gir samme resultat. Et XSD-element med
`minOccurs=1` er heller ikke uten videre globalt obligatorisk hvis dets
forelder kan utelates eller inngår i en `choice`.

**Gjenstående QA:** systematisk lesing av alle relevante dokumentkrav,
klassifisering av egendefinerte verdier per Noark-versjon og metadatafelt,
full XSD-validering av relevante XML-filer, og differensialkjøring mot
historiske KDRS Standard/U1/U2-resultater på samme uttrekk.

Ingen nye normative sannheter eller akseptregler kan innføres i DWM før
kildekontroll og eventuelt beslutning med repoets eier. DWM-rådata endres aldri.

## Videreføring i a8

Etter a7 er kilde- og metadatamatrisen videreført til et *reviewbart*
kravkandidatregister, teknisk KDRS-dispatchkontroll og valgfri validering av
fire Noark XML-filer pluss `arkivuttrekk.xml` med eget ADDML-skjema.
Se `docs/history/alpha/v0.2.1/NOARK5-KRAVREGISTER-OG-KDRS-QA-V021-A8.md`.
Ingen automatiske kildekandidater er her opphøyd til normativt godkjente krav.
