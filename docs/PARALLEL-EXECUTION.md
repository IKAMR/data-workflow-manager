# Parallell kjøring

v0.1.4-a4 etablerer parallell kjøring av **uavhengige jobber** i det generiske core-laget.

## Grense

Parallellisering skjer mellom jobber:

```text
JOB-001 ---- workflow operasjon 1 -> 2 -> 3
JOB-002 ---- workflow operasjon 1 -> 2 -> 3
JOB-003 ---- workflow operasjon 1 -> 2 -> 3
```

Rekkefølgen inne i hver jobb er fortsatt sekvensiell og checkpoint-aware.

`BatchRunner.run()` er uendret og sekvensiell. Nytt API er:

```python
BatchRunner.run_parallel(..., max_workers=N)
```

## Isolasjon

Registry-operasjoner er mutable under jobbkonfigurasjon. Derfor får hver parallell worker en isolert kopi av registry/operasjonsinstansene.

Dette hindrer at operasjonsparametre fra én jobb lekker til en annen.

## Ressursstyring

a4 kobler ikke parallell batch automatisk inn i desktop-GUI-et ennå. Før GUI-aktivering skal `recommended_workers` fra ressursstrategien brukes sammen med:

- tilgjengelig RAM
- filstørrelser
- lagringstype
- kilde-/output-konflikter
- GUI-sikker callback-marshalling

Dette gjør at vi kan teste selve parallelle core-kontrakten før brukergrensesnittet begynner å starte flere tunge jobber samtidig.

## Trådsikker persistens

Parallell kjøring kan skrive til samme RUN-logg. Derfor serialiserer a4 append av:

- canonical event-store JSONL
- `raw-results.jsonl`

Hvert JSONL-record skrives som én beskyttet append-operasjon.

## RUN-sporbarhet

Råresultatformatet er oppgradert til schema version 2 med `run_id`.

Gamle schema version 1-poster kan fortsatt leses. Dermed blir kjeden eksplisitt:

```text
RUN -> JOB -> OPERATION -> RAW RESULT
```

uten å måtte utlede RUN fra artefaktstien.
