# Analyse – Noark 5-objektnivåer

**Status:** Varig design- og implementasjonsbeskrivelse for den eksisterende
Analyse-arbeidsflaten. Gjelder første implementasjon gjennom v0.2.7-a5.

## Formål

Resultatvisning i DWM skal følge nivåene i Noark 5: arkiv, arkivdel, mappe/sak,
registrering/journalpost, dokumentbeskrivelse, dokumentobjekt og fysisk fil.
Hvert nivå viser observerte metadata, tilknyttet kildeevidens, faglige merknader
og relevante kontrollresultater – uten å utlede manglende objektposter fra
aggregert telling.

## Status per nivå

| Nivå | Implementasjonsstatus | Kilde |
|---|---|---|
| Arkiv | Åpnes som faktisk XML-objekt | Valgt arkivstruktur.xml |
| Arkivdel | Faktisk XML-objekt med systemID, tittel og foreldrekobling | Samme XML |
| Mapper/saker | Faktisk XML-objekt, inkludert xsi:type=saksmappe | Samme XML |
| Registreringer/journalposter | Faktisk XML-objekt, inkludert xsi:type=journalpost | Samme XML |
| Dokumentbeskrivelser/objekter | **Neste trinn** – ikke presentert som full liste i a5 | – |
| Fysiske filer/PUID | **Senere trinn** – behold eksisterende Siegfried/Arkade-statistikk | – |

Saksmappe og journalpost vises basert på faktisk XML-tagnavn eller xsi:type.
Hvis type ikke er oppgitt, gis ikke objektet en oppdiktet subtype.

## Brukerflyt

1. Åpne valgt jobb i **Analyse** (Enkel eller Avansert visning).
2. Velg **Noark 5 – Arkiv / Saker / Journalposter…**.
3. Objektlisten åpnes automatisk fra en fullstendig Work-indeks, eller
   DWM leser denne jobbens registrerte `arkivstruktur.xml` i en avbrytbar
   bakgrunnstråd. En egen bekreftelse for å bygge indeks er ikke nødvendig.
4. Dobbeltklikk Arkiv → Arkivdel → Mappe/Sak → Registrering/Journalpost.
   Tabellene viser bare direkte underobjekter, 100 om gangen.
5. Bruk søk innenfor valgte underobjekter, vis metadata og tilknyttede
   *identitetsverifiserte DWM-avleveringsfunn*, og registrer eventuelt
   kommentar i eksisterende Work-register.

En visning åpner den registrerte arkivstrukturen direkte. Den er foreløpig
fortsatt et separat vindu og erstatter ikke a2/a3/a4 Analyse,
Veiledet KS, Depotvurdering eller klassisk Resultatvisninger.

### Identitetskontroll og feilvisning (a5-fix1)

Hvis Analyse ikke har en `job_uid` i sitt øyeblikksbilde (noe eldre
jobblister/Qt-adaptere kan oppleve), hentes ikke identiteten fra en tilfeldig
jobb. Den kan bare leses fra `Work/job.json` når både jobb-ID-en og
rapportens `artifact_manifest.json` binder samme job-UID til rapporten.
En ikke-tom UID fra Analyse som avviker fra Work avvises fortsatt.
Manglende manifest, feil rapport og faktisk ulik jobbidentitet får ulike,
handlingsrettede feilmeldinger; ingen automatisk kobling gjøres på tvers av
Work-jobber. For uttrekk uten verifiserbar rapport-UID må man rette
jobb/Work-tilordningen, ikke manuelt endre `job.json`.

Den gamle ekstra Yes/No-bekreftelsen er fjernet fordi brukeren allerede
har valgt å åpne objektvisningen. En eventuell kildeinnlesing går i en
avbrytbar tråd; ingen ny Noark-test utføres og ingen Source-filer endres.


### XML-rotelement (a5-fix2)

`arkivstruktur.xml` er **filnavnet**, ikke rotelementet. Den offisielle
Noark 5-XSD-en for 3.1, 4.0 og 5.0 har `<arkiv>` som rotelement.
A5 hadde feilaktig et testeksempel med `<arkivstruktur>` rundt `<arkiv>`,
og validerte deretter mot dette oppdiktede rotelementet. Denne feilkontrollen
er rettet. Testgrunnlaget bruker nå en navneromsbundet `<arkiv>`-rot,
og en regresjonstest dekker nøstede `<arkiv>` (underarkiv).

Dette er en rettelse i **objektleseren**, ikke en endring i XSD-valideringen.
Original `arkivstruktur.xml`, Work-jobben, tidligere evidens og kommentarer
forblir uendret. Tidligere mislykkede forsøk har ikke publisert en ferdig indeks.

Referanse: `https://schema.arkivverket.no/N5/v5.0/arkivstruktur.xsd`
(rotelementets `xs:element name="arkiv"`).

