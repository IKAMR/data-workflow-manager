# DWM v0.2.1-a4 — metadata- og kravdekning for Noark 5 XPath

## Formål og utgangspunkt

Viderefører a1 (alle deklarerte XPath-kontroller og Work-resultater), a2
(KDRS/Saxon-kildesporing og regresjonsgrunnlag) og a3 (kildebasert
versjonskontroll). **Ingen ny XPath-motor, ingen endring av eksisterende
katalogtester og ingen automatisk faglig eller normativ godkjenning.**

DWM må kunne svare på *forskjellige* spørsmål:

1. Hvilket M-felt/krav er **registrert og kildebelagt for en bestemt Noark-versjon**?
2. Hvilke **deklarerte DWM-uttrykk nevner XML-feltet**, og hvilke har en eksplisitt
   referanse til et registrert standardverdisett?
3. Hvilke krav er faktisk **kontrollert mot korrekt kontekst og kardinalitet**?

Punkt 3 er fortsatt **ikke etablert** som en generell funksjon. Svar på 1–2
må ikke presenteres som bestått eller full dekningsgrad på 3.

## Nye, særskilt kildeverifiserte oppføringer for v5.0

Kilde: **Noark 5 versjon 5.0, Vedlegg nr. 1 Metadatakatalog**, Riksarkivet,
06.12.2018. Referanser er per *denne versjonen*, og er ikke hentet fra
nyere 5.5.0-vedlegg.

Offisiell dokumentlenke:
https://www.arkivverket.no/content/uploads/2025/11/Noark-5-v-5-vedl1-Metadatakatalog.pdf

| Metadata-ID | XML-element | Side i vedlegg 1 | Avgrenset dokumentert egenskap |
| --- | --- | --- | --- |
| **M002** | `klasseID` | 4 | Obligatorisk, én forekomst for `klasse` |
| **M003** | `mappeID` | 4 | Obligatorisk, én forekomst for `mappe` |
| **M005** | `versjonsnummer` | 5 | Obligatorisk, én forekomst for `dokumentobjekt` |
| **M007** | `dokumentnummer` | 6 | Obligatorisk, én forekomst for `dokumentbeskrivelse` |

Disse fire oppføringene er lagt til i det **eksisterende**
`config/noark5/standards/metadata/5.0.json`, med kilde-ID,
spesifikk kildeplassering, Noark-versjon og *bare de konkret kildebelagte*
egenskapene. Det er også registrert fire separate lokale krav-ID-er i
`requirements/5.0.json` for **tilstedeværelse/kardinalitet på riktig objekt**.
Identifikatorene er DWM-interne; de er *ikke* offisielle Noark-kravnumre.

**Totalt nå i DWM-registeret for v5.0:** 23 registrerte metadataoppføringer
(19 tidligere + 4 nye) og 6 registrerte krav (2 tidligere funksjonskrav +
4 nye metadatakrav). Dette er fremdeles **bare delvis kunnskapsdekning**.
Kravregistrene for v3.1 og v4.0 inneholder fortsatt 0 kildeverifiserte
normative krav; dette betyr *ikke* at standardene har null krav.

Det at M002, M003, M005 eller M007 er obligatorisk for sine arkivenheter
gir **ikke** automatisk en DWM-godkjenning. En virkelig kontroll må blant
annet avklare hvilke objekter som inngår, eventuell valgfri foreldrestruktur,
XSD/kardinalitet, manglende eller tom verdi og relevante unntak.

## Read-only analyse og datakilder

Ny modul: `app/noark5_xpath_metadata_qa_v021_a4.py`.

Data hentes fra **eksisterende** `xpath_catalog_2026_05_26.json`,
`metadata/{3.1,4.0,5.0}.json`, `requirements/{3.1,4.0,5.0}.json`,
`noark5_standard_values.json` og `sources.json`.

For hver deklarert XPath-metrikk registreres en *kandidat* dersom et
metadatafelts eksakte XML-navn forekommer i et uttrykk utenfor siterte
tekstliteraler. Dette er **leksikalsk likhet**, ikke semantisk samsvar.
Spesialhandlere der uttrykket ligger i Python blir ikke uriktig omtalt
som eksplisitt XPath-dekning.

