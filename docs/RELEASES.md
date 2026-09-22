# Versjonshistorikk

Dette dokumentet samler releaseinformasjon for ferdige versjoner i samme
Git-historikk.

Fra v0.1.4-utviklingen heter prosjektet **Data Workflow Manager**.
Versjonene v0.1.0–v0.1.3 ble utgitt under navnet **Noark 5 Workflow Manager**.

Nyeste ferdige versjon står øverst. Alpha-trinn dokumenteres ikke som egne
permanente releaseversjoner.

## Navneovergang etter v0.1.3

Etter release v0.1.3 ble repositoryet renamet fra
`IKAMR/noark5-workflow-manager` til `IKAMR/data-workflow-manager` med samme
Git-historikk. v0.1.4-a1 er første utviklingstrinn med Data Workflow Manager som
applikasjonsnavn.

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
- automatisk arbeidsstatus utenfor repository per bruker
- kontroll mot output/source-kollisjoner
- kjøremiljø og framtidig plattformretning dokumentert

## v0.1.0

Første stabile dokumenterte baseline.

Viktig funksjonalitet:

- valg og deteksjon av Noark 5-kilde og workflow-GUI
- lokal kjøring gjennom `LocalExecutor`
- arkitekturgrense for framtidig `RemoteExecutor`
- DIAS metadata- og pakkedialog
- import av eksisterende METS/`info.xml`
- fil/mappe-tillegg og direkte streaming til ukomprimert TAR
- vedvarende mapper og testdokumentasjon
- sentral workflow-PREMIS
