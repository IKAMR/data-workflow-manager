# v0.2.2-a1.3 – retting av jobblagring

Delta over **v0.2.2-a1.2**, som igjen legges over committet **v0.2.2-a1.1**.
Programversjon forblir `0.2.2-a1`. Ingen Git-operasjoner.

## Bekreftet feil i a1.2

Qt-utvidelsen antok at den etablerte `DwmWorkbenchAPI` tilbyr `api.dirty`.
Denne egenskapen finnes ikke i den faktiske API-kontrakten.
Resultatet kunne bli `AttributeError` ved oppfriskning av jobbvelgeren.
Automatisk lagring kunne heller ikke baseres på en slik egenskap.

## Rettet

- Jobbvelger og statusfelt bruker ikke lenger `api.dirty`.
- Ferdig registrerte/oppdaterte jobber lagres til eksisterende `.n5jobs`
  via den etablerte `api.save_job_list()`-metoden, uten ekstra «Start kontroll».
- Mislykket lagring markeres i statusfeltet og gir advarsel. Dataene
  forblir i den aktive arbeidsmodellen slik at brukeren kan prøve igjen.
- Første lagring av en ny, navnløs jobbliste krever fortsatt
  «Lagre jobbliste…» for å velge plassering.
- Ingen nye jobbmodeller, ingen sletting av tidligere jobber, og ingen
  automatisk kontrollkjøring.

## Test

Kjør `test.bat` og prøv tre jobber i samme `.n5jobs`:
JOB-001, JOB-002, JOB-003 opprettes i Enkel uten kjøring, gjenåpnes
fra disk, vises i Avansert og kan velges igjen i Enkel.
Sjekk at Source, Work og kontrollvalg er forskjellige per jobb.
Kjør om ønskelig «Kjør klare jobber» etter den rene lagringstesten.

15 målrettede tester består i isolert testmiljø. Ekte Windows/Qt
og full DWM-testpakke er ikke gjennomført her.
