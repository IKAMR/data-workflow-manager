# DWM – Analyse, innsyn og dataarkitektur: status, historikk og veivalg

**Status:** Arkitektur- og beslutningsgrunnlag – ikke en vedtatt migrering eller implementasjonsordre  
**Oppdatert:** 2026-11-25  
**Kodegrunnlag:** `IKAMR/data-workflow-manager`, gren `dev-0.2.7-alpha`, gjennomgått mot `v0.2.7-a12`  
**Målgruppe:** DWM-utvikling, teknisk forvaltning, test og depotfaglig videreutvikling  
**Plassering:** `docs/architecture/ANALYSE-INNSYN-OG-DATAARKITEKTUR-VEIVALG.md`

> Dette dokumentet bevarer vurderingene og kildegrunnlaget for et framtidig utviklingsvalg. Faktisk kode og tester er fasit for implementert atferd. Alle nye løsninger skal avklares før implementering. DWM skal ikke skrive til originalt Noark 5-Source eller erstatte kontrollbevis med en uverifisert søkeindeks.

## 1. Sammendrag og anbefalt retning

Data Workflow Manager (DWM) har utviklet seg fra en hovedsakelig kontroll- og arbeidsflytapplikasjon til et mer generelt verktøy for **analyse, depotfaglig vurdering og utforskning av Noark 5-uttrekk**. Resultatvisninger, navigasjon i faktiske XML-objekter og en kontrollorientert dokument-/PUID-visning utgjør allerede deler av et framtidig innsynsgrunnlag. Globalt, brukervennlig søk i hele uttrekket er imidlertid **ikke ferdig implementert**.

**Anbefalt retning:**

1. Bevar én jobb-/workflowmodell og ett kildesporbart Work-grunnlag på tvers av Enkel, Avansert og Legacy GUI. Unngå separate og konkurrerende analysemotorer per visning.
2. Bruk **SQLite som standard for store eller søkbare objekt- og dokumentregistre**, også for små uttrekk, fremfor å lage en egen JSON-søkemotor for små og SQLite for store uttrekk. DWM bruker allerede SQLite på sentrale områder.
3. Behold **JSON, JSONL, manifeste, kontrollresultater og rå evidens** som dokumenterbare, portable og sporbare artefakter. SQLite skal i hovedsak være en verifiserbar, gjenoppbyggbar lesemodell/indeks – ikke eneste bevarte kopi av tekniske bevis.
4. Standardiser objektidentitet, kilde- og jobbtilknytning, indeksversjon, kontrollsummer og søke-/pagineringstjenester før større GUI-utvidelser.
5. Behandle *Analyse*, *Kontroll*, *Innsyn/utforskning* og *Depotvurdering* som forskjellige brukerformål over felles, etterprøvbare data.
6. Prioriter dokumentasjonsvedlikehold og ytelsesmålinger før databasekonsolidering eller globalt søk.

**Ikke vedtatt:** Én felles fysisk SQLite-database, FTS5 som obligatorisk søkemotor, automatisk migrering av gamle Work-data, fulltekstsøk i dokumentbinærer, sentral serverdatabase og innsynspublisering. Dette må spesifiseres og testes senere.

## 2. Kilder og hvordan status er vurdert

### 2.1 Gjennomgåtte eksisterende dokumenter

