# Data Workflow Manager v0.2.0

## GUI-rammeverk for depotets produksjonslinje

v0.2.0 ferdigstiller den nye Qt-navigasjonen rundt DWM sine eksisterende
Noark 5-kontroller, jobber, Work-områder, resultater og faglige vurderinger.
Dette er grunnlaget for videre praktisk Noark 5-validering – ikke en påstand
om at alle produksjonstrinn eller analyser er ferdig implementert.

- **Startside og arbeidsprofiler:** Kontroll, Depot – produksjonslinje og Egendefinert,
  åtte synlige arbeidsområder og modenhetsfilter. Start i Enkel eller Avansert
  modus; samme underliggende jobb- og kontrollmotor benyttes.
- **Mottak/Ingest:** Qt-arbeidsflate over eksisterende mottaksmotor med
  forhåndsvisning og eksplisitt godkjenning. Full funksjonstest er utsatt.
- **Work og Kontroll:** Eksisterende jobblister, Work-lagring, operasjoner,
  kontrollpunkter og tekniske analyser videreføres uten automatisk flytting
  eller opprettelse av Source-/Work-mapper ved navigasjon.
- **Rapportering og depotvurdering:** Integrert tilgang til rapporter, kanoniske
  resultatdata, separate tekniske og eksterne evidenskilder og signerte,
  begrunnede vurderinger av hele uttrekket og den enkelte arkivdel.
- **Bevaring:** Viser Work-lagret bevaringsgrunnlag og kandidatenes status.
  En evidenskandidat er ikke en integritetsverifisert DIAS AIP; Qt-navigasjon
  starter ingen pakking eller godkjenning.
- **Produksjonsstatus og historikk:** Jobbtilknyttet visning av arbeidsområder,
  faktisk lagret Work-historikk og kontrollfremdrift. «Fortsett sist»
  gjenopptar GUI-navigasjon, ikke en kontrollkjøring.
- **Resultatvisninger:** Fire grupper med tilgang til eksisterende visninger,
  lesbart faglig vurderingsgrunnlag, rå JSON ved behov og tilpassede paneler
  for mindre skjermer.

## Viktige avgrensninger

Antiviruskontroll er foreløpig en arbeidsflate uten integrert skannermotor;
fullstendig Ingest- og antivirusgjennomgang gjenstår. Intern CRM og Innsyn
har ingen implementerte integrasjoner. DIAS AIP-pakking er ennå ikke
integrert i den nye Qt-bevaringsarbeidsflaten. Fullført teknisk kjøring og
produsert rapport innebærer ikke faglig depotgodkjenning.

## Videre arbeid og test

Neste prioritet er praktisk validering av faktiske Noark 5-uttrekk; resultatene
skal styre justeringer av innholdet i arbeidsflatene. Den avtalte videre
GUI-/integrasjonsplanen er bevart i `docs/ROADMAP-ETTER-v0.2.0.md`.

Kjør `test.bat` og deretter `start.bat` i Windows før commit.
Full Windows-test og operatørens kontroll av releasen gjenstår før publisering.
Deltaens baseline er committet `v0.2.0-a6` på GitHub main:
`17d4c72be450507181473b3b85af75a3421c93f6`.
