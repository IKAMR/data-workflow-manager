# Designreferanse – Data Workflow Manager

Denne mappen inneholder visuelle målbilder for videre utvikling av
Data Workflow Manager.

Målbildene er **design- og funksjonsreferanser**, ikke en ferdig eller
uttømmende spesifikasjon. De skal brukes som støtte ved vurdering av
informasjonsarkitektur, arbeidsflyt, begrepsbruk og presentasjon av resultater.

## Noark 5-resultatvisning

Målbildene for Noark 5 ligger i:

`docs/design-reference/noark5/`

Planlagt filstruktur:

1. `01-resultatvisninger-oversikt.png`
2. `02-vurderingspunkter.png`
3. `03-arkivdeler.png`
4. `04-kontroller-evidens-arkade5.png`
5. `05-kontrolldetalj-avskrivningsmate.png`
6. `06-rapport-utkast.png`

## Hva målbildene skal brukes til

### 1. Resultatvisninger – oversikt

Målbilde for samlet oversikt over uttrekket, med blant annet:

- samlet kontrollbilde
- DWM-kontroller
- Arkade 5-kontroller
- resultater uten avvik
- resultater som krever vurdering
- feil
- dekning og overlapp mellom DWM og Arkade 5
- prioriterte vurderingspunkter som krever oppmerksomhet

### 2. Vurderingspunkter

Målbilde for arbeidsliste over forhold som krever menneskelig vurdering, med
mulighet for filtrering, søk og videre behandling.

Visningen bør kunne skille mellom blant annet:

- nye vurderingspunkter
- forhold under vurdering
- forhold som må rettes
- arkivdeler som berøres
- ansvar/tildeling
- frist

### 3. Arkivdeler

Målbilde for arkivdelorientert gjennomgang.

Visningen skal støtte rask vurdering av hver arkivdel og tydelig skille mellom:

- teknisk/materialisert datagrunnlag
- kontroller og evidens
- vurderingspunkter
- depotets egen behandlingsstatus

Komplett datagrunnlag skal ikke tolkes som automatisk faglig godkjenning.

### 4. Kontroller / evidens – Arkade 5

Målbilde for presentasjon av ekstern evidens fra Arkade 5.

Arkade 5-resultater skal behandles som ekstern evidens og holdes adskilt fra
DWM sine egne kontroller. Visningen bør støtte sammenligning av flere
Arkade 5-kjøringer og versjoner.

### 5. Kontrolldetalj

Målbilde for detaljvisning av én kontroll eller ett vurderingsområde.

Visningen bør kunne samle:

- sammendrag
- verdifordeling
- sammenligning
- rådata
- relaterte funn
- DWM-resultat
- Arkade 5-evidens

### 6. Rapport – utkast

Målbilde for rapportgenerering og kvalitetssikring før endelig rapport.

Rapportvisningen bør støtte:

- forhåndsvisning
- innstillinger
- innhold
- notater
- eksport
- generering av rapport

## Viktig om eksempeldata

Bildene er konseptuelle målbilder.

Identifikatorer, kommunenummer, kommunenavn, systemnavn, perioder, datoer,
antall, testresultater og andre verdier i bildene er eksempeldata og skal
**ikke** tolkes som opplysninger fra et faktisk arkivuttrekk.

Målbildene skal derfor brukes som referanse for:

- struktur
- arbeidsflyt
- begreper
- funksjoner
- prioritering av informasjon
- visuell organisering

De skal ikke brukes som fasit for konkrete testverdier eller metadata.

## Bruk i utviklingen

Ved videre utvikling bør relevante endringer vurderes eksplisitt mot disse
målbildene.

Det er ønskelig å kunne dokumentere status per målbilde, for eksempel:

- ikke startet
- delvis implementert
- implementert
- avviker bevisst fra målbildet

Eventuelle bevisste avvik fra målbildene bør dokumenteres i relevant
utviklingsnotat eller release-dokumentasjon.

## Utvidede målbilder fra a18–a20

Følgende målbilder viderefører de seks opprinnelige referansebildene og dokumenterer retningen som ble etablert gjennom praktisk GUI-arbeid i a18–a20:

7. `noark5/07-oversikt-visuell-modernisering-a18.png` – før/etter-referanse for modernisering av Oversikt: statuskort, grafisk resultatfordeling og komprimert informasjonsstruktur. Bildet er historisk designreferanse; senere målbilder presiserer rollefordelingen mellom Oversikt og Arkivdeler.
8. `noark5/08-arkivdeler-periodeprofil-lang-periode.png` – designstudie for tre separate årsprofiler (mappe/sak, registrering/journalpost og dokument), vurderte ytterår, uteliggende år og eksempel på langt årsspenn 1998–2021.
9. `noark5/09-arkivdel-detaljert-faktaprofil-a20.png` – målbilde for valgt arkivdel: tydelig identitet/status, periodeprofil og en stor scrollbar detaljert faktaprofil med status- og fordelingsdata.
10. `noark5/10-oversikt-og-arkivdeler-rollefordeling.png` – gjeldende hovedreferanse for rollefordelingen: Oversikt er beslutnings-/orienteringsbildet for hele uttrekket; Arkivdeler er analyseflaten for totalen og enkeltarkivdeler.

### Prioritet mellom målbildene

Målbildene er utviklingsgrunnlag, ikke uforanderlige skjermspesifikasjoner. Når de overlapper, skal nyere målbilders informasjonsarkitektur normalt veie tyngst, mens gode elementer fra eldre bilder beholdes når de fortsatt passer. Vesentlige endringer i struktur eller rollefordeling skal drøftes før implementering; visuelle forbedringer som ikke endrer struktur kan foreslås proaktivt, gjerne som bilde/mockup før kodeendring.
