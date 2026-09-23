# Arkade 5 importmodell

v0.1.5-a3 gjør Arkade 5-resultater til komplett ekstern evidens i Data Workflow Manager.

## Prinsipp

Arkade-resultatet er en selvstendig autoritativ observasjon fra Arkade 5. DWM skal ikke redusere resultatet til noen få sammenlignbare tall og kaste resten.

Flyten er:

`rå Arkade JSON -> bevart original -> tapsfri normalisering -> a2 semantisk mapping -> eventuell eksplisitt reconciliation -> visninger/rapport`

## Rå evidens

Originalfilen kopieres byte-for-byte til importområdet og identifiseres med SHA-256. Samme kildefil gir stabil importidentitet og oppretter ikke skjulte duplikater.

## Normalisert resultat

Normaliseringen bevarer for hver test:

- TestId, TestName, TestType og TestDescription
- HasResults og NumberOfErrors
- beregnet Arkade-status
- hele ResultSet-hierarkiet som sti
- alle Results
- ResultType og Message
- komplett Location-objekt
- ukjente ekstra felter fra test, resultat, location og summary i `source_extra`

Dette er viktig for fremtidige Arkade-versjoner: importen skal ikke miste data bare fordi DWM ennå ikke kjenner feltet.

## Semantisk mapping

`config/noark5/external/dwm_arkade5_mapping.json` er autoritativ for relasjonen mellom Arkade-test og DWM-test.

Gyldige relasjoner er:

- `equivalent`
- `partial`
- `complementary`
- `arkade_only`
- `dwm_only`

Historisk KDRS N5-nummer brukes aldri alene til å erklære ekvivalens.

## Reconciliation

Reconciliation er strengere enn mapping. En test kan være faglig relatert uten at to tall kan sammenlignes direkte. `noark5_workflow/external_evidence/arkade5_mapping.json` inneholder bare eksplisitt verifiserte runtime-sammenligninger. a3 nullstiller eldre, for brede scalar-mappinger som ikke samsvarer med a2-kartleggingen.

## Versjonsproveniens

Arkade-versjon kan komme fra filsti/navn, men dette er bare en observasjon. Importmanifestet beholder kildehash, originalfil og normalisert fil. Kunnskapskatalogen for Arkade 5 v2.13.0 er separat og pinnet til kildekodecommit.