- [`../../README.md`](../../README.md), [`../README.md`](../README.md)
- [`../ARCHITECTURE.md`](../ARCHITECTURE.md), [`../CODE-MAP.md`](../CODE-MAP.md), [`../INTERFACE.md`](../INTERFACE.md)
- [`../DEVELOPMENT.md`](../DEVELOPMENT.md), [`../REPOSITORY-STRUCTURE.md`](../REPOSITORY-STRUCTURE.md), [`../RUNTIME-ENVIRONMENTS.md`](../RUNTIME-ENVIRONMENTS.md)
- [`../NOARK5-ANALYSIS-MODEL.md`](../NOARK5-ANALYSIS-MODEL.md)
- [`../NOARK5-CANONICAL-RESULTS-AND-KNOWLEDGE-ROADMAP.md`](../NOARK5-CANONICAL-RESULTS-AND-KNOWLEDGE-ROADMAP.md)
- [`../gui/GUI-ARCHITECTURE-V020.md`](../gui/GUI-ARCHITECTURE-V020.md)
- [`../quality/NOARK5-OBJEKTNAVIGASJON.md`](../quality/NOARK5-OBJEKTNAVIGASJON.md)
- [`../quality/NOARK5-KONTROLLNIVAER-OG-FILFORMATER.md`](../quality/NOARK5-KONTROLLNIVAER-OG-FILFORMATER.md)
- [`../quality/NOARK5-PUID-OVERSIKT-KOPIHISTORIKK.md`](../quality/NOARK5-PUID-OVERSIKT-KOPIHISTORIKK.md)
- [`../storage/WORK-OUTPUT-LAYOUT.md`](../storage/WORK-OUTPUT-LAYOUT.md)
- [`../reference/noark5/NOARK5_JOB_DISCOVERY.md`](../reference/noark5/NOARK5_JOB_DISCOVERY.md)
- [`../RELEASES.md`](../RELEASES.md)

### 2.2 Kode kontrollert i a12-grenen

| Område | Relevante implementasjoner |
| --- | --- |
| Analyse: resultat- og fagflater | `app/analysis_workspace_v027_a2.py`, `app/analysis_workspace_v027_a3.py`, `gui_qt/analysis_workspace_v027_a2.py`–`a4.py` |
| XML-objekter og objektindeks | `app/noark_object_browser_v027_a5.py`, `gui_qt/noark_object_browser_v027_a5.py` |
| Dokumentfiler, PRONOM og kopiering | `app/noark5_document_workbench_v027_a6.py`, `gui_qt/noark5_document_workbench_v027_a6.py` |
| PUID-grupper, kopihistorikk | `app/noark5_format_overview_v027_a7.py`, `gui_qt/noark5_format_overview_v027_a7.py`–`a9.py` |
| Rekursiv flerjobboppdagelse | `app/noark5_batch_discovery_v027_a11.py`, `gui_qt/batch_discovery_v027_a11.py` |
| Siegfried-publisering | `noark5_workflow/operations/siegfried_publish_v027_a10.py` |
| U1 samlet opptelling | `noark5_workflow/analysis/u1_total.py`, `noark5_workflow/analysis/u1_stream_v027_a12.py`, `noark5_workflow/operations/analyse_noark5_u1.py` |
| Historisk A170 og definisjonsanalyse | `noark5_workflow/analysis/legacy_a170_stream.py`, `noark5_workflow/analysis/definition_engine.py` |

**Avgrensning:** Dette er en målrettet kilde- og dokumentasjonsgjennomgang, ikke linjevis revisjon av alle moduler eller alle Markdown-filer. En oppført modul beviser at en implementasjon finnes; det garanterer ikke at alle GUI-scenarier eller svært store nettverksuttak er praktisk verifisert. Status må bekreftes med aktuelle tester og operatørtest.

## 3. Historikk: relevante arkitekturvalg

### 3.1 Fra Legacy GUI til delt arbeidsflyt

Den eldre, CustomTkinter-baserte GUI-linjen er fortsatt tilgjengelig og har nyttige arbeidsmåter, særlig flere samtidige vinduer på store skjermer. Den nyere PySide6-baserte linjen tilbyr Startside, Enkel modus, Avansert modus, Analyse, Setup, Resultatvisninger og flere depotrettede arbeidsflater. Faglig funksjonalitet og data må ikke erklæres foreldet bare fordi GUI-teknologien er eldre.

Arkitekturen etablerer en delt jobb-/workflow-/executor-kjerne, også brukt av CLI. Dette er viktigere enn valg av GUI-teknologi: samme `.n5jobs`, jobber, Work, logger og kjørestatus må gjelde uansett presentasjon. Legacy GUI kan bevares for kompatibilitet og spesialiserte arbeidsmåter uten at vi lager en ny parallell modell.

**Terminologisk skille:** `Legacy GUI` er det eldre grensesnittet. `A170/A180 (Legacy)` er historiske analyse-/regresjonsoperasjoner; dette er ikke det samme.

