# v0.1.15-a15

- Oppretter eksplisitt, ikke-godkjent pakkekandidat i `Work/preservation_staging/dwm-aip-candidate-v1`.
- Kopierer tilstedeværende kanonisk evidens, rapportutkast, Work-jobbidentitet og valgte verifiserte eksterne JSON-kilder.
- Skriver manifest med originalsti i Work, størrelse, SHA-256, DWM-versjon, manglende kilder og åpne sperrer.
- Verifiserer hver kopi mot kilde før atomisk publisering av kandidaten; eksisterende kandidat overskrives aldri.
- Source/uttrekksinnhold inngår **ikke**. Pakkekandidaten er **ikke** en fullstendig eller godkjent AIP.