## Kildebinding og datamodell

`app/noark_object_browser_v027_a5.py` bruker
`app.ks_xml_evidence_v023_a19.resolve_source_xml()` til å velge én XML-fil fra
**den konkrete Work-jobbens eksplisitt registrerte Source**. Det skannes aldri
andre jobber eller ukjente kildemapper. XML parses med `lxml.iterparse` med
nettverk/DTD/eksterne entiteter deaktivert og fortløpende sletting av leste
elementer. Minneforbruket for XML-leseren er knyttet til dybden, ikke antall
objekter; SQLite-databasen vokser med antall objekter.

En fullstendig strukturindeks lagres under:

`Work/noark5_evidence/noark5_objects_v027_a5/<id>.sqlite`

Til hver indeks hører et `.json`-manifest med `job_uid`, SHA-256 for
valgt depotrapport, kildefilens SHA-256, kildesignatur og komplett objektantall.
En ufullstendig parsing, avbrudd, endret kilde eller mismatch mot en dokumentert
Work-kilde-SHA publiserer **ikke** en gyldig indeks. Tidligere indeksversjoner
og originalrapporter overskrives ikke.

Hvis siste depotrapport inneholder en komplett `delivery_validation` med
`source_sha256`, kreves samsvar. Mangler historisk SHA, kan dagens Source
indekseres med synlig status **ikke verifisert mot tidligere Work-evidens**.
Ved frakoblet Source kan en tidligere komplett indeks fortsatt leses som
**lagret Work-projeksjon**, aldri som bevis for nåværende kildeintegritet.

### Struktur og identitet

Tabell `objects` inneholder intern rad-ID (eksakt forekomstposisjon ved den
indekserte kilde-SHA), foreldrerad-ID, arkivdel-rad-ID, XML-element, eventuell
`xsi:type`, faktisk `systemID`, direkte metadatafelt, XML-linje og søkestreng.
Foreldrekjeden følger observerte XML-nesting også gjennom klasse/
klassifikasjonssystem. Et tomt eller duplisert `systemID` beholdes som
usikkert, uten automatisk kobling til et enkelt kontrollfunn.

DWM avleveringsfunn knyttes bare når `findings_complete=True`, kilde-SHA er
verifisert mot Work, og objektets systemID er entydig i indeksen. De viste
funnene representerer **bare DWM-avleveringsfunn**, ikke alle Arkade-/XPath-
eller KDRS-kontroller. Fravær av treff er ingen faglig godkjenning.

### Kommentarer

Objektkommentarer skrives gjennom eksisterende
`noark5_workflow.analysis.depot_annotations.record_depot_annotation`, med
`view_id=analysis`, `target_type=noark5_object` og en entydig referanse til
kilde-SHA, faktisk rad-ID og objekttype. Det opprettes **ikke** et nytt
kommentar- eller beslutningsregister. Eksisterende a4-kommentarer til
områder, regler og forekomster beholdes uendret. Objektkommentarer vises i
objektnavigasjonen; felles visning og eksport kan samordnes senere.

## Bevisste avgrensninger

- XML-strukturen er en inspeksjonsindeks, ingen ny normativ Noark 5-test.
- Indeksen gjør ingen automatiske depotbeslutninger.
- Fullstendige dokumentobjekter, filkobling, PUID og kopi av dokumentfiler er
  **ikke** implementert i dette trinnet.
- Søk gjelder de *direkte* barna til valgt objekt, ikke hele uttrekket.
- En kilde uten dokumentert Work-SHA kan undersøkes, men kan ikke brukes til å
  tilskrive gamle DWM-avvik til enkeltobjekter.
- Ved store uttrekk bygges indeksen på en avbrytbar Qt-arbeidstråd. SQLite,
  Source og Work ligger på eksisterende filsystemer; det er ikke en nettportal.
- Historiske statusverdier eller delvis XML-evidens innebærer aldri null avvik
  eller en godkjenningsbeslutning.

## Videre

1. Neste trinn: dokumentbeskrivelse og dokumentobjekt med sikre
   relasjoner til valgt registrering; referanser til fysisk dokumentfil.
2. Filformatvurdering per konkret dokumentfil, med datert Nasjonalarkiv-profil
   som standard og historisk Arkade RAF som alternativ.
3. Eksplisitt kopiering av valgte PUID-/dokumentfiler, med flatt eller PUID-
   inndelt mål, kollisjonskontroll og verifisert manifest.
4. Fortsatt bruk av eksisterende `report_service_a20` til rapporter for ett
   eller flere uttrekk og separate, kildebundne KS-/depotrapportutkast.

## Regresjon

`py -m unittest discover -s tests -p "test_v027_a5_noark_objects.py" -v`

`py tools/release_gate.py --development`

`test.bat` – kjøres på Windows for full DWM-regresjon før commit.
