# Source – Work – Storage

Fra v0.1.3-a11 bruker jobbmodellen tre generiske, brukerrettede mapperoller:

- **Source** – datagrunnlaget som skal behandles.
- **Work** – arbeidsområde for operasjoner, analyser, logger og mellomresultater.
- **Storage** – lagringsområde for ferdige resultater eller leveranser.

Rollene tilhører **jobben**, ikke Noark 5-profilen. En jobb kan derfor konfigureres med Source, Work og Storage også når profilen er Default. Profiler og operasjoner bestemmer hvordan rollene brukes.

Storage er en selvstendig rolle. Workflow Manager foreslår derfor ikke lenger at Storage automatisk skal ligge under Work.

## Ny jobbliste

Når en ny jobbliste opprettes, opprettes `JOB-001` automatisk med Default-profil og dialogen **Mapper** åpnes. Dette gjør at jobbens Source, Work og Storage kan defineres før en formatspesifikk profil velges.

Å åpne en eksisterende jobb eller bytte mellom eksisterende jobber åpner ikke Mapper automatisk.

## Jobblister under utvikling

Jobblisteformatet er et utviklingsformat. I denne fasen prioriteres en riktig modell fremfor bakoverkompatibilitet med jobblister lagret av eldre utviklingsversjoner.
