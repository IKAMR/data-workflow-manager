# Noark 5-analysemodell – validering, kontroll og rapportering

## Grunnprinsipp
Arkivskaper er alltid ansvarlig for innholdet i uttrekket. Testing før levering utføres ofte av arkivskapers IT-/driftsmiljø eller systemleverandør på vegne av arkivskaper. Depotet foretar en selvstendig og pragmatisk validering av mottatt uttrekk og sender en forståelig rapport tilbake til arkivskaper for lesing og aksept.

Avvik dokumenteres. Nytt uttrekk er aktuelt først ved alvorlige struktur- eller innholdsmangler som gjør uttrekket utilstrekkelig som bevaringsversjon.

## Tre valideringsområder
### A – Noark 5-spesifikasjon mot Noark 5-uttrekk
Kontroll mot aktuell Noark-versjon: XML/XSD, struktur, obligatoriske elementer, relasjoner, standardverdier og andre normative krav.

### B – Noark 5-uttrekk mot innholdselementene i uttrekket
Intern konsistens og omfang: arkiv, arkivdeler, klassifikasjon, mapper, registreringer, dokumenter, journaler, endringslogg, parter, skjerming, kassasjon, sletting, konvertering, datoer og kryssfil-kontroller.

### C – Noark 5-uttrekk mot arkivskapers kontrollgrunnlag
Sammenligning mot opplysninger og forventninger fra arkivskaper, særlig avsluttede arkivdeler og forventet innhold i produksjonsbasen.

Depotet dokumenterer forskjeller. Arkivskaper vurderer og aksepterer innholdet eller sørger for korrigering dersom manglene er alvorlige.

## Standardverdier og generiske verdier
Standardverditesting og generisk opptelling skal kunne eksistere parallelt. Testdata fra ett uttrekk er evidens, ikke normativt grunnlag.

Observasjon, standardreferanse og faglig vurdering holdes adskilt.

## Individuelle analyser som grunnmodell
Hver faglig verdi skal så langt som mulig beregnes én gang av en individuell analyse eller kontroll. Resultatet lagres strukturert og gjenbrukes i views, validering, rapporter, vedlegg og senere API/database.

## U1 og U2
U1 og U2 beholdes som historisk krav-, sammenlignings- og regresjonsgrunnlag. De skal ikke være permanent grunnmodell eller parallelle beregningsprogrammer.

Målet er:

```text
individuelle analyser
        |
        v
kanoniske resultater
        |
        +--> samlet visning for hele uttrekket
        +--> samme relevante resultater per arkivdel
        +--> validerings-/kontrollvisninger
        +--> rapport og vedlegg
```

U01/U02 kan kjøres under utvikling/regresjon inntil alle nødvendige datapunkter kan rekonstrueres fra individuelle resultater.

## Views og rapportering
Views skal ikke utføre nye faglige beregninger. De setter sammen allerede beregnede resultater. Samme view kan brukes i depotets validering, hos arkivskaper, i hovedrapport og i vedlegg.

## Avvik og konsekvens
```text
testresultat / observasjon
        |
        v
avvik eller merknad
        |
        v
faglig vurdering
        |
        v
alvorlighetsgrad og konsekvens
```

Normal håndtering er dokumentasjon av avvik. Nytt uttrekk er unntaket ved alvorlige mangler.


## Avstemming mellom hele uttrekket og arkivdeler
Der et datapunkt etter Noark-strukturen naturlig tilhører én arkivdel, bør samme individuelle analyse kunne materialiseres både for hele uttrekket og per arkivdel.

Resultatene skal kunne avstemmes uten å beregnes i et separat U2-program:

```text
individuell analyse
    +--> total for hele uttrekket
    +--> resultat per arkivdel
              |
              v
      avstemming/reconciliation
```

En avstemming skal minst kunne dokumentere `total`, `archive_parts_sum`, `difference` og `status`. For generiske fordelinger summeres arkivdelenes observerte verdier nøkkel for nøkkel.

Bare metrikk som faglig er summerbare skal merkes som avstembare. Likhet skal ikke kreves automatisk for elementer som kan ligge utenfor arkivdel eller har annen strukturell semantikk. Et `mismatch` er en observasjon som skal undersøkes, ikke automatisk en teknisk kjørefeil eller et krav om nytt uttrekk.

Avstemming hører primært til valideringsområde B – intern konsistens i uttrekket – og skal senere kunne brukes som evidens i depotets validering og rapportering.

## a22 – datointervall og aggregert filstatistikk

a22 utvider samme total/per-arkivdel-modell til datointervaller og filstatistikk.

For datointervaller rekonstrueres totalen fra arkivdelene som tidligste `first` og seneste `last`. Dette brukes bare der datagrunnlaget naturlig ligger under arkivdel.

For numerisk statistikk rekonstrueres:

- `count` som sum av arkivdelenes antall,
- `sum` som sum av arkivdelenes summer,
- `min` som minste arkivdel-minimum,
- `max` som største arkivdel-maksimum,
- `average` som `total sum / total count`.

