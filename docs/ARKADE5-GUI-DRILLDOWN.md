# Arkade 5 – GUI drill-down

v0.1.5-a7 bygger videre på samlet DWM/Arkade-dekning fra a6.

- combined coverage kan filtreres på dekningsstatus og Arkade-feil
- hvert Arkade-kontrollområde kan åpnes i en detaljvisning
- detaljvisningen laster bevart normalisert evidens for valgt import-ID og test-ID
- kildefil, SHA-256, testdato og Arkade-versjon vises sammen med funnene
- Arkade-resultatet forblir ekstern evidens og endrer ikke DWM-masterresultat eller depotvurdering

A7 retter også GUI-proveniens fra a6: depotrapporten lagrer `source_file` og `source_sha256` flatt på importgruppen, og a7 leser disse feltene direkte.
