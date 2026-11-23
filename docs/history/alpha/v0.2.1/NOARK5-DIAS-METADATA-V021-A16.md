# DWM v0.2.1-a16 – komplett DIAS/METS-inventar og kildebundet metadataredigering

## Formål og avgrensning

a16 viderefører den **eksisterende** `metadata/depot_metadata.json` og de 47
Arkade 5-feltene, men begrenser ikke XML-innsynet til denne flate modellen.
Alle tekst- og attributtforekomster i en bevart ytre `info.xml` eller indre
`dias-mets.xml` indekseres med **entydig, forekomstnummerert XML-sti**.
Gjentatte `agent`, `note`, `altRecordID`, `file`, `FLocat`, utvidelsesfelter og
attributter blir ikke redusert til første forekomst. Tomme XML-elementer
fremgår som ikke-redigerbare strukturopplysninger.

**Viktig:** Dette er en fullstendig inventering av tekst- og attributtverdier
i **hver kildefil som kan leses innenfor dokumenterte sikkerhetsgrenser**, ikke
en påstand om at de 47 Arkade-feltene alene er hele METS-standarden eller at
alle tenkelige DIAS-pakker er støttet. Originalfilens byteinnhold er fortsatt
autoritativ kildeevidens, inkludert eventuelle kommentarer, navnerom og annen
XML-representasjon som ikke blir redigert av a16.

`0000-metadata-arkade.xlsx` rad 1–47 er grunnlag for 47-feltlisten;
`docs/integrations/dias/DIAS-METADATA-MAPPING.md` og Arkade 5s `ArchiveMetadata`,
`SubmissionDescriptionCreator`, `DiasMetsCreator` og to XSD-er er kildekartlegging.
De fire eksisterende depot-/katalogfeltene (eierkommuner, historiske
arkivskapere, systemregion, innleveringsinformasjon) vises separat – **ikke**
som påståtte METS-felt. Systemkategorier og øvrig systemregister i
`0000-kommune-elarkiv.xlsx` er grunnlag for senere depotprofil/modell, ikke
et ekstra METS-navnerom eller en Noark-regel.

## Brukerflate – eksakt sti

1. **Resultatvisninger → Faglig vurdering → Visning: Depotvurdering**.
2. Marker uttrekket og klikk **Sjekkliste / METS…**.
3. Velg fanen **Metadata og kilder**.
4. Klikk **Komplett DIAS/METS: sammenlign og rediger metadata…**.

I dialogen:

- **Bevart kilde** velger en byte- og SHA-256-verifisert import; ytre/indre
  METS har forskjellige navnerom og forblir adskilte. Du kan importere
  ytterligere METS-kopier med **Importer METS-kopi til Work…**. Originalfilen
  leses, mens identiske bytes lagres under Work/metadata/source_evidence/.
- **Arkade 5 – 47 metadatafelt** viser den kjente redigerbare metadataoversikten.
  Endring av disse feltene går til *samme* `metadata/depot_metadata.json`
  (`current` + `review.history`) som eksisterende metadataeditor bruker.
- **XML – alle registrerte forekomster** viser det faktiske kildeinnholdet,
  inkludert gjentatte roller/kontakter, filmetadata, sjekksummer, stier,
  ukjente kildefelt og struktur. En redigering lagres som en **arbeidsverdi**
  bundet til eksakt XML-kildes SHA-256 og den indekserte XML-stien, med
  append-only hendelse i `metadata/dias_mets_field_events_v021_a16/`.
  Kjent kanonisk metadata (de 47 Arkade-feltene) kan **bare** redigeres fra
  47-feltlisten; samme XML-forekomst vises, men er da skrivebeskyttet i
  XML-inventaret. Teknisk filmetadata i `fileSec` krever en ekstra bekreftelse
  om at dette kun er en Work-arbeidsverdi, ikke ny filintegritet.
- **Bare ulike / endrede** filtrerer forskjellene. Like verdier er nøytrale;
  avvikende verdier står med **uthevet skrift og kontrastfarge**.
  Tomme Work-felt vises som ikke registrert, ikke som automatisk avvik.
- **Søk** går gjennom alle indekserte forekomster. Tabellen tegner maksimalt
  450 treff om gangen for ytelse, med antall totale treff i statuslinjen; ingen
  kildedata forkortes eller slettes av denne visningsgrensen.