Gjennomsnitt av arkivdelenes gjennomsnitt skal ikke brukes, fordi arkivdelene kan inneholde ulikt antall verdier.

Også her er reconciliation evidens. `mismatch` betyr at forholdet må undersøkes, ikke automatisk teknisk feil.

## a22 – identitetsdata som kanoniske resultater

Identitets- og beskrivelsesdata som tidligere hovedsakelig ble skrevet direkte i U1/U2 skal også være strukturerte resultater, ikke rapporttekst. a22 innfører derfor en generell `rows`-metrikk der utvalg og feltuttrykk ligger i JSON-definisjonen. Dette gjør arkiv-, arkivskaper- og arkivdelidentitet tilgjengelig for senere views uten å bygge U1/U2 som egne beregningsprogrammer.

Per-arkivdel-kontroller fortsetter å bruke samme individuelle test som totalen der dette er faglig naturlig. De historiske U2- og R-testene beholdes inntil regresjonsdekningen er dokumentert.


## a22 – a22 avsluttes med maskinlesbar dekningskontrakt

a22 legger ikke til et nytt parallelt analyseprogram. Den formaliserer at rå datadekningen fra U1/U2 nå ligger i individuelle analyser. Dekningen dokumenteres maskinlesbart i `config/noark5/analysis/u1_u2_coverage_2026_05_26.json`.

U01/U02 merkes som `development_regression_reference`, men kjøresemantikken endres først i a24. Gjenstående standardverdier per Noark-versjon er eksplisitt utsatt til a23 og regnes ikke som manglende rå datadekning i a22.


## Terminologi og profilspesifikk konfigurasjon

U1/U2 er lokale historiske betegnelser fra IKAMRs KDRS Query-definisjoner, ikke en generell Noark- eller KDRS-standard. Nye komponenter skal navngis etter faglig funksjon. Se `NOARK5-TERMINOLOGY-NOTE.md`.

Noark 5-spesifikke standardverdier, metadata-ID-er og versjonsregler skal ligge i `config/noark5/` og ikke hardkodes i den generelle motoren. Motoren kan tilby generelle operasjoner som telling, gruppering, datointervall, rows, numerisk statistikk, reconciliation og sammenligning mot eksterne standardverdisett.

## a23 – standardverdier og observerte verdier

Fra a23 ligger maskinlesbare standardverdier under `config/noark5/standards/`. Observerte verdier beholdes uendret i de ordinære resultatfeltene. Standardverdikontrollen er et separat resultatlag som viser de observerte verdiene mot standardsett for v3.1, v4.0 og v5.0. En ekstra observert verdi gir status for videre vurdering, ikke automatisk teknisk feil.

## Standardverdisammenligning – tomme verdier

Ved sammenligning mot standardverdier skal motoren skille eksplisitt mellom at et felt ikke har observerte verdier og at alle observerte verdier finnes i standardsettet. Dette hindrer at fravær feilaktig presenteres som positivt samsvar.

Dette endrer ikke prinsippet om at standardverdikontroll og generisk observerte verdier skal eksistere parallelt.

## Profilmanifest og gjenfinning

All Noark 5-spesifikk kunnskap skal være gjenfinnbar fra `config/noark5/profile.json`. Den generelle profilregelen er dokumentert i `docs/PROFILE-ARCHITECTURE.md`, og Noark 5-oppbygningen i `docs/NOARK5-PROFILE-ARCHITECTURE.md`.


## Normative knowledge is not identical to extract tests

The profile knowledge base may contain official Noark requirements that are not directly testable from a static archive extract. Such requirements keep their provenance and validation relevance, but shall not be converted into XPath tests unless the needed evidence is present in the extract.

## a24 – ordinær kjøring og legacy-regresjon

Fra a24 skiller testkatalogen eksplisitt mellom kjøreprofiler:

- `normal` – ordinær validering; historiske `development_regression_reference`-tester kjøres ikke.
- `regression` – utviklings-/regresjonskjøring; legacy-referanser kan kjøres for sammenligning.

Filtreringen skjer på generisk `lifecycle.role`, ikke på U01/U02-test-ID-er. U01/U02 beholdes dermed som sporbar historikk uten å være del av ordinær produksjonskjøring.

Kanoniske individuelle analyser er grunnlaget for nye views og rapporter. Legacy-referansene skal aldri bli en parallell produksjonsberegning.

## a24 – maskinell legacy-regresjon

Ved `execution_profile = regression` kjøres de historiske regresjonsreferansene sammen med de kanoniske individuelle analysene. Etter kjøringen opprettes `legacy-regression-comparison.json`.

Mapping mellom historisk resultatstruktur og kanoniske resultater ligger i `config/noark5/analysis/legacy_regression_contract.json`. Sammenligningskoden er generell og kjenner ikke de faglige feltene på forhånd.

Resultatet skiller mellom:

- `match`
- `mismatch`
- `not_comparable`

Et mismatch er regresjonsevidens som må undersøkes. Det endrer ikke automatisk de kanoniske produksjonsresultatene.

## a24 – eksplisitt regresjonsoperasjon

Noark 5-profilen eksponerer nå to separate operasjoner:

- `Noark 5 XPath-tester 2026` – ordinær `normal`-profil for depotvalidering.
- `Noark 5 XPath-regresjon 2026` – eksplisitt utviklings-/QA-operasjon med `regression`-profil.

Regresjonsoperasjonen ligger i kategorien `Systemspesifikt`, kjører alle katalogdefinisjonene inkludert historiske U01/U02, og skriver resultatene separat under `noark5_tests/xpath_regression/`.

Når regresjonsprofilen fullføres opprettes `legacy-regression-comparison.json`. Denne operasjonen skal ikke brukes som ordinær depotvalidering.

## a24 – closeout av U01/U02-migreringen

Reell a24-regresjonskjøring verifiserte 113 av 113 maskinelle sammenligninger mellom historiske U01/U02-resultater og kanoniske individuelle analyser, uten mismatch eller `not_comparable`.

U01/U02 beholdes derfor som historiske regresjonsreferanser, men er ikke del av ordinær Noark 5-kjøring. Normalprofilen har 57 katalogtester; regresjonsprofilen har 59.

Regresjonsoperasjonen er en QA-/utviklingsoperasjon og ignorerer eventuelt kontrollpunkt etter operasjonen. Dette endrer ikke kontrollpunktmekanismen for andre operasjoner.

## a25 – views/compositions

Views er et eget lag over kanoniske testresultater. De skal ikke lese Noark XML direkte, kjøre XPath på nytt eller etablere alternative tellere.

Første view-katalog ligger i `config/noark5/views/canonical_views.json` og bygger:

- samlet oversikt for hele uttrekket;
- oversikt per arkivdel;
- validering/evidens med teststatus, reconciliation og standardverdikontroller.

`Noark 5 views/compositions` bruker siste ordinære (`normal`) XPath-resultatsett og skriver egne JSON-visninger under `noark5_views/`. View-definisjonene inneholder kilde-test og kilde-felt for hvert presentert felt, slik at provenance tilbake til kanonisk analyse beholdes.

Historiske U1/U2-navn brukes ikke som navn på nye views. U1/U2 finnes videre bare som legacy/regresjonsreferanse.

## a25 – gjenbrukbare views/compositions

Views er nå definert som komposisjoner av gjenbrukbare sections. Sections inneholder felt som peker til kanoniske testresultater med `source_test` og `source_path`.

Komposisjonsmotoren:
- kjører ikke XML/XPath;
- utfører ikke nye faglige tellere;
- kjenner ikke Noark-feltene hardkodet;
- henter hele-uttrekk-verdier eller tilsvarende `_archive_parts`-verdier fra eksisterende kanoniske resultater;
- rapporterer `source_missing`, `value_missing` eller `archive_part_missing` eksplisitt.

Dette gjør samme sections gjenbrukbare i depotoversikt, arkivdeloversikt, valideringsvisning og senere rapporter uten å etablere parallelle beregningsmodeller.

## a25 – presentasjon og målgrupper

Komposisjonslaget skiller nå mellom selve data-/evidenskomposisjonen og hvordan samme view skal presenteres for ulike målgrupper.

Tre målgrupper er definert:
- `depot` – detaljert kontroll- og vurderingsgrunnlag;
- `archive_creator` – lesbar oversikt som kan brukes i dialog og aksept;
- `final_report` – kandidatgrunnlag til senere sluttrapport.

Presentation metadata består av:
- presentasjonsrekkefølge;
- presentasjonsgrupper;
- labels;
- hvilke målgrupper et felt eller view er synlig for.

Dette endrer ikke kildedata, tellere eller valideringsresultater. Presentasjonslaget filtrerer og organiserer bare allerede komponerte kanoniske resultater.

`config/noark5/views/presentation_profiles.json` beskriver hvilke views som senere kan brukes for depotkontroll, arkivskaperoversikt og sluttrapportkandidat. Selve rapportgeneratoren utvikles senere.

## a25 – materialiserte presentasjonsprofiler

Views/compositions kan nå materialiseres til konkrete målgruppeutdata uten ny analyse:

- `depot`
- `archive_creator`
- `final_report_candidate`

Materialiseringen skjer etter at de kanoniske views er bygget. Den:
- filtrerer views etter `include_views`;
- filtrerer felt etter `visible_for`;
- bevarer source-test/source-path og øvrig sporbarhet;
- utfører ingen XPath, telling eller faglig beregning;
- endrer ikke original-viewene.

Resultatene skrives under `noark5_views/<timestamp>/presentations/`.

`final_report_candidate` er fortsatt bare et presentasjonsgrunnlag. Selve rapportgeneratoren utvikles senere.
