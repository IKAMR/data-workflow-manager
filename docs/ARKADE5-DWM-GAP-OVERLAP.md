
# DWM ↔ Arkade 5 – gap- og overlappanalyse

Fra v0.1.5-a9 materialiseres mappingen fra a2 som en egen operativ,
maskinlesbar gap-/overlappanalyse.

## Hva analysen er

Analysen beskriver **implementasjonsdekning**, ikke hva som faktisk ble kjørt i
en bestemt jobb. Kjøretidsdekning ligger fortsatt i combined coverage-modellen.

Kildene er:

- `config/noark5/external/dwm_arkade5_mapping.json`
- `config/noark5/external/arkade5_test_catalog.json`
- `config/noark5/tests/xpath_catalog_2026_05_26.json`

Arkade-katalogen er pinnet til Arkade 5 v2.13.0 og kildekodecommit
`40a32ee0ae84ddf44d1f3c35f1860567ca262733`.

## Resultat fra dokumentert mapping

Mappingen omfatter 54 Arkade 5-tester:

- 1 `equivalent`
- 21 `partial`
- 19 `complementary`
- 13 `arkade_only`

I tillegg er 14 DWM/KDRS-kontroller dokumentert som `dwm_only`.

De 13 dokumenterte DWM-gapene som Arkade dekker er:

`arkade:N5.01`, `arkade:N5.02`, `arkade:N5.28`, `arkade:N5.30`,
`arkade:N5.32`, `arkade:N5.33`, `arkade:N5.34`, `arkade:N5.47`,
`arkade:N5.48`, `arkade:N5.51`, `arkade:N5.62`, `arkade:N5.63`,
`arkade:N5.64`.

Dette betyr ikke at de automatisk skal reimplementeres i DWM. A9 gjør gapene
eksplisitte slik at en senere beslutning om egen implementasjon kan tas
kontroll for kontroll.

## Namespace

A9 gjør namespace eksplisitt i maskinmodellen:

- `arkade:N5.24` = Arkade 5-testen
- `dwm:kdrs.c22` = DWM-test-ID
- `kdrs:N5.24` = historisk KDRS-testpunkt

Lik nummertekst er aldri tilstrekkelig til å erklære tester ekvivalente.

Dette er spesielt viktig for historiske KDRS N5.52–58, N5.65, N5.101 og
N5.102. Disse skal ikke tolkes som Arkade-test-ID-er.

## Operativ modell

`build_gap_overlap_analysis()` produserer:

- sammendrag per relasjonstype
- alle 54 Arkade-kontrollområder
- DWM-test-ID-er og historiske KDRS-ID-er med eksplisitt namespace
- 13 dokumenterte DWM-gap dekket av Arkade
- 14 DWM-only-kontroller
- konsistenskontroll mot mappingens summer og testkatalogene

`partial` og `complementary` beholder alltid begge kilder. Arkade-resultater
blir fortsatt ikke DWM-masterresultater.
