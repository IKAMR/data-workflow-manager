# Arkade 5 – praktisk akseptansetest før v0.1.5

v0.1.5-a13 er siste planlagte Arkade-steg før release.

A12 verifiserer repository-integrasjonen. A13 verifiserer at ekte importert Arkade-evidens i én `work_operations`-struktur er intakt og kan brukes av DWM.

## Blokkerende feil

Akseptansen blir `NOT_READY` når repository health ikke er `OK`, ingen Arkade-rapport er importert, originalfil mangler, SHA-256 avviker, normalisert resultat mangler/er ugyldig, formatversjon ikke er 2, ukjente test-ID-er finnes, test-ID-er er duplisert eller importen ikke kan lastes komplett.

## Ikke blokkerende observasjoner

Arkade-feil og advarsler i selve uttrekket er arkivevidens og gjør ikke DWM-integrasjonen ugyldig. Det samme gjelder ukjent/annen utledet Arkade-versjon, manglende reconciliation og at en konkret Arkade-kjøring inneholder færre enn alle 54 kontroller.

## Release-test

Før v0.1.5-release bør A13 kjøres mot minst én, helst to, ekte Arkade 5-rapporter. Maskinresultatet er `READY` eller `NOT_READY`.
