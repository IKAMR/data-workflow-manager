# SIARD Workflow Manager – PREMIS- og loggreferanse

## Formål

Dette dokumentet bevarer konkrete observasjoner om hvordan **SIARD Workflow Manager**
per 2026-09-09 bruker PREMIS og kjørelogg.

Dokumentet er en teknisk referanse for videre utvikling av Noark 5 Workflow Manager /
Data Workflow Manager. SIARD-implementasjonen er **ikke bindende arkitektur** og skal
ikke kopieres ukritisk.

Den overordnede kontrakten for logging, testresultater, vurdering og PREMIS i dette
repositoryet beskrives fortsatt i `LOGGING-PROVENANCE.md`.

## Kilder som er kontrollert

SIARD Workflow Manager repository:

- `smult/SIARD-Workflow-Manager`
- `siard_workflow/core/workflow.py`
- `siard_workflow/core/premis_logger.py`
- `siard_workflow/operations/dias_package_operation.py`
- relevante PREMIS-tester funnet i repositoryet

I tillegg er tre faktiske filer fra en SIARD Workflow Manager-kjøring kontrollert:

- `testdb04_psql_scfc1688_int-1il_20260827_112613.log`
- `testdb04_psql_scfc1688_int-1il_premis.xml`
- `siard-wf-man_2026-08-27_02_manual-report.txt`

## 1. Dagens SIARD-arkitektur

PREMIS er i dagens SIARD Workflow Manager koblet direkte inn i workflow-kjøringen.

Forenklet:

```text
Workflow.execute()
    |
    +--> oppretter PremisProvenanceLogger
    |
    +--> kjører operasjon
    |
    +--> hvis operasjonen endrer innhold og skal registreres:
    |       PremisProvenanceLogger.record(...)
    |
    +--> ved avslutning:
            PremisProvenanceLogger.finalize(...)
            -> <base>_premis.xml
```

`Workflow.execute()` oppretter altså en konkret PREMIS-logger. PREMIS er ikke bare en
output-adapter over en generell hendelseslogg.

Loggeren legges også i workflow-kontekstens metadata som `premis_logger`.

## 2. Hvilke operasjoner blir PREMIS-hendelser

Workflow-koden registrerer ikke alle utførte operasjoner i PREMIS.

En operasjon må blant annet være markert som innholdsendrende (`modifies_content`) og
passere operasjonens PREMIS-vurdering (`premis_should_record(...)`).

Dette betyr at den ordinære workflow-/kjøreloggen er rikere enn PREMIS-filen.

PREMIS-filen fra den kontrollerte kjøringen inneholder fem hendelser:

1. `Migration` – hex-ekstraksjon
2. `Adjustment` – XML-rensing
3. `Deletion` – skjemautvalg
4. `Adjustment` – lobFolder-korreksjon
5. `Adjustment` – metadata-beriking

Den ordinære kjøreloggen fra samme kjøring viser derimot 15 workflow-steg, blant annet:

- SHA-256
- utpakking
- XML-validering
- standardisering av filendelser
- HEX-ekstraksjon
- XML-rensing
- schema-valg
- lobFolder-korreksjon
- LOB-segmentering
- rapportgenerering
- metadata-beriking
- repakking
- metadata-uttrekk
- workflow-rapport

PREMIS er derfor allerede i SIARD Workflow Manager en **selektiv fremstilling** av en
større kjøringshistorikk, selv om implementasjonen ikke har et generisk eventlager som
eget arkitekturlag.

## 3. Intern datastruktur i PremisProvenanceLogger

`PremisProvenanceLogger` samler hendelser i minnet før XML skrives.

Hver registrerte hendelse lagres i praksis som en enkel struktur med blant annet:

- `type`
- `label`
- `op_id`
- `datetime`
- `detail`
- `success`

Dette er interessant fordi strukturen allerede ligner et lite, generisk eventgrunnlag,
men den er implementert inne i en PREMIS-spesifikk klasse og utformet med PREMIS som
mål.

## 4. PREMIS-mappingen i SIARD

SIARD-loggeren bruker Arkivverkets DIAS_PREMIS v2.0-navnerom.

Gyldige PREMIS `eventType` er eksplisitt begrenset til:

- `Creation`
- `Ingestion`
- `Migration`
- `Adjustment`
- `Deletion`
- `Disposal`

Ukjente/frie typer faller tilbake til `Adjustment`.

Mer beskrivende informasjon plasseres i `eventDetail`.

For hver PREMIS-hendelse skrives blant annet:

```text
eventIdentifier
eventType
eventDateTime
eventDetail
eventOutcomeInformation
linkingAgentIdentifier
linkingObjectIdentifier
```

## 5. PREMIS-object og agent

Den kontrollerte PREMIS-filen inneholder ett `premis:object` for den ferdigbehandlede
SIARD-filen.

Objektet beskrives blant annet med:

- objektidentifikator
- format = `SIARD`
- composition level
- SHA-256/fixity når tilgjengelig

PREMIS-filen har én agent:

```text
agentType = software
agentName = SIARD Manager
agentIdentifierValue = SIARD Manager v<versjon>
```

Den kontrollerte kjøringen har **ikke en egen person-/brukeragent i PREMIS-filen**.
Det gjør den forskjellig fra retningen vi nå arbeider med i Noark 5 Workflow Manager,
der registrert bruker skal kunne inngå i hendelsesgrunnlaget og eventuelt mappes til
PREMIS-agent.

## 6. Observasjon om SHA-256 i den faktiske PREMIS-filen

