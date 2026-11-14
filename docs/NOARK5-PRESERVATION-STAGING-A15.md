# Pakkekandidat og videre AIP-løp

`preservation_staging/dwm-aip-candidate-v1` er et forberedende arbeidsprodukt i Work, **ikke** bevaringspakke/AIP eller beslutning om bevaring.

## Innhold

- `manifest-sha256.json`: verifiserbare filavtrykk, relatert Work-sti, størrelse, status og sperrer
- `payload/`: kopier av identifisert evidens og rapportutkast, inkludert tilhørende eksterne analysedata dersom SHA-256 er gyldig

Kopiene forandrer ikke evidens i Work eller Source. Det skjer ingen rekursiv kopiering av hele Work eller arkivuttrekket. Hvis kilde er endret/ikke verifisert, skal dette fremgå som manglende evidens. Eksisterende pakkekandidat kan ikke automatisk overskrives.

## Gjenstående før faktisk AIP

Arkivskapers aksept, faglig avviksbehandling og beslutning, journalføring, uttrekksdata, pakkestandard/struktur, metadata, all evidens og uavhengig integritetskontroll må håndteres i en senere, eksplisitt prosess.
