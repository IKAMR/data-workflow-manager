# Prosjektinnstillinger

Workflow Manager skiller mellom tre nivåer av konfigurasjon:

1. **Globale applikasjonsinnstillinger** – gjelder bruker/installasjon/servermiljø.
2. **Prosjektinnstillinger** – ligger sammen med arbeidsprosjektet i `wf/project.json`.
3. **Jobbprofil** – planlagt sentral mal for gjenbrukbare jobboppsett.

## Globalt

Globale innstillinger omfatter blant annet standardmapper, siste brukte steder,
GUI-preferanser og tekniske innstillinger som ikke skal bindes til ett prosjekt.

## Prosjektlokalt

Et prosjekt kan bruke:

```text
<Arbeid – operasjoner>/
└── wf/
    ├── <prosjekt>.n5jobs
    ├── project.json
    └── logs/
```

`.n5jobs` er eneste autoritative jobbfil. `project.json` er ikke en jobbkopi.

Første `project.json`-format inneholder prosjektidentitet, aktiv profil,
referanse til den lokale master-jobblisten, en valgfri framtidig
`job_profile_id` og et avgrenset `settings`-objekt.

Prosjektfilen opprettes/oppdateres automatisk når master-jobblisten lagres
direkte i prosjektets `wf`-mappe.

## Sentrale jobbprofiler – planlagt

Senere skal Workflow Manager kunne tilby sentralt lagrede jobbprofiler, lokalt
eller på server. Eksempler kan være:

- generell Noark 5-profil
- depotspesifikke Noark 5-varianter
- SIARD-profiler
- andre format-/workflowprofiler

En jobbprofil er en **mal**, ikke aktiv jobbtilstand. Et prosjekt kan senere
referere til malen med `job_profile_id`, mens den konkrete `.n5jobs`-filen
fortsatt er den autoritative kjørbare jobben for prosjektet.

Dette skillet gjør at en sentral profil kan videreutvikles uten at eksisterende
prosjektjobber automatisk endres.
