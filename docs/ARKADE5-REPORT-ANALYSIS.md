# Arkade 5 rapportanalyse

A14 legger til en menneskevennlig analyse av importerte Arkade 5-testrapporter.

Målet er å gjøre Arkades tekniske resultater forståelige og vurderbare uten at
brukeren må lese rå JSON.

Visningen:

- lar brukeren velge eksakt Arkade 5-kjøring når flere er importert,
- prioriterer Arkade-feil og advarsler,
- markerer øvrige punkter som bør vurderes når DWM-dekningen ikke er direkte,
- viser test-ID, testnavn, Arkade-status og feilantall,
- forklarer hvorfor punktet vises,
- viser DWM-dekning og eventuell reconciliation,
- viser normaliserte Arkade-funn med fil-/linjereferanse når dette finnes.

Analysen er beslutningsstøtte. Den avgjør ikke automatisk om et uttrekk skal
godkjennes eller avvises.

Eksport til en egen lesbar rapport er et naturlig neste steg, men er ikke del av
første a14-implementasjon.