### 3.2 Fra resultatsammendrag til faktiske Noark 5-objekter

- **Analyse a2–a4:** Hovedvindu med arkivdel-/årsprofiler, delresultater, filtre, detaljer og kilde-/Work-bundne kommentarer. Hovedvinduet er en orienterings- og analyseflate, ikke et fullstendig objektregister.
- **Objektnavigasjon a5:** Leser faktiske Noark 5-objekter fra valgt `arkivstruktur.xml`, etablerer SQLite-indeks, knytter objektene til en observerbar foreldre-/barn-struktur og tilbyr sidevis navigasjon og kommentarer. Status om hvilke objektnivåer som kan vises komplett, følger [`../quality/NOARK5-OBJEKTNAVIGASJON.md`](../quality/NOARK5-OBJEKTNAVIGASJON.md).
- **Kontrollorientert a6–a9:** Direkte valg mellom Noark-nivåer, operativ dokumentfil-/PUID-visning, utvalg, filformatvurdering, kopiering og kopihistorikk. **Mange nivåer over dokumentfilnivå er fortsatt navigasjonsskall**, ikke fullstendige implementasjoner av alle Noark 5-kontroller eller objektvisninger.

Disse tre Analyse-inngangene kompletterer hverandre. De må dokumenteres som forskjellige brukerformål over identitets- og evidensbundne data, ikke som tre separate sannhetskilder.

### 3.3 Store uttrekk og strømming

Tidligere A170-analyse ble tilpasset strømmende parsing for store XML-strukturer. I a12 ble også A180/U1 flyttet fra `etree.parse()` av hele XML-treet til en `lxml.iterparse()`-basert analyse med begrenset minnebruk. Den gamle `noark5_workflow/analysis/u1_total.py` finnes som referanse/legacy-implementasjon; operasjonen `analyse_noark5_u1.py` kaller nå `u1_stream_v027_a12.py`.

Siegfried-kjøring mot uttrekket `1502_024` viste behov for sikker publisering av flere millioner resultatrader etter en Windows-feil ved mappeomdøping. a10 introduserte flere omdøpingsforsøk og en verifisert kopibasert reservevei der original `.partial` beholdes og manifestet publiseres til slutt.

**Observerte fakta per 2026-11-25:** JOB-001 hadde fullført A140 og A170; i a12 ble jobben gjenopptatt fra deljobb 7/17, og A180 startet strømmende U1-opptelling. Endelig resultat av langkjøringen var ennå ikke dokumentert i denne gjennomgangen. Ikke merk a12 som praktisk godkjent på 2 TB-testgrunnlaget uten fullført logg og kontroll av resultatet.

### 3.4 Batchoppdagelse og lagringsvalg a11

Ny a11-funksjon søker rekursivt etter Noark 5-kandidater under én hovedmappe, utelater blant annet dokumentpayload og Work-/evidensområder, foreslår én Work-plassering per kilde og kan koble en entydig `info.xml` fra gitte plasseringer. Kandidater gjennomgås før jobbopprettelse. Dette bruker ordinær jobbliste/Workbench API, ikke en egen batchmotor.

Et generelt prinsipp er at *oppdagelse ikke er kjøring*: kildeidentifikasjon, Work-planlegging, jobbgodkjenning og faktisk kjøring er separate handlinger. `info.xml`-tilordning må ikke gjøres med omtrentlige navn eller første tilfeldige treff. Kildemapper og metadata må forbli uendret.

## 4. Dagens lagring: fakta og praktiske konsekvenser

