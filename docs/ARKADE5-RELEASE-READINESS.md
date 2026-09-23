
# Arkade 5 – release readiness for v0.1.5

v0.1.5-a14 samler de eksisterende kontrollene til én eksplisitt release-gate.

A14 introduserer ikke nye Noark 5-tester og endrer ikke betydningen av
Arkade-resultater. Den svarer bare på om Arkade-integrasjonen er teknisk klar
for v0.1.5-release.

## Tre obligatoriske gates

### 1. Full testpakke

`docs/test-results/.last-test-summary.txt` må vise:

- `FAILED=0`
- `ERRORS=0`

Antall tester og eventuelle skipped beholdes som dokumentasjon.

### 2. A12 integration health

`build_arkade5_integration_health()` må returnere:

`OK`

Dette bekrefter katalog, mapping, policy, DWM-ID-er, Arkade-versjon og
kildeproveniens.

### 3. A13 practical acceptance

`build_arkade5_practical_acceptance()` må returnere:

`READY`

Dette krever minst én intakt importert Arkade-rapport i den aktuelle
`work_operations`-strukturen.

## Resultat

Når alle tre er grønne:

`READY_FOR_V0.1.5`

Ellers:

`NOT_READY_FOR_V0.1.5`

Resultatet inneholder hver gate separat, slik at et blokkert punkt kan spores
uten å gjette.

## Viktig skille

Arkade-feil eller advarsler om selve arkivuttrekket er fortsatt arkivevidens og
er ikke i seg selv en feil i DWM-integrasjonen. Release-gaten blokkerer på
test-/integritetsfeil, ikke på at Arkade faktisk finner avvik i et uttrekk.