I den kontrollerte PREMIS-filen er `messageDigest` ikke bare selve SHA-256-verdien.
Elementet inneholder tekstrepresentasjonen av et Python-lignende dictionary:

```text
{'sha256': '<hash>', 'file': '<filsti>'}
```

Dette dokumenteres her som en observasjon av faktisk output. Det skal ikke behandles som
ønsket modell for Noark 5 Workflow Manager.

## 7. Forholdet mellom ordinær logg og PREMIS

Den ordinære SIARD-loggen er detaljert og operativ.

Den inneholder blant annet:

- alle workflow-steg
- status og klokkeslett
- tekniske detaljer
- antall filer/tabeller/rader
- bytes spart
- worker-/pipelineinformasjon
- skipped-operasjoner
- rapportproduksjon
- PREMIS-informasjonslinjer
- total sluttstatus og kjøretid

PREMIS inneholder bare et utvalg hendelser som er vurdert som relevante
innholdsendringer.

Dette skillet er viktig for Data Workflow Manager:

```text
rik intern hendelses-/kjøringshistorikk
               |
               +--> PREMIS-utvalg
               +--> CSV-utvalg
               +--> JSON-utvalg
               +--> tekstlig logg
               +--> andre fremstillinger
```

## 8. DIAS-pakking og PREMIS-filen

`DiasPackageOperation` kjenner den separate workflow-PREMIS-filen som en mulig fil med
tokenet:

```text
provenance_premis
```

Denne løses til siste `<base>_premis.xml` og kan inkluderes som metadata i DIAS-pakken.

SIARD Workflow Manager genererer samtidig også METS/PREMIS-relatert metadata som del av
selve DIAS-pakkingen. Workflow-proveniensfilen og pakkens egne metadata må derfor ikke
automatisk forstås som samme logg eller samme rolle.

## 9. Kjøringer over tid

Den kontrollerte manuelle rapporten fra en senere kjøring viser at mange tidligere
fullførte steg kan hoppes over, mens enkelte steg kjøres på nytt og DIAS-pakking utføres.

Eksempel:

```text
SHA-256                 -> allerede fullført / hoppet over
utpakking               -> allerede fullført / hoppet over
XML-validering          -> allerede fullført / hoppet over
...
metadata-beriking       -> kjørt
...
DIAS-pakking            -> kjørt
```

Dette illustrerer hvorfor framtidig generisk hendelseshistorikk bør kunne representere:

- flere runs
- gjenkjøring
- skipped
- tidligere fullført
- forhold mellom run, jobb og operasjon
- hvem som utførte den enkelte kjøringen
- sammenheng mellom hendelser over tid

En enkelt PREMIS-fil fra én konkret workflow-kjøring er ikke nødvendigvis tilstrekkelig
som full historikk for en slik kjede.

## 10. Hva vi tar med oss til Noark 5 Workflow Manager

Følgende observasjoner fra SIARD-løsningen er nyttige:

1. Det er fornuftig at ikke alle tekniske logghendelser automatisk blir PREMIS.
2. Operasjoner kan ha semantikk som avgjør om de er kandidater til et arkivfaglig
   loggformat.
3. PREMIS trenger en eksplisitt mapping fra intern hendelsesinformasjon.
4. PREMIS kan være en separat metadatafil som senere inngår i en større DIAS-pakke.
5. Ordinær kjørelogg trenger et rikere datagrunnlag enn PREMIS-filen.

Følgende deler skal **ikke** tas som bindende arkitektur:

1. At workflowen oppretter en konkret PREMIS-logger direkte.
2. At den interne hendelseslisten eies av PREMIS-klassen.
3. At PREMIS-felt ligger som egenskaper/metoder direkte på operasjonen som eneste
   mappingmekanisme.
4. At kun én konkret PREMIS-implementasjon finnes.
5. At programvaren er eneste agent.
6. At én workflow-PREMIS-fil alene representerer hele historikkjeden.

## 11. Retning for generisk loggmodell i Data Workflow Manager

Arbeidsretningen etter denne gjennomgangen er:

```text
Workflow / Job / Run
        |
        v
GENERISK HENDELSESDATAGRUNNLAG
        |
        +--> PREMIS implementasjon / definisjon A
        +--> PREMIS implementasjon / definisjon B
        +--> CSV implementasjon / definisjon
        +--> JSON implementasjon / definisjon
        +--> tekstlig loggimplementasjon
```

Det generiske datagrunnlaget skal være rikere enn hvert enkelt outputformat.

En outputimplementasjon skal kunne styres av definisjonsfil som blant annet beskriver:

- hvilke hendelser som inkluderes
- hvilke generiske felt som brukes
- mapping til formatets felter
- struktur
- obligatoriske felt
- konstanter
- formattering
- filterregler

Dersom nødvendig kan en definisjon senere kobles til en plugin for logikk som ikke kan
uttrykkes deklarativt.

Dette gjør det mulig å bytte PREMIS-implementasjon eller legge til CSV/JSON uten å endre
workflowmotoren eller den grunnleggende historikken.

## 12. Status

Dette dokumentet beskriver **referanseobservasjoner og arkitekturretning**.

Det er ikke:

- en PREMIS-spesifikasjon
- en fullstendig revisjon av SIARD Workflow Manager
- en beslutning om eksakt generisk event-schema
- en beslutning om eksakt definisjonsfilformat

Disse detaljene skal låses separat i Noark 5 Workflow Manager når den generiske
loggmodellen implementeres.
