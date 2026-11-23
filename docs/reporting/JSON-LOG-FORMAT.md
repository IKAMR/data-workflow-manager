# JSON loggformat

Fra z18.15 finnes første alternative formattering over den generiske event store:

```text
format = json
implementation = json_full_v1
definition = config/logging/json_full_v1.json
```

Dette er viktig som arkitekturtest: samme generiske hendelser kan nå produseres både som
intern autoritativ event store og som separat JSON-output uten endring i workflowmotoren.

## Ikke det samme som event store

Den interne event store bruker også JSONL som persistenskoding, men rollene er ulike:

```text
Generic event store
    = sannhetskilde
    = obligatorisk
    = internt schema

JSON loggformat
    = valgfri formattering/projeksjon
    = styrt av loggdefinisjon
    = kan senere ha annet schema, filter eller struktur
```

At begge foreløpig er JSONL betyr derfor ikke at de er samme lag.

## Neste steg

Neste naturlige formattering er CSV. CSV skal ikke forsøke å bevare vilkårlig nested
struktur direkte; definisjonen må uttrykke hvilke felt som flates ut til kolonner.
