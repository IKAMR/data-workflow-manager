# Noark 5 – kravkandidater mot DWM-kontroller (v0.2.1-a10)

## Formål og kilder

**Kilderekkefølge:**

- Noark 5 v3.1, v4.0 og v5.0: `IKAMR/digital-archive-workflow/docs/kilder/noark/noark5/`.
- DWM a9 kildekrav: lokal `noark5-a9-requirements.json` fra a9.2, med kilderevisjon og SHA-identitet.
- Implementasjon: faktisk lokal DWM-katalog `config/noark5/tests/xpath_catalog_2026_05_26.json`, motor `noark5_workflow/analysis/xpath_test_engine.py`, teknisk XSD-validering i `app/noark5_xsd_full_xml_v021_a8.py`, XSD-signaturer og lokale `config/noark5/standards/requirements/`.
- Historisk KDRS Query Standard/U1/U2 har originaler i `IKAMR/KDRS_Query`. DWM-katalogen er **ikke en offisiell Noark-kravliste**.

Utgangspunktet for utviklingen er a9-revisjon `42b7d3bd4cff` av DWM og referansecommit `8d28e312e1e38af8cb93bfe05cecef11e09af34f` fra kildebiblioteket. Kildecommit leses alltid fra den **faktiske** a9-rapporten, og a10 låser rapportens SHA-256 sammen med SHA-256 for lokale DWM-kontrollfiler. **a10 endrer ikke normative kilder, XSD, eksisterende XPath eller depotdata.**

## Hva a10 kontrollerer

1. a9-rapportens type, kildebibliotek, kildecommit, versjonsfordeling, kandidat-ID-er og eksplisitte *ikke-verifisert*-flagg.
2. Hvilke XPath-katalogtester som faktisk er definert for hver versjon, med test-ID, eventuelle M-ID-verdisett og ordrett XML-felt fra de konkrete XPath-strengene. For spesialbehandlere gjøres en statisk AST-kontroll av dispatch. AST-kontroll er **ikke** en faktisk testkjøring.
3. Kjøringspunktene for fire Noark 5-XSD-valideringer per versjon og en separat ADDML-variant for `arkivuttrekk.xml`. `metadatakatalog.xsd` er en importert schema-avhengighet, ikke en femte avleverings-XML.
4. Partielle lokalt registrerte DWM-krav (seks v5.0-krav i nåværende register) **som referanser**, ikke som kjørbare valideringsregler.
5. Potensielle koblinger per kravkandidat bare ved helt konkret metadata-ID (`Mnnn`), teknisk XML-felttekst eller eksplisitt XML-filnavn – alltid med kravets Noark-versjon, konkret DWM-kontroll-ID, trefftype og kildeproveniens. Vage omtaler som «arkiv», «klasse» og «mappe» gir ikke automatisk kobling.
6. Original a9-kilde-QA videreføres *uten* å bli til feil i arkivuttrekk. Åpne kildekonflikter (`6.3.25`, `12.2.28`, `2.8.3`) og ikke-attestert PDF/DOCX-tekst blir stående.

**Viktige statusgrenser:**

- `coverage_state = IKKE_VERIFISERT` for alle automatisk behandlede krav; en koblingskandidat innebærer ikke «IMPLEMENTERT».
- `evidence_state = TEKNISKE_KANDIDATER` når konkret tekstkryssreferanse finnes; `INGEN_DOKUMENTERT_KOBLING` ellers. Sistnevnte betyr ikke «mangler i DWM».
- `static_extract_testability = IKKE_FAGLIG_VURDERT`; systemfunksjonskrav blir ikke erklært irrelevante uten vurdering.
- `source_qa_severity` er kildebehandlings-QA, ikke funn fra arkivuttrekk.
- **Ingen normative krav, ingen DWM-kontroller og ingen Saxon/lxml-semantikk blir automatisk godkjent.**

## Kjøring fra DWM-rotmappen

Bruk tidligere a9.2-rapporter som inndata. Kjør `test.bat` først. Generer deretter a10 i en egen resultatmappe:

```powershell
py -m app.noark5_requirement_coverage_v021_a10 --a9-report "C:\temp\noark5-a9.2-qa\noark5-a9-requirements.json" --dwm-root "C:\git\IKAMR\data-workflow-manager" --output-dir "C:\temp\noark5-a10-qa"
```

`--dwm-root` kan utelates når koden ligger i rett repo. Output kan **ikke** ligge i kilderepoet, DWM-repoet eller a9-resultatmappen. Eksisterende a10-filer overskrives ikke.

### Genererte filer

| Fil | Formål |
| --- | --- |
| `noark5-a10-coverage.json` | Full kravmatrise, koblingsvitner, kilde-QA, kontrollinventar, kilde-/kodehash og sperrer for normative påstander |
| `noark5-a10-coverage.csv` | Filtrerbare kravrader med versjon, kravtekst, kilde, QA, koblingsstatus og test-ID |
| `noark5-a10-controls.csv` | Konkrete DWM-kontroller per versjon og antall kildekandidater med ordrette koblinger |
| `noark5-a10-unlinked.csv` | Krav uten **dokumentert koblingskandidat** – ikke automatisk «manglende kontroller» |
| `noark5-a10-summary.md` | Kort status og grensene for vurderingene |

CSV hindrer utføring av celleformler ved åpning i regneark. JSON beholder originalordlyd, kildeposisjoner og koblingsevidens.

### GUI

Åpne **Vis alle XPath-kontroller → Krav- og KDRS-review a8 → Krav–kontroll a10**.

Velg `noark5-a10-coverage.json`. Filtrer kravrader på Noark-versjon (hovedfilter), kilde-QA **FEIL/WARNING/NOTE**, teknisk kobling og dekningsstatus. Vis full dokumentasjon per krav til høyre. Underfanen **DWM-kontrollinventar** viser tekniske kontroller med deklarert versjon, registrert kjøringsart, filhash og antall koblingskandidater. Et visst antall treff er ingen normativ dekningsprosent.

## Begrensninger og videre arbeid

- a10 gjennomfører **ikke** hele kravgjennomgangen mot originale PDF-er. Den bygger videre på a9 sitt eksplisitt uavklarte arbeidsregister (v3.1: 963, v4.0: 974, v5.0: 400). Forskjellen mellom 400 v5.0-krav og 414 a8-PDF-linjekandidater er ikke løst automatisk.
- Et XML-feltnavn eller et `Mnnn`-treff kan ha helt annen normativ betydning enn den observerte DWM-metrikken. Selve regelens omfang, betingelser, kardinalitet og resultat må vurderes før implementert/mangler/ikke relevant kan konkluderes.
- Den statiske katalogen gir ingen bekreftelse på at et kontrollresultat er kjørt eller korrekt. Manglende kildefiler i en kontrollert utsjekk rapporteres, ikke kompenseres ved å gjette.
- For Saxon/lxml-paritet må samme kontroller og testuttrekk sammenlignes faktisk med KDRS Standard/U1/U2 i **a11**.
- For hvert uttrekk kommer samlede FEIL/WARNING/NOTE-rapporter i **a12**, etter at regelbevis og testdekning er gjennomgått.

`tests/test_v021_a10_requirement_coverage.py` gir enhetstester med isolert syntetisk DWM-inventar. Full `test.bat` på Windows med faktisk 60-testkatalog kreves før commit.
