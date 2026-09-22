# Adaptiv parallell batch i GUI

v0.1.4-a5 kobler den parallelle core-funksjonen fra a4 til desktop-GUI-et.

## Valg på jobblistenivå

I Jobber/Batch-vinduet kan bruker velge:

- `Auto`
- `Sekvensiell`
- `Parallell`

og eventuelt en øvre grense for workers:

- `Auto`
- `1`, `2`, `3`, `4`, `6`, `8`

Valget lagres som applikasjonsinnstilling.

## Auto

Auto beregner batchstrategi fra:

- antall jobber
- logiske CPU-er
- tilgjengelig RAM
- største umiddelbare kildefil
- lokal, nettverks- eller flyttbar lagring
- ressursbeslutningen fra a3

Auto er konservativ:

- maksimalt 4 workers som generell standard
- nettverks-/flyttbar lagring begrenses til maksimalt 2
- svært store kildefiler begrenses til maksimalt 2
- ressursmodellen kan redusere dette helt til 1

## Viktig grense

Parallellisering gjelder mellom uavhengige jobber.

En enkelt jobb kjører fortsatt sine workflow-operasjoner sekvensielt. Checkpoints, cursor, gjenopptakelse og eksisterende JobRunner-kontrakt beholdes.

## GUI-sikkerhet

Worker-tråder oppdaterer ikke Tk-widgets direkte. Progress, logg og state-oppdateringer marshalles tilbake til GUI-tråden med `after()`.

## Praktisk test

Før a5 låses bør en jobbliste med minst to uavhengige testjobber kjøres med:

1. `Sekvensiell`
2. `Auto`
3. eventuelt `Parallell` med maks 2 workers

Kontroller at:

- to jobber kan stå `Kjører` samtidig i parallell modus
- hver jobb beholder egne operasjonsparametre
- resultatmapper og RUN/JOB-identitet holdes adskilt
- stop/status/fullføring oppdateres riktig
- samme jobbliste fortsatt fungerer sekvensielt
