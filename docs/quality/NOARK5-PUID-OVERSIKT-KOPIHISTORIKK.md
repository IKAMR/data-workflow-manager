# DWM v0.2.7-a7 – kontrollnivåer, PUID-oversikt og kopihistorikk

**Grunnlag:** `dev-0.2.7-alpha` etter committet v0.2.7-a6 (`1607221b06ad14d135e921c634412a631acce305`). A5-objektnavigasjon og a6-format-/kopimotor er bevart.

## 1. To innganger – samme kildegrunnlag

**A5: Objektnavigasjon** er fortsatt en kildeverifisert, sidevis inspektør for stikkprøver: Arkiv → Arkivdel → Mappe/Sak → Registrering/Journalpost. Den brukes for oppslag i faktiske XML-objekter, felter og kommentarer.

**A7: Noark 5-kontroller** er den kontrollorienterte inngangen. Direkte nivåvalg eller «← Forrige Noark-nivå» / «Neste Noark-nivå →» viser følgende sammenhengende rekke:

1. Arkiv
2. Arkivdel
3. Klassifikasjonssystem
4. Klasse
5. Mappe/Sak
6. Registrering/Journalpost
7. Dokumentbeskrivelse
8. Dokumentobjekt
9. Dokumentfil/Filformat

**Nivå 1–8 er fremdeles navigasjonsskall i denne kontrollvisningen**, ikke påstander om at alle normative Noark 5-krav er implementert der. A5 er tilgjengelig fra disse skallene. Fullstendig kravdekning per nivå bygges videre på eksisterende XSD/XPath/KDRS/Arkade-evidens, ikke nye «OK»-statuser.

## 2. Operativt dokumentnivå i a7

Standardvisningen på Dokumentfil/Filformat er **PUID-grupper**, ikke 100 enkeltfiler med en gang. En rad per PUID viser:

| Felt | Betydning |
|---|---|
| Velg | Avkryssing av PUID for filter og kopiering; samkjørt med venstre liste |
| PUID | Dokumentert PRONOM-ID, eller eksplisitt uidentifisert/flertydig/feil |
| Kategori | Overordnet menneskelesbar gruppe (PDF, Bilde, XML, Kontor, Lyd, Video osv.) |
| MIME-gruppe | **Veiledende** fellesgruppe fra dokumentert formatnavn, ikke verifisert MIME for hver fil |
| Filformat | Siegfried-formatnavn fra lagret Work-evidens |
| Filer | Antall individuelle oppføringer under valgt omfang |
| Kopier | Sum registrerte filkopieringer fra a7; gjentatte kopieringer telles på nytt |
| Eksporter | Antall registrerte, fullførte kopieringsjobber som omfatter denne PUID-en |
| Faglig vurdering | Historisert vurdering fra eksisterende `depot_annotations.json`, ikke automatisk depotgodkjenning |

Bruk **dobbeltklikk på PUID** eller «↓ Vis filer for valgt PUID» for å åpne detaljlisten med de faktiske filene og kopieringsstatus per fil. «↑ Til PUID-grupper» går tilbake. Filetterne vises sidevis (100 om gangen), med nøkkelbasert sidebytte via indeksert `id` fremfor store SQL `OFFSET`.

Velg omfang **hele uttrekket eller en arkivdel**. Arkivdelantall baseres bare på entydig, kildeverifisert XML-kobling; manglende koblinger er ikke nullfunksjon eller bevis på at ingen dokumenter finnes. Søkeord og valgte PUID-er avgrenser visningen. Kopiering er fortsatt eksplisitt brukerhandling, aldri automatisk av et filterbytte.

### Formatvurdering

A7 gjenbruker Setup-innstillingen for Nasjonalarkivets daterte liste eller historisk Arkade RAF, og a6-funksjonene for faglige kommentarer: akseptert, avvik, avklaring, merknad, spørsmål og oppfølging. Valgt PUID og faglig vurdering er uavhengig av identifisering. Fravær fra Nasjonalarkivets liste er «til avklaring», ikke automatisk ugyldig format.

## 3. Varig kopihistorikk – skilt fra originalkildene

Etter at a6-kopimotoren har verifisert og publisert et komplett outputområde, registrerer a7 fullført eksport i:

`<Work>/noark5_evidence/document_copy_history_v027_a7.sqlite`

Tre tabeller er adskilt:

- `exports`: tidspunkt, Work-jobbens varige identitet, valgt Siegfried-kjøring, rapportrevisjon, outputområde, filmanifestets SHA-256, layout, arkivdelomfang og totalt antall.
- `export_groups`: antall filer per PUID og eksport for rask oversikt uten gjennomlesing av millioner av filrader.
- `copied_files`: én rad per faktisk kopiert fil, med original relativ filsti, PUID, arkivdel når dokumentert, kopihash og utsti. Indeks støtter oppslag for *bare* de 100 viste filene.

Alle filposter registreres i **én SQLite-transaksjon**, slik at en feil ikke gir delvis registrert eksport. Eksport av samme resultat/manifestsjekksum kan registreres på nytt uten duplikat. Målområdet inneholder fortsatt a6-originalene `sammendrag.json` og `kopimanifest.jsonl` med SHA-256; de endres ikke av historikkføringen.

**Kopieringsstatus er en historisk hendelse, ikke en garanti for at mottakeren fortsatt har filene.** Historikk viser bare a7-eksporter – eldre a6-kopier importeres ikke automatisk. En eventuell senere revisjonskontroll av eksportmappe må være eksplisitt.

Hvis kopieringen lykkes, men journalen i Work ikke kan oppdateres, gis en synlig advarsel **med outputstien**. Verifiserte, ferdige kopier skal ikke feilaktig omtales som bortfalt. `Source`, opprinnelig depotrapport og A6-dokumentregister endres ikke.

## 4. Store uttrekk – strategi for 10 000 til over 1 000 000 filer

| Størrelse | Lesing og GUI | Kopiering |
|---|---|---|
| 10 000 filer | PUID-grupper og 100 filrader per side | Standard kopiering etter PUID, valgfri flat struktur |
| 50 000–100 000 | SQLite-indeksert PUID-leser; ingen full filtabell i GUI | Strømmende kontroll, SHA-256 for hver kopi og fullført manifest |
| 1 000 000+ | PUID-tall fra a6-indeksens allerede beregnede `by_puid`; bare én formatprøve per PUID; indeksbaserte filsider via `(puid,id)` | Strømmende kopimotor, separat outputområde og journal som behandler manifestet linje for linje; diskplass og kopieringstid blir viktige |

**Syntetisk 1 000 000-raders backendkontroll** (lokal Linux-container, ikke GUI eller nettverksdisk): 5 PUID-grupper, 1 000 000 oppføringer, 100 rader lest fra omtrent posisjon 990 000. Observasjon: PUID-oversikt ca. 0,002 s, nøkkelbasert filside ca. 0,002 s etter klargjort SQLite-indeks; maksimum prosessminne ca. 107 MB. Dette er en teknisk røykprøve, **ikke en garanti** om ytelse på Windows/nettverkslager, ved XML-kobling, fritekstsøk eller faktisk kopiering.

**Gjenstående skaleringsgrenser:** a6 oppretter fortsatt en kontrollert komplett indeks ved første gangs lesing, som kan ta betydelig tid for 1M filer. Fritekstsøk gjennom `instr(search,...)` kan være tregt når svært mange rader må skannes, og a6 sin navnekollisjonskontroll ved selve kopieringen holder et voksende sett med filnavn. Disse delene bør stresstestes og eventuelt erstattes med diskbaserte indekser ved svært store kopieringsutvalg. Den a7-implementerte PUID-oversikten og keyset-pagineringen skalerer uavhengig av disse begrensningene. Det er derfor ikke korrekt å love at millionfil-kopiering eller alt søk er ferdig ytelsesverifisert.

## 5. Operatørtest i Windows

1. Pakk ut deltaen på `dev-0.2.7-alpha` over committet a6.
2. Kjør `py -m unittest discover -s tests -p "test_v027_a7_format_overview.py" -v` og `test.bat`.
3. Åpne `1525_004` → Analyse → Noark 5-kontroller. Se at **PUID-grupper vises først**, med MIME-gruppe, antall og vurdering. Test forrige/neste Noark-nivå og direkte nivåvalg.
4. Velg én PUID og gå ned til filvisningen. Gå opp igjen; test tekstfilter og avkryssing.
5. Kopier et **lite, eksplisitt valgt** PUID-utvalg til en separat mappe. Sjekk manifest/sjekksummer, og deretter PUID-kopitall, filmerker og «Kopihistorikk…».
6. Gjenta samme kopiering til nytt outputområde: hendelsestallet øker, originalfilene og rapportene endres ikke. Arkivdeltilordning og kopitall skal ikke låne resultater fra andre arkivdeler.

**Ikke inkludert:** komplett kravbasert testregister på alle ni nivåer, tvungen automatisk XML-kobling, revisjon av eksterne kopier som er flyttet etter eksport, import av a6-historikk, og produksjonstest med faktiske millioner av kopierte filer.
