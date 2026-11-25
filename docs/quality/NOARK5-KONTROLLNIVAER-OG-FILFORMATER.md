# DWM – Noark 5-kontrollnivåer og dokumentfiler

**Kodegrunnlag:** `dev-0.2.7-alpha` med fullført `v0.2.7-a5-fix2`.

## Mål og to innganger

DWM skal bevare **to forskjellige, komplementære måter** å arbeide med Noark 5-uttrekk på.

1. **Objektvisning / stikkprøver (a5):** velg arkiv, arkivdel, mappe/sak og registrering/journalpost, og undersøk kildeobjekter, deres metadata, avleveringsfunn og kommentarer. Opprinnelig Source berøres ikke.
2. **Kontrollorientert visning (a6):** velg overordnet omfang, status og hvilket Noark-nivå du vil undersøke, **uten å gå gjennom alle mellomliggende nivåer**. Dokumentfil/filformat er første fullt operative seksjon. Den samme arbeidsflaten skal senere samle krav, tester og avvik på de andre nivåene.

## Direkte nivåvelger

Nivåer i kontrollrekkefølge:

| Nivå | Status |
| --- | --- |
| Arkiv | Direkte nivåvalg etablert. Detaljer/stikkprøver via a5. Full testmatrise per nivå gjenstår. |
| Arkivdel | Direkte nivåvalg etablert, valg av arkivdel tilgjengelig; full testmatrise gjenstår. |
| Klassifikasjonssystem | Skall etablert; full kilde- og testprojeksjon gjenstår. |
| Klasse | Skall etablert; full kilde- og testprojeksjon gjenstår. |
| Mappe / Sak | Skall etablert; eksisterende a5-inspeksjon tilgjengelig. |
| Registrering / Journalpost | Skall etablert; eksisterende a5-inspeksjon tilgjengelig. |
| Dokumentbeskrivelse | Nivåvalg, sammenstilling med dokumentfiler der XML-kobling er entydig. **Ikke** komplett dokumentbeskrivelsesregister. |
| Dokumentobjekt | Nivåvalg, sammenstilling med dokumentfiler der XML-kobling er entydig. **Ikke** komplett dokumentobjektregister. |
| **Dokumentfil / Filformat** | **Operativt:** individuelt filregister, filformat-/PUID-filter, faglig vurdering, merknader og kopiering. |

Statusfilter for dokumentnivå: alle, faglig avvik, faglig akseptert, til avklaring, uten faglig vurdering, uidentifisert/flertydig, finnes i valgt formatliste. De øvrige nivåene er eksplisitte skall i a6 og må aldri fremstilles som komplett testdekning.

## Filidentifisering og vurderingsgrunnlag

### Faktiske filoppføringer

`noark5_workflow/operations/siegfried_stream_v022_a4.py` produserer allerede en fullført, Work-eid DWM/Siegfried-kjøring med følgende:

- `external_evidence/siegfried/<run>/manifest.json` med jobb-UID, kilde og SHA-256 for råresultater og inventar;
- `file_inventory.jsonl` med én relativ sti, størrelse og filens `mtime_ns` per dokument;
- `siegfried_files.jsonl` med ett faktisk Siegfried-resultat per fil, i nøyaktig samme rekkefølge.

A6 leser begge JSONL-filene i takt og publiserer en **komplett SQLite-projeksjon i Work** først etter at filantall og begge SHA-256-summer stemmer med manifestet. Kildestien må høre til valgte jobbs lagrede Source. Innhold fra andre jobber, mislykkede/partielle kjøringer eller en løs PRONOM-aggregatsum blir aldri brukt som konkret filreferanse.

Filidentifikasjon behandles separat fra formatvurdering:

- Én entydig PRONOM-treff gir PUID/formatnavn/versjon.
- Flere mulige PRONOM-treff står som **flertydig**, ikke automatisk godkjent.
- Ingen gyldige treff står som **uidentifisert**.
- Registrert Siegfried-feil står som **identifikasjonsfeil**.

### Arkivdelkobling

A6 kan lese `arkivstruktur.xml` fra den samme Work-jobbens registrerte Source. **Bare når XML-SHA-256 samsvarer med lagret Work-evidens**, kan filreferansen `dokumentobjekt/referanseDokumentfil` brukes til å knytte et konkret dokument til en native arkivdel-systemID. Kun entydige, komplette relative `DOKUMENT/...`-referanser kobles. Basename- eller tittelmatching brukes ikke. Dobbel referanse, ingen referanse eller utilgjengelig/ikke attestert XML gir **ukjent arkivdeltilhørighet**. Bare tilordnede dokumentfiler blir med i et valgt arkivdelfilter. Hele uttrekket viser alle individuelt registrerte filer.

### Regel- og faglig vurdering

Varig standard settes fortsatt i **Setup → Filformatvurdering**. Kontrollvisningen leser valgt grunnlag ved åpning og tillater midlertidig sammenligning uten å endre Setup:

- **Nasjonalarkivet, datert liste 2026-11-10:** eksisterende `app.format_policy_v0110_a4` og `config/formats/nasjonalarkivet_2026-11-10.json`. Treff betyr *på valgt liste*, ikke juridisk eller depotfaglig godkjenning.
- **Arkade 5 RAF-220301:** eksisterende historiske Arkade-vurderinger på PUID-aggregatnivå kan vises når de finnes i Work. De kommer **ikke** fra den aktuelle enkeltfilen og er ikke gjeldende norm i seg selv.

