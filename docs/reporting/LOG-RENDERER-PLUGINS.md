# Dynamisk loggimplementasjon

Fra z18.14 er `implementation` i loggdefinisjonen en faktisk runtime-kontrakt.

Pipeline importerer ikke lenger konkrete formatteringsklasser som PREMIS- eller
tekst-sink direkte. Den laster definisjonsfilen og slår opp renderer/plugin via
`noark5_workflow.renderers.registry`.

Dagens registrerte implementasjoner er:

```text
premis_xml_v1
text_run_log_v1
```

Arkitekturen er dermed:

```text
Generic event store
        |
        v
loggdefinisjon
        |
        +--> format
        +--> event_kinds
        +--> field_map
        +--> options
        +--> implementation
                    |
                    v
              renderer/plugin
```

Dette gjør det mulig å legge til for eksempel:

```text
premis_xml_v2
premis_kdrs_v1
csv_standard_v1
json_full_v1
```

uten å endre workflowmotoren eller event store.

## Registrering

Renderer/plugin-registry er foreløpig et eksplisitt Python-register. Det er bevisst
enkelt i første implementasjon. Senere kan samme kontrakt utvides med dynamisk plugin-
discovery, men definisjonsfilens `implementation` skal fortsatt være den stabile
referansen.

En ukjent implementasjon skal feile eksplisitt ved oppbygging av formatteringspipeline.
Det skal ikke finnes skjult fallback til en annen renderer, fordi det kan produsere et
annet loggformat enn det definisjonen faktisk ba om.
