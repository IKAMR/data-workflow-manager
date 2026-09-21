# Versjonshistorikk

Dette dokumentet samler releaseinformasjon for **ferdige versjoner** av Noark 5 Workflow Manager.

Nyeste ferdige versjon står øverst.

Alpha-trinn som `a1`, `a2`, `a3` og midlertidige rettelser som `a3.1` dokumenteres ikke som egne permanente releasefiler. De er utviklingstrinn fram mot en ferdig versjon.

## v0.1.3

Robust flerjobbkjøring, sporbare resultater og forbedret validering av store Noark 5-uttrekk.

Hovedendringer:

- forbedret jobb- og batchhåndtering med gjenopptak etter lagringsfeil
- selektiv gjenkjøring og versjonerte resultatsett
- unike resultatmapper og `artifact_manifest.json` med `JOB`-/`RUN`-identitet
- regel på jobblistenivå for egne Work-undermapper per jobb
- kontroll av eksisterende resultater ved oppdagelse av jobber
- Noark 5 XPath-resultater, views og depotrapporter holdes adskilt per jobb og kjøring
- forbedret fremdriftsvisning for operasjoner og tester i jobblisten
- streamingbasert XML/XSD-validering for svært store XML-filer
- validering av `arkivstruktur.xml` over 4 GB praktisk verifisert
- resultat- og ytelsesdiagnostikk med bedre sporbarhet

## v0.1.2

Noark 5-validering og rapportering basert på kanoniske analyser.

Hovedendringer:

- Noark 5 XPath-analyser med `lxml` og eksterne definisjoner
- analyse av hele uttrekket og per arkivdel
- standardverdikontroller og avstemming av resultater
- U1/U2 beholdt som regresjonsgrunnlag
- gjenbrukbare views for presentasjon av analyseresultater
- depotvalideringsrapport med avvik, vurderingspunkter og sporbarhet

## v0.1.1

Job/Batch og vedvarende jobblister.

Hovedendringer:

- `Job`, `JobStatus` og `JobBatch`
- eget Jobber/Batch-vindu
- én jobb eier kilde, workflow, operasjonsparametre, output, status og logg
- `Start alle` kjører jobbene sekvensielt med `LocalExecutor`
- stopp av batch ved neste avbruddspunkt
- separat DIAS-konfigurasjon og output per jobb
- output/resource locking
- vedvarende `.n5jobs`-jobblister
- flere separate jobblister kan lagres og åpnes
- aktiv jobb, workflow, operasjonsparametre og relevant jobbstatus kan gjenopprettes
- store Noark 5-uttrekk lagres ikke i jobblistefilen; de refereres med sti
- automatisk arbeidsstatus for ikke-manuelt lagret gjeldende jobb/jobbliste lagres utenfor repository per bruker
- siste arbeidsstatus kan gjenopprettes etter normal avslutning og ny programstart
- kontroll mot samme target/output i flere jobber
- source-duplikat gir advarsel, men er tillatt
- target som kolliderer med source eller allerede identifisert Workflow Manager-output blokkeres
- ikke-tom ukjent target gir advarsel
- permanent output-markør gjør tidligere Workflow Manager-output identifiserbar
- kjøremiljø og framtidig plattformretning dokumenteres i `RUNTIME-ENVIRONMENTS.md`

Checkpoints/stoppunkter og stegvis gjenopptakelse er planlagt for neste utviklingstrinn og er ikke del av v0.1.1.

## v0.1.0

Første stabile dokumenterte baseline.

Viktig funksjonalitet:

- valg og deteksjon av Noark 5-kilde og workflow-GUI
- lokal kjøring gjennom `LocalExecutor`
- eksplisitt arkitekturgrense for framtidig `RemoteExecutor`
- DIAS metadata- og pakkedialog
- import av eksisterende METS/`info.xml`
- legg til fil, legg til mappe og opprett mappe i pakkestrukturen
- direkte streaming av innhold til ukomprimert TAR
- vedvarende sist brukte mapper
- automatisert testresultatdokumentasjon
- sentral workflow-PREMIS tilpasset fra SIARD Workflow Manager
- workflow-PREMIS skrives bare til eksplisitt arbeids-/utdataområde

Dokumentasjonsbaseline omfatter blant annet `DEVELOPMENT.md`, `ARCHITECTURE.md`, `INTERFACE.md`, `DEFINITIONS.md`, `TESTING.md`, `CODE-MAP.md`, `SHARED-DEVELOPMENT.md` og `SHARED-ROADMAP.md`.

## Ved ny ferdig versjon

Legg den nye seksjonen **øverst**, rett under innledningen:

```text
## vX.Y.Z

Kort beskrivelse.

Hovedendringer:
- ...
- ...
```

Ikke opprett permanente `RELEASE-vX.Y.Z-aN.md` for interne alpha-/fikstrinn.
