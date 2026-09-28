# Noark 5 – depotpresentasjon, vurdering og KI-støtte

## Formål

Dette dokumentet er den kanoniske kunnskapsreferansen for hvordan Noark 5-resultater skal presenteres og vurderes i `Resultatvisninger`.

Det bygger på den kanoniske XPath-/analysemodellen i repository, inkludert:

- `config/noark5/tests/xpath_catalog_2026_05_26.json`
- `config/noark5/analysis/u1_u2_coverage_2026_05_26.json`
- `config/noark5/analysis/legacy_regression_contract.json`
- `config/noark5/standards/noark5_standard_values.json`
- `docs/NOARK5-ANALYSIS-MODEL.md`
- `docs/NOARK5-U1-U2-COVERAGE-MAPPING.md`

2026-katalogen inneholder 60 aktive/definerte testobjekter, hvorav ett er et DWM-supplerende metadatauttak. Legacy-regresjonsgrunnlaget er 59 katalogtester. Katalogen dekker Noark 5 v3.1, v4.0 og v5.0, og U1/U2-rådatadekningen er dekomponert til individuelle kanoniske analyser.

Målet er ikke å gjenskape gamle U1/U2-lister i et penere GUI. Målet er å bruke de kanoniske resultatene til en bedre, mer intelligent og etterprøvbar presentasjon for depotarbeid.

## Overordnet presentasjonsmodell

### Oversikt – hele uttrekket

`Oversikt` skal svare raskt på:

> Hvordan står det til med hele uttrekket, og hva bør brukeren se nærmere på?

Oversikt skal være en beslutnings- og orienteringsflate, ikke en kopi av `Arkivdeler -> Alle arkivdeler`.

Typisk innhold:

- uttrekks-/jobbidentitet
- hovedtall for arkivdel, mappe/sak, registrering/journalpost og dokument
- teknisk kontrollstatus
- kompakt korrespondanseprofil
- arkivdelstatus og mangler
- kompakt periodeindikator for hele uttrekket
- viktige vurderingspunkter som løftes dynamisk fra hele analysegrunnlaget
- tydelig navigasjon til Arkivdeler, Depotvurdering, Filformater og Rapporter

Oversikt skal normalt ikke vise full detaljert faktaprofil eller tre store årsdiagrammer. Detaljene ligger i Arkivdeler.

### Arkivdeler – analyse og drill-down

`Arkivdeler` skal svare på:

> Hva består uttrekket av, hvordan er det fordelt, og hvorfor ser det slik ut?

`Alle arkivdeler` er aggregert analysevisning for hele uttrekket. Valg av én arkivdel viser samme faglige struktur for den valgte delen.

Den nederste delen av siden skal være en scrollbar analyseflate der alle relevante materialiserte resultater kan presenteres intelligent. Brukeren må kunne scrolle ned til full faktaprofil uten at førstebildet blir overlesset.

Denne delen skal være bedre enn de historiske XPath/U1/U2-utskriftene ved å:

- gruppere relatert informasjon faglig
- bruke lesbare labels i stedet for rå test-ID-er
- vise fordelinger, ikke bare totalsummer
- vise null/fravær eksplisitt når det er relevant
- skille observasjon, standardreferanse og depotvurdering
- bevare source-test/source-path slik at alle tall kan spores tilbake

## Faglige domener som skal kunne presenteres

### 1. Mappe / sak

Kandidater fra blant annet C08 og C13:

- mapper totalt
- saker og andre mappetyper
- mappetypefordeling
- saksstatus
- nivåfordeling
- opprettet/avsluttet/saksdato/møtedato
- mapper uten undermapper eller registreringer
- generiske mapper uten spesialisering
- møtearkiv/møtemapper der dette finnes

### 2. Registrering / journalpost

Kandidater fra blant annet C14, C15, C16 og C20:

