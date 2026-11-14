# Pakkekandidat og videre AIP-løp

`preservation_staging/dwm-aip-candidate-v1` er et forberedende arbeidsprodukt i Work, **ikke** bevaringspakke/AIP eller beslutning om bevaring.

## Innhold

- `manifest-sha256.json`: verifiserbare filavtrykk, relatert Work-sti, størrelse, status og sperrer
- `payload/`: kopier av identifisert evidens og rapportutkast, inkludert tilhørende eksterne analysedata dersom SHA-256 er gyldig

Kopiene forandrer ikke evidens i Work eller Source. Det skjer ingen rekursiv kopiering av hele Work eller arkivuttrekket. Hvis kilde er endret/ikke verifisert, skal dette fremgå som manglende evidens. Eksisterende pakkekandidat kan ikke automatisk overskrives.

## Gjenstående før faktisk AIP

Arkivskapers aksept, faglig avviksbehandling og beslutning, journalføring, uttrekksdata, pakkestandard/struktur, metadata, all evidens og uavhengig integritetskontroll må håndteres i en senere, eksplisitt prosess.

## Avgrensning presisert i a16

Denne evidenskandidaten er en kopi-/hash-samling for intern kvalitetssikring. Den er **ikke** DIAS-pakkemotor og skal ikke omtales som den faktiske AIP. Den fungerende DIAS-produksjonen ligger i `noark5_workflow/operations/dias_package.py`, med METS/`info.xml` fra `dias_mets.py` og redigerbar Work-metadata fra `app/dias_info_v0113_a2.py`. GUI bruker nå navnet «Evidenskandidat (Work)» og kan vise eksisterende kandidats integritet uten å pakke. For detaljer om faglige valg, se `NOARK5-CONTROL-TO-PRESERVATION-ROADMAP.md`.
