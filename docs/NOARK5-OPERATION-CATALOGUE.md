# Noark 5 – operasjonskatalog

Fra v0.1.3-a11 skiller katalogen mellom ordinær master-workflow, referansekjøringer og utvikler/QA-operasjoner.

## Rekkefølge

Operasjoner har `display_order` i `config/operations.json`. Rekkefølgen er brukerfaglig og styrer plasseringen fra venstre mot høyre under hver hovedknapp. GUI viser samme rekkefølge som `1.`, `2.`, `3.` osv.

## Ordinær master-workflow

- Kontroll: `1. XML/XSD`, `2. Noark 5-tester`
- Analyse: `1. Metadata`, `2. Arkivstruktur`
- Resultat: `1. Resultatvisninger`, `2. Depotrapport`
- Pakking: `1. DIAS-pakking`

De individuelle Noark 5-testresultatene er masterresultatet. Resultatvisninger og depotrapport bygger videre på lagrede resultater.

## Referanse og QA

- Referanse: `1. U1`
- Avansert: `1. Testregresjon`

`Noark 5-analyse` (`analyse_noark5_core`) beholdes foreløpig som implementasjon, men skjules fra operasjonskatalogen fordi den tidligere U1/U2-baserte modellen ikke lenger er masterarkitekturen.

Nye referansekilder som U2, historisk standard XPath og Arkade 5 skal først vises som egne operasjoner når de faktisk er koblet til workflow-modellen.
