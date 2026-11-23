# Definisjonsdrevet loggformat

## Prinsipp

Den generiske event store er sannhetskilden. Et konkret loggformat skal ikke definere
hva som faktisk skjedde; det skal definere **hvordan et utvalg av generiske hendelser
representeres**.

Fra z18.13 finnes eksterne loggformatdefinisjoner under:

```text
config/logging/
```

Dagens første definisjoner er:

```text
text_run_default_v1.json
premis_default_v1.json
```

## Definisjonskontrakt

En definisjon beskriver minst:

- `definition_id`
- `definition_version`
- `format`
- `implementation`
- `event_kinds`
- `field_map`
- `options`

Eksempel på arkitektur:

```text
Generic event store
       |
       +--> premis_default_v1
       |        |
       |        +--> implementation: premis_xml_v1
       |
       +--> text_run_default_v1
                |
                +--> implementation: text_run_log_v1
```

`format` og `implementation` er bevisst separate begreper.

Dermed kan vi senere ha for eksempel:

```text
format = premis
implementation = premis_xml_v1

format = premis
implementation = alternative_premis_xml_v2
```

uten at workflowmotoren må endres.

## Hva som er implementert nå

z18.13 introduserer definisjonsmodell, loader og eksterne JSON-definisjoner.

Pipeline laster valgt definisjon og sender den til formatteringssinken. Sinkene bruker
definisjonens `event_kinds` som filter.

Noen formatdetaljer i dagens PREMIS- og tekstimplementasjon er fortsatt Python-kode.
Det er tilsiktet i dette steget. Neste steg er å flytte mer av selve feltmappingen og
formatteringsreglene ut av Python og over i definisjonslaget der dette kan uttrykkes
deklarativt.

## Plugin-grense

En definisjonsfil trenger ikke kunne uttrykke all fremtidig logikk.

`implementation` er grensen mot en konkret renderer/plugin. Definisjonen beskriver
kontrakten og mappingen; renderer/plugin utfører formatspesifikk serialisering eller
logikk som ikke er praktisk å uttrykke deklarativt.

Dette følger samme hovedregel som resten av Data Workflow Manager:

**spesialisering skal ligge i plugins og/eller definisjonsfiler, ikke i den generiske
workflowmotoren.**