- **Lagre endring i Work** krever DWM-brukerprofil, endret verdi og faglig
  begrunnelse. Konkurrerende eller foreldet editorstatus avvises.

**Endringer blir ikke skrevet til original `info.xml`, indre METS, original
Source, arkivstruktur, tekniske kontrollrapporter eller tidligere rapporter.**
Det produseres ikke en korrigert SIP/AIP eller en autorisert ny METS-fil i a16.
Arbeidsverdier på rå XML-stier må derfor ikke forveksles med korrigert
arkivpakke eller bekreftet kildefakta. Formell beslutning forblir manuell.

## Kildetrohet og feiltilfeller

- Innlesing krever METS med LOC-navnerom for ytre fil, eller
  `http://arkivverket.no/standarder/METS` for indre DIAS.
- Bevarte filkopier verifiseres mot opprinnelig registrert SHA-256 ved hver
  lesing. Uten verifiserbar kopi vises de 47 Work-feltene, men visningen gjør
  **ikke** krav på komplett historisk XML.
- Utrygge/relative stier, symlinks, manglende Work-jobbidentitet,
  endret kildehash, uregistrert bruker, korrupte/tamperede endringshendelser,
  DTD og entitetsdeklarasjoner avvises.
- Øvre grense per kildedokument er 32 MiB og 180 000 XML-elementer for denne
  GUI-/indekseringsvarianten. Større METS med mange filobjekter **avvises
  eksplisitt**, aldri delvis importert eller feiltolket som komplett.
  Streaming-indeks for svært store DIAS AIP/SIP er et senere arbeidspunkt.

## Praktisk test på Windows

1. Pakk `v0.2.1-a16.zip` over **committet v0.2.1-a15**.
2. Kjør `test.bat`; ikke commit ved feil.
3. Åpne `1525_004` i Depotvurdering og gå til den nye dialogen.
4. Kontroller at **47 Arkade-felt** og omtrent **124 XML-forekomster** vises
   for den tidligere importerte `info.xml` i dette testgrunnlaget.
5. Sammenlign `METS LABEL`, `DELIVERYSPECIFICATION`, arkivskaper/eier,
   `CREATOR SOFTWARE`, system-/uttrekksversjon og `STARTDATE/ENDDATE`.
   Like verdier skal ikke fremheves.
6. Endre et ikke-kritisk felt til en *testverdi*, med begrunnelse; kontroller
   at gjeldende verdi og endringshistorikk oppdateres, og tilbakefør deretter.
7. Importer eventuelt en **indre** `dias-mets.xml`; sjekk separat kildevalg og
   forekomster fra `fileSec`, og at originalen er uendret.
8. Åpne eksisterende metadataeditor; kontroller at de 47 kanoniske verdiene
   fra a16 er de samme som i den gamle editoren. Arkades funn, N5.22 `ERROR`,
   sjekklistevurderinger og tidligere rapporter skal være upåvirket.

## Utviklingskontroll

- **95 målrettede tester** fra a12–a16 består lokalt (68 tidligere + 27 nye).
- Ekte `1525_004`-kilde i *isolert Work-kopi*: 47 kanoniske felter, 124
  individuelle XML-forekomster, ingen konflikter i disse 47, SHA-256-kontroll
  og bevart original etter prøveredigering.
- Qt-vinduene er syntax-/integrasjonssjekket, men **ikke** visuelt kjørt mot
  Windows/PySide6 her. Full `test.bat` og praktisk GUI-test gjenstår hos bruker.

## Avgrenset videre plan

- **a17:** Depotprofil, første generiske profil **Test Depot**, valgfri
  logo/ikon, avsender, saksbehandler, `Small/Medium/Full` dokumentheader.
- **a18:** Konsolider to historiske sjekklisteutkast til **ett** vedlikeholdt
  dokumentgrunnlag og en profilbasert sjekklistevisning, koblet til evidens.
- **a19:** Enkel lineær kontrollflyt i tillegg til uendret avansert modus.
- **a20:** Profilbasert godkjenningsbrev fra samme datagrunnlag, med eksplisitt
  manuell godkjenningsbeslutning – ingen automatisk aksept.
- **Senere:** Strømmebasert indeksering av store indre METS-filer, strukturell
  eksport av korrigert XML når egen prosess og kontroll er avklart, og
  kontekstvisning av originale XML-forekomster fra tekniske kontrollfunn.
