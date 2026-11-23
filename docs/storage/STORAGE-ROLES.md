# Lagringsroller per jobb

Dette dokumentet låser den første generiske mappekontrakten for Data Workflow Manager-retningen. Rollene beskriver **hva et område brukes til**, ikke hvilken fysisk mappestruktur et depot må ha. DIAS og andre pakkestrukturer beskrives i profil/setup/definition, ikke i de generiske rollenavnene.

## Source

- `source_root` – overordnet hovedområde for kildematerialet.
- `source_tar` – eventuell TAR-representasjon av leveransen.
- `source_unzipped` – eventuell utpakket representasjon av TAR-leveransen.
- `source_extraction` – mappe som inneholder det konkrete uttrekket det arbeides med.

`source_extraction` er valgfri. Eksisterende jobber bruker `source_root` som aktiv uttrekksmappe når `source_extraction` ikke er satt. Dette bevarer kompatibilitet mens source-modellen generaliseres.

DIAS er et pakkenivå og skal ikke bygges inn i disse feltnavnene. Innholdet kan blant annet være Noark 5, SIARD, ADDML-baserte uttrekk, JSON eller andre uttrekksformater.

## Arbeid

- `work_root` – hovedområde for arbeidet med jobben.
- `work_content` – valgfritt område for arbeidskopi/varianter av uttrekket.
- `work_operations` – område for validering, analyse, rapporter og andre operasjonsresultater.

Ingen av disse rollene krever bestemte fysiske mappenavn. Et depot kan eksempelvis mappe `work_operations` til `administrative_metadata/repository_operations`, mens et annet kan bruke en helt annen struktur.

XML/XSD-valideringen skriver fra a13 til `work_operations/xml-validation/`. Den skriver aldri rapporten til source som fallback.

## Arkiv

- `archive_root` – hovedområde for arkivpakke/AIP/AIC-finalisering.

Når DIAS brukes, er DIAS-strukturen under dette nivået standardstyrt. Det gjør ikke DIAS til en del av den generiske lagringskontrakten. Eksisterende `output_root` beholdes midlertidig som bakoverkompatibelt felt for dagens DIAS-kjøring og migreres ikke bredt i a13.

## DIP

DIP/innsynsområde låses ikke i a13. Aktuelle retninger omfatter blant annet SIARD/DBPTK for KDRS Søk & Vis, Noark 5-uttrekk og andre innsynsformater. Rollen konkretiseres når praktisk DIP-arbeid starter.

## Prinsipper

- Source behandles som read-only evidens.
- Generert analyse/validering går til eksplisitt arbeidsområde.
- Arbeidsområde og arkiv/finalisering er separate roller.
- Fysiske mappenavn og standardspesifikke strukturer tilhører setup/profil/definition.
- Roller skal kunne peke til lokal disk, ekstern disk, nettverksområde eller senere serverlagring uten å endre operasjonssemantikken.

## Praktisk presisering i a14

Source-panelet velger den konkrete **Source – uttrekksmappe**. Etter at `source_root` settes til en overordnet felles Source – hovedmappe skal aktiv jobb derfor fortsatt identifiseres mot `source_extraction`, ikke mot `source_root`. Dette er særlig viktig når mange jobber deler samme mottatte hovedområde.

Den overordnede kjøreloggen beholdes sentralt i applikasjonens konfigurerte loggområde. Som standard speiles samme logg samtidig til:

`<Arbeid – operasjoner>/workflow_logs/`

Dette styres av setup-verdien `copy_run_log_to_work_operations` (standard `true`). PREMIS er et separat provenienslag og erstatter ikke vanlig workflow-/kjørelogg.

## Jobblister: sentral eller prosjektlokal master

En jobbliste har alltid én autoritativ `.n5jobs`-fil. Workflow Manager skal ikke holde to redigerbare masterkopier synkronisert.

GUI støtter to arbeidsmåter:

- sentral jobbliste i appens konfigurerte standardmappe (`job_list_dir`)
- prosjektlokal jobbliste direkte under `<Arbeid – operasjoner>/wf`

`wf` er bevisst generisk og skal ikke hete `n5wf`; samme orkestreringsstruktur skal kunne brukes for Noark 5, SIARD og andre profiler senere. Workflow Managers egne prosjektlokale kjørelogger hører hjemme under `wf/logs`. Faglige testresultater (for eksempel Noark 5-kontroller eller Arkade 5-resultater) skal ikke tvinges inn under `wf`.

Appen husker inntil ti sist brukte jobblistemapper i tillegg til standardmappen. Åpne/Lagre som lar brukeren velge standard, prosjektlokal `wf`, et nylig brukt sted eller en annen mappe. Valg av et nylig sted endrer ikke den konfigurerte standardmappen.


## Prosjektlokal Workflow Manager-struktur

Når en arbeidsmappe representerer ett prosjekt med én autoritativ jobbliste, brukes:

```text
<Arbeid – operasjoner>/
└── wf/
    ├── <prosjekt>.n5jobs
    ├── project.json
    └── logs/
```

`project.json` er et prosjektmetadata-/preferanselag, ikke en kopi av jobben. Jobbtilstand,
workflow, operation parameters og lagringsroller ligger fortsatt autoritativt i `.n5jobs`.

Første format av `project.json` lagrer:

- `project_name`
- `profile_id`
- `job_profile_id` (valgfri referanse, reservert for senere sentrale jobbprofiler)
- `job_list_file`
- et begrenset `settings`-objekt for prosjektlokale preferanser
- opprettet/endret-tidspunkt

I a14 brukes prosjektinnstillingen `copy_run_log_to_work_operations`. Globale UI- og
applikasjonsinnstillinger forblir sentrale og kopieres ikke inn i prosjektet.


## Åpning og historikk for jobblister

Åpning og lagring har ulik brukerflyt:

- **Åpne:** kjente prosjekt-/historikkfiler vises med fullt filnavn og kan åpnes direkte.
  Historikkposten kan slettes uten at `.n5jobs`-filen på disk slettes.
- **Lagre som:** brukeren velger først standard, prosjektlokal eller nylig brukt mappe,
  og velger deretter filnavn i ordinær Lagre som-dialog.

Historikken omfatter både nylig brukte mapper og nylig brukte `.n5jobs`-filer.
Dialogen dimensjoneres etter de lengste viste stiene innenfor tilgjengelig skjermbredde.