| Datatype | Dagens hovedmønster | Anbefalt framtidig rolle |
| --- | --- | --- |
| Originalt Noark 5-uttrekk | XML, skjemaer, `DOKUMENT`-filer | Read-only Source; aldri import av dokumentbinærer i indeks som standard |
| Jobb, jobbliste, oppsett | `.n5jobs`, Work-metadata/JSON, Setup | Behold etablerte kontrakter inntil eventuell eksplisitt migreringsplan |
| Rå Siegfried-evidens | `file_inventory.jsonl`, `siegfried_files.jsonl`, kontrollsummer og manifest | Bevar som verifiserbar, portabel original evidens |
| A5 objektregister | Versjonert SQLite + JSON-manifest | Videreutvikle som kildebundet objektindeks |
| A6 dokument-/formatregister | Versjonert SQLite bygd fra verifisert JSONL | Videreutvikle til paginert dokumentindeks |
| A7 kopihistorikk | SQLite, eksportmanifest/JSONL | Behold transaksjonell historikk og egen proveniens |
| Samlede analyser og rapporter | JSON, JSONL, genererte rapporter | Bevar rapport-/evidenskontrakter; vurder SQL-projeksjoner for svært store detaljlister |
| Faglige vurderinger | Work-bundne historiserte registreringer | Hold beslutning og teknisk funn atskilt |

**Viktig:** SQLite er allerede i produksjonskode. Problemstillingen er derfor ikke «skal DWM begynne å bruke SQLite?», men «hvilke lesetjenester, identiteter og indekser skal standardiseres?».

### 4.1 Konkret skaleringsobservasjon fra kode

- A5 `objects` har blant annet interne ID-er, foreldrekobling, kildemetadata og søkestreng. Objektleseren har `LIMIT/OFFSET` og `instr(search_blob, ?)`, som er en enkel løsning, men ikke nødvendigvis effektiv ved dyp paginering/globalt fritekstsøk.
- A6 `files` lagrer filidentitet, PUID, arkivdel- og dokumentreferanser og søkestreng. Den leser JSONL sekvensielt og bygger en indeks; enkelte spørringer bruker `instr()` og `LIMIT/OFFSET`.
- A7 har nøkkelbasert sidebytte (`id`-basert) for dypt dokumentoppslag og separate transaksjonelle tabeller for eksporter og kopierte filer. Dette er et mønster som kan gjenbrukes ved globalt søk.
- Analyse-hovedflaten leser rapport-/sammendrags-JSON. Dette kan være hensiktsmessig for avgrensede oppsummeringer, men bør ikke utvikles til å laste millioner av detaljerader inn i minnet.
- Flere visninger kan bygge relaterte indekser over samme uttrekk. Før fysisk sammenslåing må vi kartlegge dupliserte data, byggetid og de ulike evidens-/revisjonskontraktene.

### 4.2 Størrelse: 2 TB er ikke én parameter

Det er antall XML-elementer, antall dokumentfiler, relasjonsgrad, søkeindekser og I/O-mønster som bestemmer belastningen, ikke alene antall TB i Source. Uttrekket `1502_024` hadde omtrent 3,44 millioner dokumentfiler. Et fullstendig dokumentregister på dette nivået skal ikke materialiseres som en Python-liste eller en full Qt-tabell; les bare etterspurt side, gruppe eller aggregat.

## 5. Veivalg: SQLite kombinert med JSON/JSONL

**Foreslått arkitektur, ennå ikke vedtatt:**

```text
Noark 5 Source (read-only)
  |-- arkivstruktur.xml / øvrig XML
  |-- DOKUMENT/...  (dokumentinnhold forblir utenfor databasen)
  |
  +--> strømmet lesing, integritet og kildeidentitet
            |
            +--> rå JSON/JSONL, manifeste og kontrollbevis i Work
            |
            +--> versjonert, verifisert SQLite-leseindeks
                       |-- Noark-objekter / foreldre / barn
                       |-- dokumentreferanser / filidentitet / PUID
                       |-- kilde- og jobbidentitet / indekstilstand
                       +-- indekserte søke- og sidevisningstjenester
                                  |
                                  +--> Analyse
                                  +--> Kontroll
                                  +--> Innsyn/utforskning
                                  +--> Depotvurdering (egne beslutninger)
```

Prinsippet er **én logisk evidenskilde, flere avledede lesemodeller**. En SQLite-indeks kan bygges på nytt dersom den mangler eller dens identitet/verifikasjon feiler; den får ikke autoritet over original Source eller bevarte kontrollresultater.

### 5.1 Hvorfor ikke «SQLite i stedet for all JSON»?

