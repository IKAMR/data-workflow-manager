# Overgang til Data Workflow Manager

## Status

Repositoryet ble 2026-09-22 renamet fra:

`IKAMR/noark5-workflow-manager`

til:

`IKAMR/data-workflow-manager`

Git-historikken er videreført. v0.1.3 er siste ferdige release under navnet
**Noark 5 Workflow Manager**. Utviklingen fra v0.1.4-a1 bruker
**Data Workflow Manager** som applikasjons- og repositorynavn.

## Hva v0.1.4-a1 endrer

- applikasjonsnavn: `Data Workflow Manager`
- repositoryidentitet: `IKAMR/data-workflow-manager`
- README og sentral generaliseringsdokumentasjon
- versjonslinje til `0.1.4-a1`

## Hva v0.1.4-a1 ikke endrer

For å bevare kompatibilitet gjør a1 ingen bred intern omdøping av:

- `noark5_workflow`
- `n5wf`
- `.n5jobs`
- eksisterende Noark 5-profiler og konfigurasjonsstier
- Python-distribusjonsnavnet `noark5-workflow-manager`
- eksisterende brukerdata, jobblister og resultatstrukturer

Disse er tekniske kompatibilitetsidentifikatorer og skal ikke byttes ut før
migreringsregler og bakoverkompatibilitet er eksplisitt definert og testet.

## Noark 5 etter navneendringen

Noark 5 er ikke fjernet. Noark 5 er den første komplette profilen i Data
Workflow Manager og beholder domeneidentitet i profiler, definisjoner,
operasjoner, rapporter og kildemodell.

Målet er fortsatt:

> generisk runtime, eksplisitt domenelag

## Lokale Git-kloner

GitHub videresender den gamle repositoryadressen etter rename, men lokale
kloner bør oppdateres eksplisitt:

```text
git remote set-url origin https://github.com/IKAMR/data-workflow-manager.git
```

Kontroller deretter:

```text
git remote -v
```

## Gammelt repositorynavn

Det gamle navnet `IKAMR/noark5-workflow-manager` skal **ikke opprettes på nytt
med en gang**. GitHub bruker det gamle navnet som redirect til det renamede
repositoryet. Hvis navnet gjenbrukes til et nytt repository, slutter denne
redirecten å virke.

Et eventuelt senere tynt Noark 5-repository/wrapper under det gamle navnet skal
først opprettes når vi bevisst ønsker å erstatte redirecten, og når relevante
lenker, remotes og dokumentasjon er oppdatert.

## Videre migreringsrekkefølge

1. Behold fungerende v0.1.3-kompatibilitet.
2. Stabiliser Data Workflow Manager-branding og generisk runtime.
3. Flytt flere generiske ressurser ut av Noark 5-spesifikke lag når dette gir
   reell verdi.
4. Definer eventuell ny generell CLI-/jobblisteidentitet med migreringsstøtte.
5. Vurder deretter et tynt Noark 5-wrapperrepository hvis det fortsatt er
   nyttig.
