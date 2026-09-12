# U1/U2 – dekningskartlegging mot individuelle Noark 5-analyser

## Formål
U01/U02 brukes som historisk referanse og regresjonsgrunnlag. a22 har dekomponert rå databehov fra U1/U2 til individuelle analyser som kan materialiseres for hele uttrekket og, der faglig relevant, per arkivdel.

Maskinlesbar fasit for dekningsstatus ligger i:

`config/noark5/analysis/u1_u2_coverage_2026_05_26.json`

## Status etter a22

**Rå datadekning fra U1/U2 er ferdigstilt for a22.** Ingen kjente U1/U2-rådatapunkter står igjen som `MISSING` eller `PARTIAL`.

Det betyr ikke at U01/U02 slettes i a22. De beholdes kjørbare som utviklings-/regresjonsreferanse frem til a24.

### Individuell modell som nå dekker U1/U2

- C01/C02: arkiv, arkivskaper, arkivdelidentitet og hovedtall.
- C08/C09/C12/C13: mapper, typer, nivå, status, datoer, år og tomme mapper.
- C14/C15/C16: registreringer, journalposter, typer, status, datoer og dokumentkoblinger.
- C21–C25: dokumentbeskrivelser, dokumentobjekter, dokumentnummer, versjonsnummer, status, medium, format, variantformat, filstørrelse og datoer.
- F01–F13: parter, korrespondanseparter, merknader, kryssreferanser, presedens, avskrivning, dokumentflyt, skjerming, gradering, kassasjon, konvertering og sletting.
- H/I/J/L: journalfiler, kryssfilkontroll, endringslogg og virksomhetsspesifikke metadata.

Der total og arkivdelsum faglig kan sammenlignes brukes reconciliation. Dette er evidens; mismatch er ikke automatisk teknisk feil.

## Bevisst utsatt – ikke hull i a22

### a23 – standardverdier og Noark-versjon
Normative standardverdier for Noark 5 v3.1, 4.0 og 5.0 skal modelleres maskinlesbart. Standardverdier og generiske observerte verdier skal beholdes parallelt.

### a24 – U1/U2-regresjon og ordinær kjøring
Det skal bygges en eksplisitt maskinell kontroll som rekonstruerer relevante U1/U2-sammensetninger fra individuelle resultater. Når denne er verifisert kan U01/U02 tas ut av ordinær kjøring og beholdes som utviklings-/regresjonsreferanse.

### a25 – views/sammensetninger
Lister og tabeller for validering, kontroll og rapportering skal defineres som views over kanoniske resultater. De skal ikke utføre nye faglige beregninger.

### a26 – depotets valideringsrapport
Rapportering bygges over de samme resultatene og viewene.

### Senere – område C
Sammenligning mot arkivskapers produksjonsgrunnlag og avsluttede arkivdeler modelleres separat fra U1/U2.

## U01/U02-livssyklus
I a22 er U01 og U02 eksplisitt merket `development_regression_reference` i katalogen. Dette endrer ikke kjøringen i a22; selve uttaket fra ordinær kjøring er planlagt til a24.


## a23 – standardverdier flyttes ut av historisk U1/U2-språk

Standardverdier behandles fra a23 som en egen Noark 5-spesifikasjonsreferanse og ikke som en egenskap ved U1/U2. Første maskinlesbare register ligger i `config/noark5/standards/noark5_standard_values.json`. U1/U2-navn brukes videre i denne filen bare fordi filen dokumenterer migrering og regresjonsdekning fra de historiske KDRS Query-definisjonene.
