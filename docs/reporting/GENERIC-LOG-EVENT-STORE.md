# Generisk loggbasis

## Formål

Workflow Manager skal ha ett generisk hendelsesdatagrunnlag som er sannhetskilden for
hva som faktisk skjedde under en kjøring.

PREMIS, tekstlig logg, CSV, JSON og andre formater skal være **projeksjoner** over dette
grunnlaget. De er ikke parallelle autoritative historikker.

## Intern event store

Fra a18 lagres runtime-hendelser append-only i en intern JSONL-fil med
`schema_version = 1`.

JSONL er valgt som intern persistenskoding fordi den er enkel å skrive append-only og
enkel å inspisere. Dette betyr **ikke** at den interne event store er det samme som et
senere offentlig/konfigurerbart `JSON`-loggformat.

Hver record inneholder blant annet:

- `schema_version`
- `event_id`
- `timestamp`
- `kind`
- `run_id`
- `job_id`
- `operation_id`
- `operation_name`
- `parent_event_id`
- `success`
- `message`
- `user`
- `data`

`data` er strukturert og kan inneholde formatnøytrale metrics, resultatreferanser,
input/output-informasjon og andre hendelsesspesifikke data.

## Én kjøring – én run_id

Overordnet run og operasjonene under samme kjøring deler samme `run_id`.

`RunOverviewLog` oppretter transient runtime-kontekst:

- `_current_run_id`
- `_current_event_store_path`

Disse verdiene deles med `JobRunner`/`OperationContext`, men er ikke portable
setup-innstillinger og skal ikke eksporteres som brukeroppsett.

Dermed kan `run.started`, `job.started`, `operation.completed`, `job.finished` og
`run.finished` inngå i samme hendelseskjede.

## Obligatorisk sannhetskilde

`GenericEventStoreSink` er obligatorisk (`required = True`).

Valgfrie formatteringssinks kan feile isolert uten å stoppe andre formatteringer.
En feil ved skriving av selve generiske event store skal derimot ikke skjules som om
kjøringen hadde komplett sporbarhet.

## Output-formater

`enabled_log_sinks` gjelder output-formatene, ikke den generiske event store.

Dagens output-adaptere er:

- `text_run_log`
- `premis`

Planlagte eksempler:

- CSV
- JSON
- alternative PREMIS-profiler/implementasjoner

Neste arkitektursteg er definisjonsfiler som beskriver hvilke generiske hendelser/felter
som et konkret outputformat skal bruke og hvordan de mappes.