- registreringer totalt
- journalposter totalt
- registreringstype
- generiske registreringer uten spesialisering
- journalposttype
- journalstatus
- opprettet-/journaldato pr. år
- arkivertDato-intervall
- journalposter med/uten hoveddokument

Journalposttype skal kunne presenteres som en lett forståelig korrespondanseprofil, for eksempel:

- inngående
- utgående
- notat
- andre

Samtidig skal alle faktisk observerte verdier beholdes og være tilgjengelige. Hardkodede historiske KDRS Query-tekster er ikke autoritativ sannhet.

### 3. Dokumentkjeden

Kandidater fra C19 og C21–C25:

- dokumentbeskrivelser
- dokumentobjekter
- hoveddokument / vedlegg / andre relasjoner
- registreringer uten dokumentbeskrivelse
- dokumentbeskrivelser uten dokumentobjekt
- dokumentstatus
- dokumenttype
- dokumentnummer
- versjonsnummer
- variantformat
- dokumentdatoer og årsfordeling

`Registrering uten dokumentbeskrivelse` og `Dokumentbeskrivelse uten dokumentobjekt` er særlig viktige kandidater for vurderingspunkter fordi de beskriver brudd eller hull i dokumentkjeden.

### 4. Format, medium og størrelse

Kandidater fra C02 og C24:

- dokumentmedium
- formatfordeling
- formatDetaljer
- variantformat
- filstørrelsesstatistikk
- størrelsesintervaller
- største/minste/gjennomsnittlige filstørrelse når datagrunnlaget finnes

Formatinformasjon skal kunne vises både samlet og per arkivdel.

### 5. Korrespondanseparter

Kandidater fra F05:

- totalt antall korrespondanseparter
- hvilken type element de er knyttet til
- typefordeling

For Noark 5.0 omfatter standardregisteret blant annet:

- Avsender
- Mottaker
- Kopimottaker
- Gruppemottaker
- Intern avsender
- Intern mottaker

Dette skal ligge som en egen detaljseksjon og ikke blandes sammen med journalposttype.

### 6. Arkivstruktur og klassifikasjon

Kandidater fra C05–C13:

- klassifikasjonssystemer
- klasser
- nivå 1–4
- tomme klasser
- klasser uten innhold
- klasse/mappe-konflikter
- mapper pr. nivå/type/status

Dette er viktig strukturinformasjon, men skal normalt ligge i detaljprofilen og bare løftes til Oversikt ved relevante funn.

### 7. Tilgang, skjerming og gradering

Kandidater fra F08 og F09:

- skjerminger totalt
- skjerming på arkivdel, klasse, mappe, registrering og dokumentbeskrivelse
- tilgangsrestriksjon
- skjermingMetadata
- skjermingDokument
- gradering

Skjerming er ikke bare et totalsummeringsfelt. Fordelingen forteller hva slags materiale uttrekket inneholder og hvor tilgangsreglene er brukt.

### 8. Bevaring, kassasjon og sletting

Kandidater fra F10, F11 og F13:

- kassasjonsvedtak
- fordeling av kassasjonsvedtak
- hvor kassasjon er knyttet
- utført kassasjon
- slettinger utenom kassasjon
- slettingstype

For Noark 5.0 inneholder standardregisteret blant annet `Bevares`, `Kasseres` og `Vurderes senere` for kassasjonsvedtak.

Forekomst av kassasjon, utført kassasjon eller sletting er viktig depotinformasjon og kan løftes til Oversikt som vurderingspunkt uten at det automatisk klassifiseres som feil.

### 9. Konvertering

Kandidater fra F12:

- konverteringer totalt
- konvertert fra format
- konvertert til format
- konverteringsverktøy

Dette er viktig for å forstå dokumenthistorikk og transformasjoner.

### 10. Parter, merknader, kryssreferanser og presedens

Kandidater fra F01–F04:

- sakspart/part
- hvor part er knyttet
- merknader
- kryssreferanser
- presedens