JSON/JSONL fungerer godt til strømmede resultater, portabel utveksling, lesbare manifeste, langtidssporbarhet og kjøre-/testbevis. SQLite gir derimot transaksjoner, relasjoner, B-tree-indekser og raske deluttrekk. Å erstatte all JSON med SQLite vil svekke eksisterende formater og kreve en risikabel migrering uten å løse alle ytelsesproblemer. **Kombinasjonen er derfor et bevisst arkitekturvalg.**

### 5.2 Plattform og lagringsplassering

SQLite støttes på Windows, Linux og macOS og kan brukes fra Python uten ekstern databaseserver. DWM sin dokumenterte støttede baseline er likevel Windows desktop; andre plattformer skal ikke omtales som praktisk verifisert uten test.

**Nettverksfilsystem:** SQLite WAL er ikke egnet som delt, skrivbar database mellom klienter via nettverksfilsystem. For tunge indekser bør vi vurdere en lokal cache med eksplisitt binding til Work-kilden og robust gjenoppbygging. Varig evidens kan fortsatt ligge under jobbens Work. Dette krever eget design for autoritet, tilgang, cacheinvalidering, ledig diskplass og bruk av ulike klienter.

**Ikke vedtatt:** Å flytte alle eksisterende Work-SQLite-filer til lokal disk eller å erstatte Work sin nåværende verifiserbare struktur. Dette må måles og besluttes separat.

### 5.3 Søkestrategi

- Først indeksbaserte eksakte/nære oppslag på `systemID`, native sak-/registrerings-ID, dokumentreferanse, arkivdel, feltnavn og daterte metadata.
- Så dokumentert filtrering, sortering, keyset-paginering og navigasjon i foreldre-/barn-relasjoner.
- Undersøk SQLite **FTS5** for metadata-/tittelsøk (indekskostnad, tegnnormalisering, norske tegn, relevans, søkestruktur og bygge-/oppdateringstid).
- Globalt søk må aldri koble objekter fra ulike jobber eller ulike kilde-SHA-er. Dupliserte/manglende `systemID` håndteres som tvetydig identitet, ikke automatisk unik nøkkel.
- Søk inni PDF-er og andre dokumentbinærer er **et annet prosjekt**; krever uttrekks-/formatstrategi og eget tilgangs-/personvernregime.
- Brukerens uttrykk «søk virker ikke enda» forstås her som at *fullstendig globalt innsynssøk* ennå mangler. Koden har begrensede lokale tekst-/filtreff; disse er ikke det samme som et fungerende søk på tvers av hele uttrekket.

## 6. Funksjonsområder og GUI – ønsket felles begrepsbruk

| Område | Primært brukerformål | Viktig skille |
| --- | --- | --- |
| Enkel modus | Veiledet oppsett, kontrollkjøring, fortsettelse, Analyse | Skal håndtere samme jobbliste som Avansert modus |
| Avansert modus | Jobblister, deljobber, rekkefølge, kontrollstatus, arbeidsflater, logger | Må ikke etablere egen jobb-/resultattilstand |
| Legacy GUI | Eldre arbeidsflater og fler-vindusarbeid, kompatibilitet | Bevares og dokumenteres som egen GUI-teknologi, ikke særskilt datamodell |
| Analyse – hovedvindu | Oversikt, arkivdeler, årsprofiler, rapportert resultat, faglige kommentarer | Aggregerte og kildeavledede resultater er ikke et komplett objektregister |
| Analyse – objektvisning | Navigere observerte XML-objekter og metadata | Bare dokumenterte objekter, entydig kilde- og jobbidentitet |
| Analyse – Noark-kontroller/PUID | Direkte nivåvalg, dokumentfilregister, filformat, kopiering | Ikke alle nivåene er fullstendige Noark-kontroller |
| Innsyn/utforskning – senere | Globalt oppslag i objekter, metadata, dokumentreferanser | Ikke det samme som offentlig publisering av dokumentinnhold |
| Depotvurdering | Faglige beslutninger og avklaringer | Kontroll-OK betyr aldri automatisk depotgodkjenning |

### 6.1 Bevar fungerende Legacy