En bruker med registrert depotprofil kan legge inn en begrunnet faglig status per PUID: **faglig akseptert for dette uttrekket**, **avvik**, eller **krever avklaring**. Dessuten finnes merknad, spørsmål, oppfølging og akseptabelt avvik. Hendelsene blir historisert i det **eksisterende** rapportbundne `depot_annotations.json` (view_id `analysis`); ingen ny beslutningsdatabase, ingen endring av tekniske testresultater og ingen automatisk depotgodkjenning. Ved nytt Siegfried-rawgrunnlag arves ikke tidligere faglige vurderinger automatisk.

## PUID-utvalg, filtrert visning og filkopiering

Bruker velger PUID-er i en **avkryssbar liste**, eventuelt begrenset med arkivdel, status og fritekstsøk. Dokumentfilene vises sidevis med PUID, relativ dokumentsti, format, størrelse, eventuelt verifisert arkivdel og dokumentobjekt. Kopieringen omfatter kun avmerkede filtyper som samsvarer med valgt status-/arkivdelfilter. **Fritekstsøk avgrenser visningen, ikke kopieringen;** velg PUID-ene før kopiering.

Kopieringen krever en eksisterende målmappe som **ikke overlapper Source eller Work**. Resultatet legges i et nytt `DWM-filutvalg-<tid>-<id>`-område under valgt mappe, aldri direkte over eksisterende filer. Brukeren velger:

1. **Standard:** `fmt_14/`, `x-fmt_263/` osv. med dokumentfilene i PUID-undermapper.
2. **Flat:** alle filene under kopimappen, med sikker deterministisk navnedifferensiering ved kollisjoner.

Før hver fil kopieres, kontrolleres Source-sti, filtype, størrelse og modifikasjonstid mot det lagrede Siegfried-inventaret. Kopiert fil får SHA-256 og blir deretter lest tilbake for verifikasjon. Full oversikt over kilde, mål, størrelse, PUID, arkivdel-ID, dokumentobjekt-ID og SHA-256 skrives til `kopimanifest.jsonl`, samt `sammendrag.json`. **Ingen flytting, overskriving eller konvertering.** Ved kildeendring, avbrudd, feil eller kollisjon fjernes den ufullstendige mellomkatalogen uten å publisere en sluttmappe. Ved arkivdelfilter må også `arkivstruktur.xml` fremdeles stemme med det verifiserte grunnlaget.

**Avgrensning:** Kopifunksjonen identifiserer kopier av originaler, ikke en ny AIP eller selvstendig arkivoverføring. Målområdet må ha kapasitet og tilstrekkelige rettigheter. Sjekksum beviser kopiens byteidentitet på kopieringstidspunktet, ikke at formatet er bevaringsmessig egnet.

## Kode

- `app/noark5_document_workbench_v027_a6.py`: Work-evidens, SQLite-indeks, fil-/PUID-filter, klassifisering, merknader og sikker kopiering.
- `gui_qt/noark5_document_workbench_v027_a6.py`: nivåvelger, separat kontrollvindu, kilde-/statusvalg, checkbox-liste, paginering, merknader, bakgrunnstråder og kopidialog.
- `gui_qt/__main__.py`: legger til a6 etter a5 kun i ekte Qt-hovedvindu. Eldre Resultatvisninger, Veiledet KS og samlerapportmotorer er uendret.
- `tests/test_v027_a6_document_workbench.py`: kildeintegritet, nivåskall og endringstransaksjoner.

## Videre trinn

1. Fullstendige kildeobjekter for dokumentbeskrivelse/dokumentobjekt (også uten filreferanse), med Noark-metadata og A4-kommentarer per objekt.
2. Normative Noark 5-kontroller og faglige merknader per nivå, versjonsbundet til Noark 3.1/4.0/5.0 – ikke bare dagens DWM-avleveringsfunn.
3. Samlet, komplett kildebundet funnregister per arkivdel/objekt fra DWM, Arkade, XSD og XPath; ingen skjult avkorting.
4. Omfangs- og resultatbasert navigasjon fra samlerapporter og flere jobber, med jobb-UID som varig identitet.

## Praktisk test

Start fra repo-roten på `dev-0.2.7-alpha` **etter a5-fix2**:

```bat
py -m unittest discover -s tests -p "test_v027_a6_document_workbench.py" -v
py tools/release_gate.py --development
test.bat
```

Åpne Analyse for ett ferdig Noark 5-uttrekk, trykk **Noark 5-kontroller → Velg nivå / Filformater / Dokumentkopiering**, velg direkte **Dokumentfil / Filformat**, kryss av én eller flere reelle PUID-er, kontroller status og detaljer, og test først kopiering av et lite utvalg til et ufarlig og **tomt kontrollområde utenfor Source/Work**. Kontroller kopier og manifest. Test også arkivdel, avviksvurdering, flat struktur og dupliserte filnavn.

**Teststatus:** Full Windows/Qt-prøving og full `test.bat` gjenstår etter utpakking. Lokale målrettede tester verifiserer backend og kilde-/oppstartskontrakter, men er ikke en formell brukergodkjenning.