Dette hører normalt hjemme i den scrollbar detaljprofilen.

### 11. Avskrivning og dokumentflyt

Kandidater fra F06 og F07:

- avskrivningsmåte
- journalposter med avskrivning
- referanse til annen journalpost
- dokumentflyt

### 12. Journalfiler og endringslogg

Kandidater fra H-, I- og J-testene:

- løpende journal
- offentlig journal
- skjermede journalposter i løpende journal
- datointervall og årsfordeling
- kryssfil-sammenligning mot arkivstruktur
- endringslogg, antall, periode og endringer pr. år

Disse er primært hele-uttrekksdata og skal ikke late som de finnes per arkivdel dersom scope ikke støtter det.

### 13. Virksomhetsspesifikke metadata

Kandidater fra L02:

- total forekomst
- mappe
- sakspart/part
- registrering
- dokumentbeskrivelse

Stor eller uventet forekomst kan være viktig å løfte i Oversikt, fordi vesentlig informasjon kan ligge utenfor de ordinære Noark-elementene.

## Status på elementer er en del av historien

Statusfelt skal behandles som bevaringsinformasjon, ikke som kosmetiske kvalitetsmarkører.

Relevante standardsett omfatter blant annet:

- arkivstatus (`M050`)
- arkivdelstatus (`M051`)
- saksstatus (`M052`)
- journalstatus (`M053`)
- dokumentstatus (`M054`)

Verdier og tillatte standardsett varierer mellom Noark-versjonene. UI og analyse skal derfor bruke versjonsspesifikt standardregister og samtidig bevare alle observerte verdier.

Et uttrekk kan legitimt dokumentere at historiske data i produksjonsbasen ikke var perfekte. Eksempler kan være:

- sak fortsatt under behandling
- journalpost ikke journalført/ferdigstilt
- dokument fortsatt under redigering
- element med status `Utgår`

Workflow Manager skal ikke automatisk endre slike statusverdier for å produsere et «penere» eller mer komplett uttrekk.

### Prinsipp om historisk sannhet

Mottatt uttrekk er bevaringsbevis. Det skal som hovedregel analyseres og beskrives, ikke repareres for å passe en forventet idealtilstand.

Automatisk omskriving av en uferdig eller uønsket status til `Avsluttet`, `Journalført`, `Ferdig` eller tilsvarende kan forandre den historiske tilstanden som faktisk fantes i kildesystemet. En slik endring må derfor aldri være en skjult valideringssideeffekt.

Dersom en transformasjon en dag er nødvendig, skal den være:

- eksplisitt
- sporbar
- separat fra mottatt original
- dokumentert med begrunnelse og proveniens

Normal depotadferd er å bevare observasjonen og vurdere betydningen.

## Fravær er også et resultat

En telling av hva som **ikke** finnes i uttrekket er ofte like viktig som hva som finnes.

Presentasjonen og senere KI-støtte skal skille mellom minst disse situasjonene:

1. **Kilde mangler** – for eksempel manglende `loependeJournal.xml`.
2. **Element finnes ikke** – telling er reelt `0`.
3. **Felt mangler på observerte elementer**.
4. **Felt finnes, men verdi er tom**.
5. **Ikke relevant for valgt Noark-versjon eller scope**.
6. **Resultatet er ikke materialisert / analyse ikke kjørt**.
7. **Resultatet finnes, men er filtrert bort fra aktuell presentasjon**.

Disse tilstandene skal ikke presenteres som samme `0` eller samme `mangler`.

Vurderingspunkter kan blant annet oppstå når:

- forventede dokumentobjekter mangler
- registreringer mangler dokumentbeskrivelse
- en forventet type/status ikke forekommer
- hele datakategorier mangler i en arkivdel
- tidsserier har uvanlige topper eller uteliggende år
- statusfordelingen viser mye uavsluttet materiale
- standard-/observerte verdier avviker

