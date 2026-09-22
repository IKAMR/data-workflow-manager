# Data Workflow Manager – arkitekturretning

## Status

Dette dokumentet ble opprinnelig etablert i Noark 5 Workflow Manager
v0.1.2-a12 for å beskrive generaliseringsretningen.

**Repository-rename er nå gjennomført.** Hovedrepositoryet er:

`https://github.com/IKAMR/data-workflow-manager`

Git-historikken er videreført fra `IKAMR/noark5-workflow-manager`.
Data Workflow Manager er fra v0.1.4-a1 hovednavnet på applikasjonen, mens
Noark 5 videreføres som den første komplette profilen.

Historisk gjaldt følgende a12-avgrensning, og beholdes dokumentert fordi den
forklarer utviklingsløpet: **Repository-rename skal ikke gjøres i a12**.

Generaliseringsarbeidet er fortsatt gradvis. Praktisk analyse, validering,
rapportering og bevaring skal ikke blokkeres av unødvendig refaktorering.

## Repository-strategi

Den planlagte strategien er nå gjennomført i første trinn:

```text
IKAMR/noark5-workflow-manager
        |
        | rename / viderefør Git-historikken
        v
IKAMR/data-workflow-manager
        |
        +-- generisk runtime
        +-- GUI / CLI
        +-- profiler/extensions
        +-- Noark 5 som første praktiske profil
```

Vi skal ikke opprette en parallell full kodebase ved å kopiere historikken.

Et eventuelt senere tynt `IKAMR/noark5-workflow-manager` kan dokumentere eller
wrappe Noark 5-profilen, men skal ikke opprettes før vi bevisst ønsker å
oppheve GitHubs redirect fra det gamle repositorynavnet.

Se også `IDENTITY-MIGRATION.md`.

## Grunnmodell

Data Workflow Manager utfører oppgaver på en input. Input vurderes og behandles
gjennom operasjoner og ender i output med eller uten dokumentasjon.

```text
Input
  |
  v
identify / inspect
  |
  v
operations / workflow
  |
  +--> structured results
  +--> reports
  +--> provenance / logs
  |
  v
Output
```

Den innerste runtime-kjernen skal ikke kjenne begrepene Noark 5, SIARD, ADDML
eller DIAS.

## Arkitekturlag

### 1. Runtime / orchestration

Generisk runtime eier blant annet:

- Job / jobbliste
- Workflow
- kontrollpunkter og fortsettelse
- preflight
- JobRunner / BatchRunner
- executor-grense
- logging
- status/resultat-kontrakter
- input/output-kontekst
- GUI / CLI / senere API som klienter over samme tjenester

### 2. Generiske operasjoner

Aktuelle generiske operasjonstyper:

- fil- og mappekopiering
- flytting/migrering mellom lagringsområder
- checksum og verify
- fil-/mappeinspeksjon
- analyse gjennom eksternt definert evaluator/kriteriesett
- generisk kjøring av eksternt verktøy
- TAR/ZIP pakking og utpakking
- generisk rapport-rendering
- transformasjons-/migreringsorkestrering

At en operasjonstype er generisk betyr ikke at alle kriteriene er innebygd i
rammeverket.

## Definitions / extensions

Definisjonslaget bestemmer hva som skal vurderes, transformeres eller
produseres.

Eksempler:

- kriterier og regler
- schemas
- mappings
- rapportdefinisjoner/templates
- pakkedefinisjoner
- ekstern Python-kode
- eksterne programmer
- domenespesifikke operasjoner

Ekstern kode kan være hardkodet mot sitt fagområde. Kravet er at Data Workflow
Manager Core ikke hardkoder domenet.

## Profiles

En profil setter sammen relevante definitions/extensions/operasjoner til et
brukbart domeneoppsett.

Eksempler:

- Noark 5
- SIARD
- ADDML 7.3
- senere andre formater og arbeidsflyter

En profil er ikke nødvendigvis en separat applikasjon.

```text
Noark 5 profile
    |
    +-- Noark source
    +-- Noark validation
    +-- Noark reporting
    +-- Arkade adapter
    +-- generic checksum
    +-- generic transfer
    +-- DIAS packaging extension
```

DIAS er derfor ikke en del av Noark 5 Core. Det er et spesialisert pakkelag
som kan brukes sammen med flere profiler.

## Transformasjon og migrering

Migrering skal være en førsteklasses operasjonstype.

```text
Source
  |
  v
validate source
  |
  v
map
  |
  v
transform / generate
  |
  v
validate target
  |
  v
compare / reconcile
  |
  +--> report
  +--> provenance
  |
  v
Target
```

Aktuelle retninger omfatter blant annet:

- ADDML 7.3 -> SIARD
- SIARD -> SIARD, inkludert dialekt-/normaliseringsløp
- Noark 5 -> SIARD
- framtidig generering av Noark 5-uttrekk
- andre format- og representasjonsmigreringer

## Implementert arkitekturbevis fra a12

### Profile boundary

`app/profile.py` introduserer `WorkflowProfile`.

Noark 5 setter sammen dagens operasjoner i `noark5_workflow/profile.py`:

```text
NOARK5_PROFILE
      |
      v
WorkflowProfile
      |
      v
OperationRegistry
```

### Registry boundary

`noark5_workflow/core/registry.py` kjenner ikke konkrete Noark 5-operasjoner.

### Source boundary

`noark5_workflow/core/source.py` definerer den minimale generiske
`WorkflowSource`-kontrakten.

`OperationContext.input_root` er den generiske inngangen for runtime/executor.
Det eksisterende `extraction_root` beholdes for kompatibilitet.

### Domenelaget forblir domenespesifikt

Dette er tilsiktet:

```text
noark5_workflow/sources/noark5_extraction.py
noark5_workflow/operations/metadata_inventory.py
noark5_workflow/operations/analyse_arkivstruktur.py
```

Målet er:

> generisk runtime, eksplisitt domenelag

ikke domenekode som later som den er formatnøytral.

## Kodekart for grensen

```text
Desktop GUI -------------------+
                               |
CLI ---------------------------+
                               |
                               v
                     generic runtime
        Preflight / BatchRunner / JobRunner
                               |
                               v
                         Executor
                               |
                               v
                     OperationRegistry
                               ^
                               |
                        WorkflowProfile
                               ^
                               |
                   +-----------+-----------+
                   |                       |
              Noark 5 profile        future profiles
                   |                  SIARD / ADDML / ...
                   v
           Noark operations
                   |
                   v
             Noark source
```

## Hva a12 uttrykkelig ikke gjør

Denne historiske avgrensningen er fortsatt relevant for å forstå hvorfor vi
ikke masseomdøper kode i v0.1.4-a1:

- dynamisk plugin-discovery/installasjon
- eget plugin package-format
- repository-rename (ble gjennomført senere, etter v0.1.3)
- kopiering til et nytt parallelt hovedrepo
- bred omdøping av `noark5_workflow`
- omskriving av alle eksisterende Noark-operasjoner
- ny SQLite-modell
- ny server/runtime
- ny API-tjeneste
- migreringsmotor
- generisk rapportmotor

## Prioritet etter a12 og v0.1.4-a1

Den historiske a12-prioriteten var at **hovedprioriteten tilbake til praktisk
Noark 5-leveranse** skulle gjelde etter arkitekturbeviset. Det står fortsatt:
Noark 5-profilen skal være fungerende mens den generiske runtimeen forbedres.

Samtidig er repositoryet nå Data Workflow Manager, og ny generisk funksjonalitet
skal plasseres i riktig lag fra starten av.