Et **eksplisitt verdi-settreferanse** krever en katalogregistrert
`standard_value_checks`-referanse til registrert sett for riktig versjon,
rett metadata-ID og en eksisterende metrikk-ID; kildestatus vurderes
separat. Selv et slikt treff betyr ikke at M300 eller annet felt er
helhetlig validert. U1/U2 er fortsatt utviklings-/regresjonsreferanser.

Krav som beskriver *funksjonalitet eller autorisasjon* og ikke kan
bekreftes fra et statisk XML-uttrekk, vises eksplisitt som
`not_directly_testable_from_extract`.

Resultatet er i minnet og endrer **ikke** Source, Work, gamle resultater,
kanoniske indekser, kontroller eller DIAS AIP-pakking. `--summary`
skriver bare sammendrag til standard utdata, ingen filer.

## GUI — samme arbeidsflate

Åpne **Resultatvisninger → Oversikt → Vis alle XPath-kontroller…**.

* Nytt XPath-filter **Metadata / krav**, blant annet *XPath omtaler
  metadatafelt*, *Eksplisitt verdi-settreferanse* og *Ingen metadata-kandidat*.
* Ny fane **Metadata og krav** i det **samme vinduet**, ved siden av
  **XPath-kontroller**. Fanen viser *alle registrerte* metadata/krav for
  valgt Noark-versjon, også der XPath-kandidater mangler.
* Velg en metadata- eller kravrad for dokumentert kilde, XML-feltnavn,
  konkrete DWM-test-ID-er, metrikker og uttrykk. Valg av Noark-versjon
  gjelder begge faner.
* Eksisterende FEIL/WARNING/NOTE, KDRS-kildefilter, Work og XSD-visning
  består.

Fanene er ikke nye testmotorer. Manglende lenke betyr *ikke dokumentert
kobling*, ikke automatisk at testen er irrelevant eller kravet ikke finnes.

## Kommandolinje (valgfritt)

Kun sammendrag for v5.0:

```bat
py -m app.noark5_xpath_metadata_qa_v021_a4 --version 5.0 --summary
```

Fullt JSON-koblingsregnskap for alle registrerte versjoner (kan bli langt):

```bat
py -m app.noark5_xpath_metadata_qa_v021_a4
```

## Hva som skal testes — og hvordan

1. Pakk ut a4-deltaen over **committet/pushet v0.2.1-a3** i reporoten.
2. Kjør `test.bat` og krev **0 feil**. Kjør deretter `start.bat` og kontroller
   at DWM viser **v0.2.1-a4**.
3. Med en eksisterende jobb: åpne **Resultatvisninger → Oversikt → Vis alle
   XPath-kontroller…**. Velg **Noark 5 v5.0** og fanen **Metadata og krav**.
4. Finn **M002**, **M003**, **M005** og **M007**. Kontroller kildested og at
   mulige XPath-treff **ikke** vises som bestått validering.
5. Finn **M300**. En verdi-settreferanse eller et treff i `dokumentmedium`
   skal **ikke** betegnes som faglig verifisert M300-kontroll.
6. Bytt til v3.1/v4.0: ingen v5.0-krav eller kildeverifikasjoner skal arves.
   I fanen **XPath-kontroller**, prøv nytt *Metadata / krav*-filter.
7. Du trenger **ikke** kjøre nye XML-kontroller, teste Ingest eller produsere
   en AIP i denne GUI-røykprøven.

Hvis tiden er knapp, er `test.bat` hovedkontrollen nå. Praktisk Windows GUI-
kontroll kan noteres som utsatt. Dette er **ikke** en full normativ
dekningsrevisjon eller Saxon/lxml-ekvivalensverifikasjon.

## Videre

* a5: FEIL/WARNING/NOTE og øvrige kontrollfunn kobles tydeligere til
  kilde-, metadata- og regelidentitet, uten falsk alvorlighetsgrad.
* a6: XML-/objekt-/arkivdels- og dokumentevidens per funn.
* a7: samlet verifisering, kontrollerte datadekningshull og regresjon mot
  faktiske uttrekk for alle tre versjoner.
