# CSV loggformat

Fra z18.16 finnes også en flat CSV-projeksjon over den generiske event store.

```text
format = csv
implementation = csv_standard_v1
definition = config/logging/csv_standard_v1.json
```

CSV er viktig fordi formatet tvinger fram et eksplisitt skille mellom:

- rik, strukturert intern hendelsesdata
- hvilke felt en konkret flat rapport/logg faktisk skal eksponere

Kolonnene kommer fra `field_map` i definisjonsfilen. Renderer-koden kjenner derfor ikke
på forhånd hvilke generiske felt som skal bli CSV-kolonner.

Dagens standarddefinisjon bruker blant annet:

```text
timestamp
kind
run_id
job_id
operation_id
operation_name
success
message
username
user_id
```

Nested `data` tas ikke med som én stor tekstkolonne i standarddefinisjonen. Senere kan
andre CSV-definisjoner velge spesifikke nested felter, for eksempel metrics, som egne
kolonner.

## Praktisk validering etter z18.16

Etter dette steget bør en faktisk kjøring brukes til å kontrollere at samme run kan gi:

- obligatorisk `*.events.jsonl`
- tekstlig `.log`
- PREMIS når aktivert og relevant
- JSON når aktivert
- CSV når aktivert

og at alle formatteringene kan spores til samme `run_id`.