Dokumenter hvordan Legacy GUI startes, hvilke vinduer og oppgaver som fortsatt er nyttige, hva som er testet, og hvilke feil/ustabile UI-forhold som finnes. Ikke fjern det på grunnlag av alder alene. Et eventuelt framtidig GUI-samlingsprosjekt skal være et eksplisitt brukerbesluttet arbeid.

### 6.2 Ikke tre analysemotorer

De tre Analyse-arbeidsflatene bør kunne bruke felles lesetjenester/indeksreferanser. Det er ikke nødvendigvis riktig å slå alle vinduene sammen i ett stort GUI. **Felles data- og objektkontrakter er viktigere enn lik visuell layout.**

## 7. Sikkerhet, proveniens og migrering

Før en felles indeks-/søkearkitektur implementeres, må følgende krav besluttes:

1. **Jobbidentitet:** Stabil `job_uid`, valgt Source, kilde-SHA/manifest og indeksgenerasjon; aldri koble på bare `JOB-001`.
2. **Kildeintegritet:** Bind objektregister til dokumentert Source/Work. Vis når indeks er lagret projeksjon og Source ikke er tilgjengelig eller ikke verifisert på nytt.
3. **Indeksens livssyklus:** Bygg i midlertidig område, valider fullstendighet og signatur, publiser atomisk eller med kontrollert reserveprosedyre; behold tidligere gyldig indeks ved feil/avbrudd.
4. **Skjemaversjon:** Egen `schema_version` og eksplisitt kompatibilitet for indekslesere. Ikke tolk enhver gammel SQLite-fil som gyldig ny modell.
5. **Oppgraderinger:** Ingen destruktiv migrering av eldre jobblister/Work, og ingen skjult bulk-reindeksering ved oppstart. Gi brukerinitiert og avbrytbar gjenoppbygging.
6. **Feil og utfall:** Disk fullt, Windows fil-lock, frakoblet nettverksstasjon, ugyldig XML, manglende dokumentreferanse, ufullstendig råresultat, duplisert native-ID og databasekorrupthet skal gi tydelig status – ikke «0 treff» eller «OK».
7. **Sikkerhet/personvern:** Kildedata kan inneholde personopplysninger og skjermingsbehov. Lokal søkeindeks og cache må få lagrings-, tilgangs-, slettings- og eventuelt krypteringspolicy før indekser med sensitive metadata opprettes i nye brukerområder.
8. **Historikk:** Opprinnelig teknisk evidens, manuelle vurderinger og senere reindekseringer er forskjellige hendelser; ingen stilltiende overskriving av faglige vurderinger.

## 8. Dokumentasjonsrevisjon: hva som bør oppdateres

Gjeldende dokumentasjon er omfattende, men enkelte dokumenter beskriver eldre trinn som om de fortsatt var siste tilstand. Nye alpha-trinn skal oppdatere *kanoniske* dokumenter, ikke skape en `README-Axx.md` i reporoten eller ett nytt historikkdokument for hver kodeleveranse. Se [`../REPOSITORY-STRUCTURE.md`](../REPOSITORY-STRUCTURE.md).

| Prioritet | Dokument | Endringsbehov |
| --- | --- | --- |
| Høy | `docs/ARCHITECTURE.md` | Gjør skillet evidens/JSONL/SQLite-indekser og innsynsretning tydelig |
| Høy | `docs/CODE-MAP.md` | Fra gammel plan om rekursiv oppdagelse til implementert a11; vis a5–a12-dataflyt |
| Høy | `docs/NOARK5-ANALYSIS-MODEL.md` | Beskriv Analyse/Kontroll/Innsyn og gjenbruk av faktiske objekter |
| Høy | `docs/quality/NOARK5-OBJEKTNAVIGASJON.md` | Oppdater status etter a5 og krysshenvis til a6–a9, uten å overdrive objektdekning |
| Høy | `docs/quality/NOARK5-PUID-OVERSIKT-KOPIHISTORIKK.md` | Synkroniser a8/a9, faktiske filtre, kopihistorikk og begrensninger |
| Høy | `docs/reference/noark5/NOARK5_JOB_DISCOVERY.md` | Beskriv a11-rekursivt mappefunn ved siden av tidligere Robocopy-import |
| Høy | `docs/storage/WORK-OUTPUT-LAYOUT.md` | Felles `dwm`-mappe, a11-suffiks og hvordan kollisjoner unngås |
| Høy | `docs/gui/GUI-ARCHITECTURE-V020.md` | Faktisk Enkel/Avansert/Legacy, og tre Analyse-innganger |
| Middels | `docs/RUNTIME-ENVIRONMENTS.md` | Lokal SQLite-cache, nettverksrestriksjoner og fortsatt Windows-baseline |
| Middels | `docs/README.md`, `README.md` | Synlig navigasjon til nye autoritative arkitektur-/Analyse-dokumenter |
| Middels | `docs/TESTING.md` | Langkjøringer, minne, nettverk, store indekser og dataintegritet |
| Middels | `docs/NOARK5-CANONICAL-RESULTS-AND-KNOWLEDGE-ROADMAP.md` | Skille mellom opprinnelig målplan og senere faktisk kodestatus |