Dette er observasjoner og kandidater til faglig vurdering, ikke automatisk feilklassifisering.

## Periode og ytterår

Periodepresentasjonen skal skille mellom:

- oppgitt periode
- observert periode
- vurdert periode

Vurderte ytterår kan markeres visuelt over årsfordelingen. Når vurderingen endres, skal markørene flytte seg.

Fjerne uteliggende år, for eksempel `2099`, skal ikke komprimere hele hovedperioden. De skal vises separat som observerte uteliggere. Systemet skal ikke automatisk konkludere med at en uteligger er feil.

Tilsvarende kan et teknisk sluttår, for eksempel 2020/2021, ha stor aktivitet selv om den faglig vurderte perioden slutter i 2019. Dette skal synliggjøres og vurderes, ikke skjules.

## Dynamisk løfting til Oversikt

Detaljdata skal ikke føre til stadig flere permanente dashboardkort.

I stedet skal `Vurderingspunkter` og andre kompakte oversiktselementer kunne løfte frem relevante funn dynamisk, for eksempel:

- uteliggende år
- dokumentbeskrivelser uten dokumentobjekt
- registreringer uten dokumentbeskrivelse
- stor andel uavsluttede saker/journalposter/dokumenter
- kassasjonsvedtak eller utført kassasjon
- slettinger utenom kassasjon
- virksomhetsspesifikke metadata
- betydelig skjerming/gradering
- avvik mellom arkivstruktur, løpende journal og offentlig journal
- manglende datagrunnlag

Den detaljerte forklaringen skal fortsatt ligge i Arkivdeler/Kontroller.

## KI/Ollama som førstegjennomgang

Lokal KI, for eksempel Ollama, er en naturlig kandidat for en rådgivende førstegjennomgang av det strukturerte resultatgrunnlaget.

En slik KI skal arbeide på materialiserte kanoniske resultater og vurderingsgrunnlag, ikke lese/endre originalkilden som en skjult sideeffekt.

Aktuelle oppgaver:

- oppsummere omfang og karakter
- peke på tydelige fravær
- finne uvanlige fordelinger
- beskrive statusmønstre
- se etter periodiske uteliggere
- prioritere hvilke vurderingspunkter en bruker bør undersøke først
- formulere forklarbare forslag basert på konkrete resultatreferanser

KI-resultat skal være **rådgivende**. Det skal ikke:

- endre Noark-kilden
- endre statusfelt
- automatisk godkjenne/avvise uttrekk
- skjule rå observasjoner
- erstatte menneskelig depotvurdering

En framtidig KI-vurdering bør minst registrere:

- modell/provider
- tidspunkt
- input/resultatgrunnlag
- hvilke source-test/source-path som støtter konklusjonen
- selve forslagsteksten
- eventuell menneskelig aksept/avvisning/kommentar som eget lag

Dette gjør også små lokale modeller nyttige: de trenger ikke «forstå alt», men kan effektivt gjøre første sortering av strukturerte funn og fravær.

## Visuell målreferanse

Gjeldende designretning ligger i:

`docs/design-reference/noark5/07-resultatvisninger-oversikt-arkivdeler-target.png`

Bildet er et målbilde, ikke en låst pikselspesifikasjon. Viktige strukturelle endringer skal fortsatt diskuteres før implementasjon.

Fargeprinsipp for sentrale domener:

- blå: mappe/sak
- gul: registrering/journalpost
- lilla: dokument
- grønn: komplett/OK
- grå: nøytral/annen
- tydelig kontrastmarkør: vurdert start/slutt og andre referansemarkører

## Maskinlesbar kunnskapsreferanse

Sammenfatningen av denne analysen finnes også maskinlesbart i:

`config/noark5/analysis/depot_presentation_knowledge.json`

Denne filen skal brukes som startpunkt ved videre arbeid med Resultatvisninger, slik at kandidatkartleggingen ikke må gjøres på nytt fra bunnen av.
