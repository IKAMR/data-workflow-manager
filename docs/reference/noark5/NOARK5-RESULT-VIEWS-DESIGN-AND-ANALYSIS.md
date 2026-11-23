# Noark 5 resultatvisninger – design- og analysegrunnlag

Dette dokumentet er en inngang til prosjektkunnskapen som ble konsolidert i a18–a20. Det supplerer `NOARK5-ANALYSIS-MODEL.md` og `design-reference/README.md`.

## Retningen

Resultatvisningene skal utvikles fra tekniske resultatlister til et depotfaglig arbeidsverktøy som raskt viser hva uttrekket inneholder, hva kontrollene sier, hva som er uvanlig eller mangler, og hvor brukeren bør undersøke videre.

Det skal fortsatt være mulig å gå helt ned i evidens og detaljer. Visuell forenkling betyr derfor ikke at informasjon fjernes; informasjonen organiseres etter nivå.

## Oversikt

Oversikt er hele uttrekkets beslutnings- og orienteringsflate. Den bør prioritere uttrekks-/jobbkontekst, sentrale mengder, kontrollstatus, korrespondanseprofil, arkivdelstatus, tidsbilde, viktige filformater, vurderingspunkter og innganger til videre arbeid. Den skal ikke kopiere full faktaprofil eller tre detaljerte årsdiagrammer fra Arkivdeler.

## Arkivdeler

Arkivdeler er analyseflaten. «Alle arkivdeler» gir aggregert detaljanalyse for hele uttrekket; valg av én arkivdel bruker samme modell avgrenset til denne. Tre årsprofiler holdes separate fordi mappe/sak, registrering/journalpost og dokument kan ha forskjellige mønstre og forskjellige tekniske uteliggere.

Under periodeprofilen skal en scrollbar faktaprofil kunne utnytte mest mulig av resten av vinduet. Her kan all relevant materialisert metadata presenteres intelligent, blant annet typer, statuser, korrespondanse, dokumentrelasjoner, format/medium, skjerming, kassasjon, struktur og andre domeneopplysninger. Brukeren må kunne scrolle ned for dybde uten at detaljene dominerer førstebildet.

## Depotfaglig premiss

DWM vurderer mottatt uttrekk og skal bevare skillet mellom observerte data og faglig konklusjon. Historiske uferdige statuser og andre kvalitetsproblemer kan være en sann del av kildens historie. Verktøyet skal synliggjøre dem, ikke etablere en forventning om at arkivskaper/leverandør burde ha manipulert produksjonsdata før uttrekk for å skape et perfekt resultat.

## Visuelle referanser

De seks opprinnelige målbildene i `docs/design-reference/noark5/` beholdes. Bildene 07–10 dokumenterer den nyere retningen og er særlig relevante for videre arbeid med Oversikt og Arkivdeler. Se `docs/design-reference/README.md` for navn og rolle.

## Videre analyse

Videre arbeid bør prioritere å gjøre eksisterende kanoniske resultater rikere og mer gjenbrukbare fremfor å bygge GUI-spesifikke beregninger. Særlig statusfordelinger, relevant fravær, korrespondanse, periodeavvik og komplett faktaprofil er naturlige kandidater. Lokal KI/Ollama kan senere legges over dette resultatlaget som rådgivende analyse, aldri som erstatning for deterministiske resultater eller menneskelig depotvurdering.