**Dette dokumentet erstatter ikke** ovennevnte kanoniske kontrakter. Det beskriver analyse, avveiing og et foreslått vedlikeholdsarbeid. De aktuelle kanoniske dokumentene oppdateres når arbeidstrinnene prioriteres.

## 9. Foreslåtte beslutningsporter og implementeringstrinn

### Trinn D0 – dokumentasjon (kan startes uten databaseendring)

- Oppdater eksisterende kanoniske dokumenter etter tabellen over.
- Etabler en vedlikeholdt funksjonsmatrise mellom GUI-linjene og Analyse-arbeidsflatene.
- Dokumenter faktisk status og begrensninger for a10, a11, a12 – **ikke** påstå at langkjøring a12 er bestått uten sluttlogg.
- Kontroller lenker, Markdown-layout og eksisterende dokumentasjonstester.
- Beslutningsport: Dokumentasjonen er konsistent med testet implementasjon.

### Trinn D1 – måling før endring

- Kartlegg databasene A5, A6 og A7: tabeller, fremmednøkler, identiteter, manifest, byggetid, størrelse og overlapp.
- Mål 10 000, 100 000, 1 million og 3+ millioner objekter/filoppføringer; både lokal SSD og representativ Work-/Source-lagring på nettverk når praktisk mulig.
- Mål minnebruk, indeksbygging, fritekstsøk, eksakt oppslag, dyp side, kald/varm gjenåpning, ledig disk og avbrutt bygg.
- Beslutningsport: Problemene er målt; det er klart hva som skal forbedres uten full migrering.

### Trinn D2 – felles *logisk* indekskontrakt

- Definer stabile objektreferanser og `index_manifest` (jobb, Source, kilde-SHA, datamodell/skjemaversjon, gyldighet og byggestatus).
- Definer et lite, GUI-uavhengig Python-lesegrensesnitt for `get_object`, `children_page`, `search_objects`, `get_document`, `files_page` og aggregater; navnene er forslag, ikke API-vedtak.
- Avklar om A5, A6 og A7 forblir separate databaser med ett adapterlag, eller om noe bør konsolideres fysisk. **Ikke slå sammen før nytte og migreringskostnad er dokumentert.**
- Beslutningsport: Datakontrakt og bakoverkompatibilitet er testet.

### Trinn D3 – metadata- og objektsøk

- Begynn med eksakte identitetsoppslag og indeksbasert navigasjon; deretter filter, sortering og keyset-paginering.
- Prototype FTS5 i en separat søkeprojeksjon om nødvendig; sammenlign mot B-tree-indekser/enkle søk.
- Vis scope, kildeidentitet, antall treff og om data kommer fra aktuell kilde eller en bevart Work-projeksjon.
- Beslutningsport: Fungerer på millioner av rader uten å laste full treffliste i minnet.

### Trinn D4 – integrert innsynsflate

- Gjenbruk eksisterende Analyse-objektnavigasjon og dokumentreferanser.
- Skille objektsøk, tekniske kontrollfunn og faglige merknader i GUI.
- La brukeren gå fra treff til arkiv/arkivdel/sak/registrering/dokumentreferanse med dokumentert relasjon.
- Ikke innfør automatisk offentlig visning, tilgang til skjermede dokumenter eller fulltekstsøk i binærfiler uten separat avklaring.
- Beslutningsport: Brukerakseptanse på reelle uttrekk og tydelige begrensninger.

