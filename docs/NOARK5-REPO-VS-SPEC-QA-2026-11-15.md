# Noark 5: kildebasert QA av DWM mot egne spesifikasjoner

**Dato:** 2026-11-15  
**Status:** Teknisk kildeinventar og avviksanalyse utført; full normativ, punktvis dokumentgjennomgang er **ikke** fullført.  
**Kildeprioritet:** `IKAMR/digital-archive-workflow` først; eksterne dokumenter er kontrollkilder, aldri automatisk erstatning. Historiske XPath-originaler: `IKAMR/KDRS_Query`.

## 1. Fiksert kildegrunnlag

| Rolle | Repositorium | Kontrollert commit |
| --- | --- | --- |
| Intern autoritativ Noark-samling | [`IKAMR/digital-archive-workflow`](https://github.com/IKAMR/digital-archive-workflow) | `82bd59f23aafdc2386e317e5492941862c2bab9a` |
| Originale historiske XPath-tester | [`IKAMR/KDRS_Query`](https://github.com/IKAMR/KDRS_Query) | `a68d809ee04c8aceb75976c668bf9746e26d67cb` |
| DWM, siste verifiserte commit ved a5-analysen | [`IKAMR/data-workflow-manager`](https://github.com/IKAMR/data-workflow-manager) | `0a258ee6919b59857b24285f859ccc3637c31c9f` (`v0.2.1-a4`) |
| Historisk analysegrunnlag for denne rapporten | Før a4-commit | a3 + a4-deltaene; a4 ble siden committet 2026-11-15 |

`docs/NOARK-SOURCE-LIBRARY.md` og rotfilen `AGENTS.md` setter kildepolicyen. En revisjon av et kildedokument krever referanse til riktig versjon, fil og commit. Oppdateringer av intern samling ved avvik mot eksterne kilder skjer **bare etter QA-beslutning med repoets eier**. Ingen kildedokumenter, XSD-er eller normative registre er skrevet om i denne pakken.

## 2. Omfanget av materiale i den interne kildesamlingen

| Versjon | XSD | Hovedspesifikasjon og vedlegg, inklusive eksempeldata | Filtyper |
| --- | ---: | ---: | --- |
| 3.1 | 5 | 7 | 5 PDF, 1 XLSX med kravtabell, 1 XML |
| 4.0 | 5 | 13 | 6 PDF, 6 DOCX, 1 XML |
| 5.0 | 5 | 9 | 4 PDF, 4 DOCX, 1 XML |
| **Sum** | **15** | **29** | **44 kilderelevante filer** |

Følgende skjemaer finnes for hver av de tre versjonene: `arkivstruktur.xsd`, `endringslogg.xsd`, `loependeJournal.xsd`, `metadatakatalog.xsd`, `offentligJournal.xsd`. I tillegg ligger en README per versjon. Filene er oppført i `docs/kilder/noark/SOURCE-MANIFEST.json`, unntatt README.

**Integritetskontroll:** 15 av 15 SHA-256 i manifestet ble reprodusert fra innholdet i GitHub ved rekonstruksjon av opprinnelige CRLF-linjeskift. GitHub gir LF-normalisert tekst og derfor andre råfilstørrelser. Dette er **ikke** et konstatert kildeavvik. Ved lokal kjøring viser revisjonsverktøyet `identical_bytes` eller `matches_original_after_restoring_crlf`, ikke et falskt feilsignal.

**Opphav:** Samlingen er vår interne fasit, men `SOURCE-MANIFEST.json` har foreløpig `source_status: not_documented` for Noark 5-filene. Samme dokument har `publication_permission_verified: false`. Dette gjelder kildeproveniens, ikke dokumentert teknisk inkompatibilitet. Før vi kaller bestemte eksterne utgaver identiske, kreves direkte byte-/tekstkontroll og QA.

## 3. Skjemaanalyse: metadata og strukturelle endringer

Metadata-ID-er her er **annoterte XSD-typedefinisjoner**, ikke fullstendig registrert normativt kontrollomfang. I v5.0 inngår eksempelvis hjelpetypen `M016 ID`.

| Kontroll | v3.1 | v4.0 | v5.0 |
| --- | ---: | ---: | ---: |
| XSD-typedefinisjoner med M-ID i `metadatakatalog.xsd` | 158 | 158 | 159 |
| Registrerte M-ID-er i DWMs metadataregister | 9 | 9 | 23 (a4) |
| Registrerte krav i DWM | 0 | 0 | 6 (a4) |
| Standardverdisett registrert i DWM | 9 | 9 | 18 |
| `arkivstruktur.xsd`: elementdeklarasjoner | 271 | 271 | 282 |
| `arkivstruktur.xsd`: unike elementnavn | 166 | 166 | 167 |
| `loependeJournal.xsd`: elementdeklarasjoner | 41 | 41 | 51 |
| `offentligJournal.xsd`: elementdeklarasjoner | 36 | 36 | 44 |

Mellom **3.1 og 4.0** endres blant annet datatypene for `M104 mottattDato` og `M105 sendtDato` fra `xs:dateTime` til `xs:date`. Endringer forekommer også i verdimengder for M087 og M619.

Mellom **4.0 og 5.0** har 118 annoterte M-typedefinisjoner minst én forskjell i navn, base, enumeration, minLength eller annen enkel facet. Særlig viktige eksempler er `M010 sakspartID` -> `partID`, `M302 sakspartNavn` -> `partNavn`, `M303 sakspartRolle` -> `partRolle`, `M506 gradering` -> `grad`, `M707 filstoerrelse` fra `xs:string` til `xs:integer`, og `M001 systemID` med strengere ID-form. `M056` har typebetegnelsen `presedensStatus` i v5.0 og `presedensstatus` i v3.1/4.0. Dette er faktiske XSD-forskjeller, men betydning for hver kontroll krever per-kontekst gjennomgang.

## 4. Sammenhold mot DWMs kontroller

- `config/noark5/tests/xpath_catalog_2026_05_26.json` har **60** testdefinisjoner: **58 aktive** og **2 regresjonsreferanser** (U1/U2). **57** er merket `master_query_subtype_needs_qa` for versjonsgrunnlag. 59 er deklarert for alle tre versjoner, én kun for 5.0. Dette er deklarasjoner, ikke en fullstendig godkjent gyldighetsmatrise.
- Testenes primære XML-kilder: `arkivstruktur.xml` **50**, `loependeJournal.xml` **4**, `offentligJournal.xml` **3**, `arkivuttrekk.xml` **2**, `endringslogg.xml` **1**. **45** defineres som vanlige metrikkjobber og **15** som spesial-/sammensatte jobber.
- Standardverdikontroll: **16** referanser fordelt på **12** tester. Det finnes **ingen eksplisitt `normative_requirement_refs`** i katalogens testdefinisjoner.
- En konservativ tokenanalyse av deklarerte XPath-metrikker identifiserte **43 av 158** M-typenavn for v3.1, **43 av 158** for v4.0 og **44 av 159** for v5.0. Disse tallene er **ordtreff, ikke 27-28 % normativ dekning**. De 15 spesialhandlerne og annen beregning er ikke fullt semantisk mappet av denne leksikalske metoden. Fravær av treff er ikke bevis for fravær av implementasjon.
- `config/noark5/xml_schema_validation.json` har **kun ett XSD-valideringstrinn:** `arkivstruktur.xml` mot lokal `arkivstruktur.xsd` funnet i uttrekket. `noark5_workflow/operations/validate_xml_schema.py` kjører første og eneste definisjon. Dette er nyttig reell `lxml` XSD-validering, men **ikke systematisk validering av alle 5 dokumenttypene mot den versjonerte referansesamlingen**. XPath-beregninger er en annen type kontroll.
- Historiske originaler: Alle fem `xml-queries_noark5_2026-05-26*.txt` i DWMs `docs/reference/kdrs-query/` er **byte-identiske Git-blobber** med `IKAMR/KDRS_Query/doc/` ved kontrollerte kildecommitter. Identisk referansefil er ikke bevis på at alle uttrykk kjører semantisk likt i DWM/lxml som i KDRS/Saxon.
- a4s fire nye verifiserte v5.0 M-felt (M002, M003, M005, M007) har matchende feltnavn og typer i v5.0 XSD, men **påstandene om obligatorisk plassering, kontekst og sidetall fra Vedlegg 1 er ikke uavhengig normativt kontrollert i denne analysen**. De fire kravene er korrekt merket `implemented_as_dwm_control: false`. De to opprinnelige funksjonskravene er heller ikke uttrekkstester.

## 5. Åpne QA-saker / beslutningspunkter

| ID | Funn og kilder | Alvor / handling | Beslutning |
| --- | --- | --- | --- |
| **QA-N5-001** | `M300 dokumentmedium`: v3.1 og v4.0 `schemas/metadatakatalog.xsd` oppgir `Fysisk medium`; DWM `noark5_standard_values.json` oppgir `Fysisk arkiv`. Alle øvrige sammenlignbare XSD-enumeration-verdier i disse registrene samsvarte. | Kan gi feilaktig WARNING i verdilisteavstemming. Kontroll mot Vedlegg 1 og godkjenning før endring. | **Åpen, krever brukers QA** |
| **QA-N5-002** | M056 og M506, samt `sakspart` / `part`, har versjonsspesifikke navn. DWM har bl.a. `M506` med navn `gradering` i v5-registret; XSD-type er `grad`, mens overordnet XML-element `gradering` fortsatt finnes. | Før eksplisitte alias- og kontekstregler, ikke automatisk strenglikhet. | Kartleggingspunkt |
| **QA-N5-003** | DWM XML/XSD-operasjon validerer bare `arkivstruktur.xml`; den interne samlingen har fem XML-skjemaer per versjon. | Utvid testdekning med XSD-validering av relevante XML-typer, versjonssikret og separat fra uttrekksleverandørens XSD-er. | Implementasjon mangler |
| **QA-N5-004** | 57 XPath-definisjoner mangler ferdig verifisert versjonstilknytning; original XPath og semantisk DWM-ekvivalens er ikke fullattestert. | Lag regelbasert matrise per test/versjon, kjør differensialtester med samme uttrekk. | QA-gjennomgang og tester |
| **QA-N5-005** | `SOURCE-MANIFEST.json` har uavklart opphav/utgave og publiseringsrettigheter for versjonsfilene. De fulle normative kravtabellene i PDF/DOCX/XLSX er ikke gjennomgått punktvis her. | Fyll en sporbar kravmatrise per kildefil, side/avsnitt og XSD-komponent, med bruker-QA for avvik. | Kildeverifisering gjenstår |
| **QA-N5-006** | Interne v5 XSD-filer omtaler vedlikehold 2023-11-09 og `5.5.0`. Eksterne publiseringsdatoer og mulige senere XSD-utgaver er ikke direkte innholdssammenlignet. | Bruk Nasjonalarkivet som kontrollkilde; eventuelt avvik forelegges bruker. | Ikke et påvist kildeavvik |
| **QA-N5-007** | Andre analyse-, import-, rapporterings- og Arkade5-integrasjonsmoduler har indirekte validering. Denne gjennomgangen kontrollerer kjernefilene, ikke alle 1857 filer linje for linje. | Utvid maskinell kodelesing og test-evidens per modul ved videre arbeid. | Revisjonsomfang må utvides |

**Ingen kildefil, XSD, verdi eller normativ regel endres automatisk ut fra disse funnene.** Spesielt QA-N5-001 skal avklares med repositoriets eier før korrigering eller godkjent unntak.

## 6. Gjennomføring av full dokument- og testmatrise lokalt

`tools/noark5_internal_source_audit.py` i denne deltaen kan kjøres etter at begge repoene er sjekket ut ved siden av DWM. Den leser alle lokale PDF-, DOCX-, XLSX- og XML-filer i versjonenes `spesifikasjoner/`, med tekstuttrekk når parser er tilgjengelig, og bygger:

- `noark5-source-audit.json`: filinventar, SHA-256, XSD-typer, forekomstbegrensninger, XSD-navn per versjon, M-ID-er, deklarerte XPath-kandidater, standardverdiforskjeller og lokale KDRS-SHA-kontroller.
- `noark5-source-audit.md`: lesbar overordnet rapport med kildecommitter og QA-funn.

Kjør fra DWM-roten:

```bat
py tools\noark5_internal_source_audit.py --dwm-root "C:\git\IKAMR\data-workflow-manager" --source-root "C:\git\IKAMR\digital-archive-workflow" --kdrs-root "C:\git\IKAMR\KDRS_Query" --output-dir "C:\temp\noark5-kilde-qa"
```

PDF krever `pymupdf` eller `pypdf` for tekstuttrekk; uten slik installasjon blir de tydelig markert **ikke lest**. Dette er **inventar og maskinell kandidatkartlegging**, ikke full godkjenning av normative krav eller automatisk dokument-OCR. Originalkilder forblir urørt. PDF-er uten tekstlag krever separat manuell/visuell kontroll. Tekstbasert kravkartlegging må deretter gjennomgås mot faktisk kravordlyd, ikke bare søkestrenger.

## 7. Avgrensning og videre implementering

1. **a4 er committet og pushet** (`0a258ee6919b59857b24285f859ccc3637c31c9f`). Videre QA bygges på denne faste baselinen. Full lokal Windows-test for senere versjoner må fortsatt kjøres ved hver ny delta.
2. Utarbeid full normativ v3.1/4.0/5.0 kravmatrise fra hovedspesifikasjonene og vedleggene, med kravklassifisering (`uttrekksverifiserbart` vs. funksjonskrav), kildeside og signatur. Bruk XSD som teknisk delbelegg og bevar verdi- og datatypeforskjeller.
3. Utvid versjonsspesifikk XML/XSD-validering for de fem XML-typene og knytt funn til originalfil, linje, element og arkivenhet.
4. Gjennomfør semantisk differensialtest for hver KDRS Standard/U1/U2-definisjon mot DWM med identisk testuttrekk; før avvik til QA.
5. Koble normativ matrise og eksterne tester til hovedfunn i DWM uten å likestille metrikkstatus `ok` med normativ godkjenning.

**Konklusjon:** Kildene til alle tre Noark 5-versjonene finnes i vårt repo, og XSD-integriteten samt historiske testkilder er kontrollert. DWM har derimot **ikke komplett kildeverifisert normativ dekning**. Full fagnormativ gjennomgang av hvert avsnitt i binære kildedokumenter krever at dokumentene faktisk tekst-/visuelt åpnes, gjennomgås og kobles til test- og kravregistrene. Dette er ikke påstått ferdigstilt i denne rapporten.

## 8. Videreføring etter a4: XSD-varianter og faglige verdier

Se `docs/NOARK5-XSD-VARIANTER-VERDIER-OG-DIAGNOSTISK-QA-V021-A5.md` for
versjonsspesifikke XSD-enumerationer (M300/M619), identifikasjon av CRLF/LF-varianter,
diagnostisk før/etter-validering og QA-kandidater for observerte ordformer.
Ingen normative regler er automatisk endret.
