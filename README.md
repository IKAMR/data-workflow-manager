# Data Workflow Manager

Data Workflow Manager er et generisk arbeidsflytverktøy for analyse, validering,
behandling, dokumentasjon og migrering av strukturerte data og digitale
arkivuttrekk.

Fra **v0.1.4-a1** er dette hovednavnet på applikasjonen og repositoryet:

`https://github.com/IKAMR/data-workflow-manager`

Prosjektet viderefører hele Git-historikken fra **Noark 5 Workflow Manager**.
**v0.1.3** var siste ferdige release under det gamle applikasjonsnavnet.

## Profiler og spesialisering

Data Workflow Manager skal ha en generisk runtime, mens domene- og
formatspesifikk funksjonalitet legges i profiler, definisjoner og extensions.

**Noark 5 er den første praktiske og mest komplette profilen.** Dagens Noark
5-funksjonalitet videreføres og skal ikke svekkes av generaliseringen.

Planlagte/aktuelle profiler og arbeidsretninger omfatter blant annet:

- Noark 5
- SIARD
- ADDML 7.3
- migrering mellom strukturer og representasjoner
- generiske fil-, kontroll-, rapport- og pakkearbeidsflyter

DIAS SIP/AIC er et pakkelag som kan brukes sammen med flere profiler og er ikke
selve Noark 5-kjernen.

## Status

Programmet har blant annet:

- CustomTkinter-basert desktop-GUI
- lokal CLI (`n5wf`) for kontroll, status og kjøring av eksisterende jobblister
- Job/Batch-modell med flere isolerte jobber
- vedvarende `.n5jobs`-jobblister
- `JobPreflight`, `JobRunner`, `BatchRunner` og executor-grense som er
  uavhengig av GUI-et
- sekvensiell batchkjøring og gjenopptak etter kontrollpunkt/lagringsfeil
- selektiv gjenkjøring og versjonerte resultater
- unike JOB/RUN-resultatområder og `artifact_manifest.json`
- resultatkontroll ved oppdagelse av jobber
- Noark 5-analyse, XPath-kontroller, views og depotvalideringsrapport
- streamingbasert XML/XSD-validering for svært store XML-filer
- DIAS SIP/AIC-pakking og import av eksisterende METS/`info.xml`
- sentral workflow-logging og PREMIS-proveniens
- lokal CLI og arkitekturgrense for senere server/API/worker-kjøring

## Kompatibilitet etter navneendringen

v0.1.4-a1 endrer **repository- og applikasjonsidentitet**, men gjør ikke en bred
intern refaktorering.

Følgende tekniske identifikatorer beholdes foreløpig av
bakoverkompatibilitetshensyn:

- Python-pakken `noark5_workflow`
- CLI-navnet `n5wf`
- jobblisteformatet `.n5jobs`
- eksisterende Noark 5-konfigurasjon og profiler
- Python-distribusjonsnavnet `noark5-workflow-manager`

Dette er bevisst. De skal bare migreres når vi har en eksplisitt
kompatibilitets-/migreringsstrategi.

Se [docs/IDENTITY-MIGRATION.md](docs/IDENTITY-MIGRATION.md) og
[docs/DATA-WORKFLOW-MANAGER.md](docs/DATA-WORKFLOW-MANAGER.md).

## Kjøremiljø

**Windows desktop er dagens testede og støttede baseline.** Python-kjernen er i
stor grad plattformuavhengig, og Linux/macOS, terminalserver, headless
server/worker og web/API er framtidige mål som først skal omtales som støttet
etter praktisk verifikasjon.

Normal bruk på Windows:

1. Kjør `install.bat` ved første installasjon eller når avhengigheter endres.
2. Kjør `test.bat` og kontroller at alle tester består.
3. Start GUI med `start.bat`, eller bruk CLI med `n5wf ...`.

Eksempler:

```text
n5wf --help
n5wf jobs check <file.n5jobs>
n5wf jobs status <file.n5jobs>
n5wf jobs run <file.n5jobs>
```

Se [docs/CLI.md](docs/CLI.md) og
[docs/RUNTIME-ENVIRONMENTS.md](docs/RUNTIME-ENVIRONMENTS.md).

## Jobber og jobblister

Grunnprinsippet er:

> One job = one source + one workflow + one output area.

Store uttrekk bygges ikke inn i jobblistefilen; kilder og output refereres med
plassering. Jobber, workflow, status og resultater skal kunne brukes fra GUI,
CLI og senere server/API gjennom samme underliggende runtime.

## Operasjonsarkitektur

En operasjon arver fra `BaseOperation` og implementerer:

```python
run(ctx) -> OperationResult
```

Operasjoner angir et `ExecutionTarget`:

- `local`
- `server`
- `either`

I dagens implementasjon brukes `LocalExecutor`. `RemoteExecutor` er
arkitekturgrensen for senere klient/server-støtte.

Målet er:

> generisk runtime, eksplisitt domenelag

Noark 5-spesifikke kilder, tester og rapporter skal derfor fortsatt hete Noark
5 der de faktisk er Noark 5-spesifikke.

## Bevaringsprinsipp

Mottatt kildemateriale skal som hovedregel behandles read-only. Genererte
logger, rapporter, PREMIS, analyser og pakkedata skal lagres utenfor originalen
med sporbar identitet og proveniens.

## Testing

`test.bat` kjører automatiserte tester og skriver versjonert rapport under
`docs/test-results/`.

## Utviklingsdokumentasjon

Før større endringer, se blant annet:

- [docs/DATA-WORKFLOW-MANAGER.md](docs/DATA-WORKFLOW-MANAGER.md)
- [docs/IDENTITY-MIGRATION.md](docs/IDENTITY-MIGRATION.md)
- [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md)
- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)
- [docs/INTERFACE.md](docs/INTERFACE.md)
- [docs/CLI.md](docs/CLI.md)
- [docs/CODE-MAP.md](docs/CODE-MAP.md)
- [docs/SHARED-DEVELOPMENT.md](docs/SHARED-DEVELOPMENT.md)
- [docs/SHARED-ROADMAP.md](docs/SHARED-ROADMAP.md)
- [docs/RUNTIME-ENVIRONMENTS.md](docs/RUNTIME-ENVIRONMENTS.md)
- [docs/RELEASES.md](docs/RELEASES.md)

## Historikk

Releasehistorikken fram til og med v0.1.3 tilhører samme Git-historikk selv om
prosjektet da het **Noark 5 Workflow Manager**.

## Lisens

GNU General Public License v3. Se `LICENCE`.
