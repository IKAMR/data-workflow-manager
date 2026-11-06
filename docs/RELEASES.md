# Versjonshistorikk

Dette dokumentet samler releaseinformasjon for ferdige versjoner i samme
Git-historikk.

Fra v0.1.4-utviklingen heter prosjektet **Data Workflow Manager**.
Versjonene v0.1.0–v0.1.3 ble utgitt under navnet **Noark 5 Workflow Manager**.

Nyeste ferdige versjon står øverst. Alpha-trinn dokumenteres ikke som egne
permanente releaseversjoner.

## v0.1.9

Sporbar kildeevidens, faglig depotvurdering og portabel lagring for selvstendige Work-jobber.

Hovedendringer:

- Utvidede Resultatvisninger i PySide6 med Kildeoversikt og Arkade-dekning: bevarte DWM-, Arkade 5- og KDRS Query-kilder vises separat med identitet og kildegrunnlag. KDRS Query får filtrering for Standard/U1/U2, og kildeoversikt kan eksporteres som CSV, HTML og JSON. Eksisterende rapport- og årsfordelingsvisninger videreføres.
- Ny Depotvurdering per uttrekk og per arkivdel (original system-ID), med teknisk status, periodegrunnlag og faglig beslutning som separate felt. Manuelle beslutninger krever begrunnelse og brukeridentitet, har historikk og er bundet til rapportens SHA-256. En fullført arbeidsflyt betyr ikke faglig godkjenning.
- Forbedret jobbliste med status for tilgjengelig/frakoblet Work, identitetskontroll, gjenoppretting fra Work og eksplisitt omkobling av flyttet Work eller Source. Varig jobb-UUID og historikk beholdes.
- Portabel lagringsmodell med kontrollert rotomkobling for flere jobber, for eksempel fra G:\ til H:\, med relativ delsti per lagringsrolle. Source, Work og AIP kan fortsatt ligge under forskjellige røtter. Work lagrer et eget `storage-roots.json` med rotmapping, jobbreferanse og relative delstier.
- Forhåndskontroll, identitetskontroll av Work og eksplisitt brukerbekreftelse før omkobling. Ingen arkivfiler kopieres, flyttes eller analyseres på nytt. Eksisterende `.n5jobs`-filer og det opprinnelige CustomTkinter-GUI-et videreføres.

Avgrensninger: Historiske absolutte stier i gamle rapporter og logger omskrives ikke. `storage-roots.json` er et tillegg til de autoritative `job.json`, `job-state.json` og `job-events.jsonl`; eksisterende runtime bruker fortsatt oppdaterte absolutte stier. En omkobling over flere jobber er ikke én atomisk transaksjon. SIARD-analyser, tverrjobbanalyse og parallelle workers inngår ikke i denne releasen.

## v0.1.8

Nytt fleksibelt brukergrensesnitt og selvstendige jobber i Work.

Hovedendringer:

- Nytt PySide6-basert GUI med flyttbare paneler, lagrede arbeidsflater og separate visninger av Kjøreløp, Kjørelogg og Systemlogg. Det opprinnelige CustomTkinter-GUI-et beholdes som alternativ.
- Felles applikasjons-API som skiller brukergrensesnitt fra arbeidsflytmotoren og viderefører eksisterende analyser.
- Jobbdefinisjon, status og hendelser lagres autoritativt i Work, med varig UUID, jobbliste som indeks og mulighet for gjenoppretting uten opprinnelig jobbliste.
- Selektiv kjøring av deljobber, varig Kjøreløp, logger og identifiserbare kjøringer.
- Førkjøringskontroll av uttrekk, lagringsroller, arbeidsflyt og Arkade 5 CLI, med samtykke før opprettelse av manglende Work-mapper.
- Resultatvisninger og rapportering fra lagrede DWM-, Arkade 5- og KDRS Query-resultater, inkludert årsfordelinger, arkivdeler, periodevurdering og samlerapporter.
- Forbedret valg av rapportmappe og husking av sist brukte kilde-, Work- og rapportmapper i det nye GUI-et.

En teknisk fullført arbeidsflyt innebærer ikke at et uttrekk er faglig godkjent. Resultatgrunnlag og manuelle vurderinger holdes adskilt.

SIARD-analyser, analyser på tvers av ulike uttrekkstyper og en separat parallell arbeidsmotor inngår ikke i denne releasen.

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
