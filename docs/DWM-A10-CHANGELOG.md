# v0.1.15-a10

- Ny eksplisitt ekstern resultatimport under `noark5_workflow/analysis/canonical_external_import_v0115_a10.py`.
- Ny GUI-handling **Analyser eksterne resultater...**, uavhengig av opprinnelig kontrollkjøring.
- Egen `noark5_evidence/canonical-external-analysis.json`: SHA-256, kildeidentitet, tolkningsstatus, uverifiserte eksterne testposter og Siegfried-formatfunn.
- Strengt støttet formatidentifikasjon; ikke-støttet Arkade XML/CSV og ukjente JSON-formater markeres `not_parsed`.
- Ingen automatisk depotgodkjenning, endring av Source eller overskriving av kanonisk resultatindeks.
- Oppdatert versjonskontrolltest fra a9 til a10.

## Korrigering etter test med 1525_004

- Støtte for faktisk normalisert Arkade 5 v2 med `source_status`, `number_of_errors`, `results`, `result_set_path` og rapportert kildestatus.
- Støtte for `pronom_statistics.json` (12 formatrader i verifisert eksempel), med original `RAF-220301`-verdi og filantall.
- Bevarer test- og feildetaljer separat fra DWM-master; ingen depotgodkjenning eller summering på tvers av kilder.
- Regresjonstester benytter syntetiske data. Ingen depotfiler inkludert i repoet.

## Korreksjon: samlet kildevalg i GUI

- «Analyser eksterne resultater» viser en kildeliste funnet i valgt Work, uten manuell navigering gjennom undermapper.
- Arkade 5 Noark og Arkade PRONOM kan krysses av samtidig og analyseres i ett atomisk skrevet `canonical-external-analysis.json`.
- Eksisterende kildevalg hentes fra forrige analyse i *samme* Work. Nye kilder må velges uttrykkelig.
- Status, formatstatistikk og kilde-SHA-256 holdes atskilt; ingen automatisk testgodkjenning.
- Kun kjente filnavn fra avgrensede eksterne Work-undermapper vises. Ingen Source-skanning.