### Trinn D5 – eventuell bredere lagringsreform

Vurder først her om jobbstatus, utvalgte materialiserte analyser eller flere objektindekser skal bruke en felles SQLite-basert lagringstjeneste. Bevar eksisterende Work-kontrakter, migrer aldri destruktivt, og tillat kontrollert tilbakerulling. En framtidig flerbrukertjeneste kan kreve egen serverdatabase; dette er utenfor dagens beslutning.

## 10. Sjekkliste før implementering avtales

- [ ] Er brukerformålet **innsyn**, **kontroll**, **analyse** eller **faglig vurdering** definert?
- [ ] Er faktisk kilde- og Work-identitet kjent, og er manglende/tvetydig kobling håndtert?
- [ ] Vet vi hvilken indeks/datamodell som er autoritativ for *oppslag*, og hvilken evidens som er autoritativ for *kontrollbevis*?
- [ ] Kan løsningen håndtere millioner av objekter med avgrenset RAM og paginert GUI?
- [ ] Er nettverksstasjon, lokal cache, avbrutt jobb og disk-fullt testet?
- [ ] Finnes schema-/indeksversjoner, regresjonstester og en gjenoppbyggingsvei?
- [ ] Er JSON/JSONL og eksisterende Work-data bakoverkompatible?
- [ ] Er faglige kommentarer og depotbeslutninger holdt atskilt fra tekniske funn?
- [ ] Har relevante kanoniske `.md`-filer blitt oppdatert, uten nye løse aNN-notater?
- [ ] Er GUI-støtte og faktisk teststatus dokumentert uten å blande mål og implementasjon?

## 11. Beslutningslogg (oppdateres når beslutninger tas)

| Dato | Tema | Foreløpig anbefaling | Beslutning |
| --- | --- | --- | --- |
| 2026-11-25 | SQL kontra JSON | SQLite til søkbare indekser; JSON/JSONL bevares som evidens/utveksling | **Åpen** |
| 2026-11-25 | Ett eller flere SQLite-filer | Behold eksisterende A5/A6/A7 til vi har målte krav til eventuell sammenslåing | **Åpen** |
| 2026-11-25 | Globalt Noark 5-søk | Bygg på verifiserte indeks-/objektkontrakter, med eksakte oppslag først | **Åpen** |
| 2026-11-25 | Legacy GUI | Dokumenter og bevar; ingen avvikling uten eget vedtak | **Åpen** |
| 2026-11-25 | Dokumentasjon | Oppdater kanoniske filer, bevar historikk, ingen løse README-Axx | Eksisterende repo-policy; praktisk vedlikehold **ikke utført** |

## 12. Bruk av dokumentet i neste utviklingsrunde

Før ny implementasjon innen Analyse, søk, SQLite, filformat-/dokumentvisning eller innsyn:

1. Les dette dokumentet sammen med `docs/ARCHITECTURE.md`, `docs/CODE-MAP.md`, `docs/DEVELOPMENT.md`, `docs/NOARK5-ANALYSIS-MODEL.md` og relevante `docs/quality/`-dokumenter.
2. Sjekk **gjeldende branch og kode**; dokumentet er et datert bilde av a12, ikke en garanti for senere versjoner.
3. Oppdater status og beslutningsloggen etter avklaring av omfang, ikke ved å anta at forslag er vedtatt.
4. Lever kode, tester, synkroniserte `version.py`/`pyproject.toml` og nødvendige endringer i *kanonisk dokumentasjon* i samme delta.
5. Kjør relevante målrettede tester, `test.bat`, dokumentasjonskontroll og praktisk Windows-/uttrekkstest før commit. Brukeren eier commit og push.

**GitHub Wiki:** Kan bruke dette og øvrige `docs/` som teknisk kilde, men er et separat, brukerrettet presentasjonslag. Wiki skal ikke være eneste lagringssted for arkitekturvedtak eller tekniske kontrakter.
