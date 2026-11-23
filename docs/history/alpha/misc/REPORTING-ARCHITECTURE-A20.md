# DWM – felles rapporttjeneste (v0.1.7-a20)

**Baseline:** `IKAMR/data-workflow-manager` `main` commit `b03cb2d354b445940ddcbbe0edeabf28af0664b9` (v0.1.7-a19).

## Formål

Bruk én rapporttjeneste for enkeltuttrekk, flere valgte jobber og fremtidige
kall fra Resultatvisninger, batch, CLI og depotportal. Jobblisten angir
utvalget, men er **ikke** rapportens autoritative evidenslager.

## Stabilt kallgrensesnitt

```python
from noark5_workflow.reporting.job_summary_a16 import ReportOptions
from noark5_workflow.reporting.report_service_a20 import export_selected_jobs

path = export_selected_jobs(
    report_directory,
    selected_jobs,
    ReportOptions('Full', (), True, True),
    prefix='1502_ephorte',
    formats=('html', 'pdf', 'json', 'csv'),
)
```

Utvalg kan inneholde én, seks, 28 eller et annet antall jobber. Samme API
kalles fra `gui/report_selected_dialog_a16.py` uten å starte analyser. Ingen
ekstern arbeidsmappe søkes rekursivt; kilde-/rapportoppdagelse er fortsatt
DWMs eksisterende jobbspesifikke logikk.

## Lagdeling

| Ansvar | Autoritativ implementasjon |
| --- | --- |
| Jobb / rapportoppslag | `job_summary_a16._latest_report` |
| Arkade, Siegfried/PRONOM, KDRS Query og valg | `external_report_a18`, `evidence_comparison_a18` |
| KDRS U2 og arkivdelknytning | `archive_u2_a18`, `archive_part_annex_a18` |
| Lagrede faglige perioder | `period_assessment_a16` |
| Periodeevidens fra DWM og KDRS | `period_report_a18` og `period_kdrs_evidence_a18` |
| Eksisterende rapportinnhold, årsdiagram og PDF | `report_package_a16` |
| **Felles a20 datamodell** | `report_model_a20` |
| **a20 HTML- og CSV-presentasjon** | `report_views_a20` |
| **Felles kall, eksport, staging og versjonsuavhengig GUI-rute** | `report_service_a20` |

Tjenesten gjenbruker a19-pakken i stedet for å duplisere XPath, KDRS-import,
Arkade-import, rapportvalgslogikk eller PDF-konvertering. Det etablerte JSON-
formatet `ikamr.noark5.selected_report.v1` beholdes; `a20_report_snapshot`
legges til som et nytt, avledet og eksplisitt navngitt felt.

## Betydning av status og måltall

- Manglende **DWM XPath-årsserie** er ikke det samme som manglende faglig
  vurderingsmulighet. Hele uttrekket kan vurderes manuelt på dokumentert
  KDRS Standard/U1-årsvolum, også for 1502_024.
- Lagret faglig godkjent periode vises bare når vurderingen er satt til
  `godkjent` og inneholder to gyldige år. `undersokes` vises separat.
- Vurdering av hver arkivdel bygger på arkivdelens **native `system_id`**,
  ikke U2-indeks eller en liknende tittel. Ingen U2-tall legges automatisk
  til DWM som om de var samme resultat.
- Eksisterende `report_count_overview` / `source_comparison` er fortsatt
  kilden til KDRS/DWM-valgte måltall i rapporten. a20-sammendragets tall er
  merket **DWM**, med eksplisitt antall jobber som mangler DWM-verdi.
- Faktisk `0` er verdi; `None`/manglende felt er ukjent. Manglende rapporter
  og delvis gjennomførte jobber skal fortsatt listes.
- En rapport er grunnlag for en **manuell depotfaglig beslutning**, ikke en
  automatisk GO for sletting av kildekontainer.

## Formater og filnavn

Samme kildedata brukes til:

- HTML: `index.html` og valgte vedlegg A–D. Hovedrapporten får korrigert
  faglig periodestatus; vedlegg B får en **kompakt én-rad-per-arkivdel-indeks**.
- PDF: genereres fra den endelige a20-HTML-en via a19s PDF-motor.
- JSON: eksisterende a19-struktur + `a20_report_snapshot`.
- CSV: semikolonseparert UTF-8 med BOM for Excel. Vedlegg B får én rad per
  arkivdel. Alle øvrige valgte rapportdeler får en jobbrad per uttrekk.

Eksport bygges i en midlertidig katalog. Kollisjon med eksisterende filer
kontrolleres **før** utdata produseres. PDF-feil stopper ikke HTML/JSON/CSV,
men rapporteres tydelig; en gammel PDF skal ikke forveksles med en ny.

## Kjente grenser i a20

- Sammenstilling på tvers av flere jobblister som bruker **samme JOB-nnn**
  blokkeres foreløpig. Den eldre U2-rapportmodellen benytter JOB-ID som
  koblingsnøkkel. Det er tryggere å stoppe enn å tilordne arkivdeldata feil;
  dette løses når permanent, global jobbidentitet gjennomføres.
- A20 endrer ikke selve periodevurderingsdialogens lagringsskjema eller
  behovet for å velge `Hele uttrekket` / `Arkivdel` og lagre eksplisitt.
- CSV har tabellarisk overblikk, **ikke** kopi av hver rå evidenslinje. JSON
  og vedlegg C/D bevarer detaljene.
- Felles tjeneste er koblet til *Rapport valgte*. Andre GUI-flater kan ta
  den i bruk uten egen ny implementasjon, men er ikke migrert i denne deltaen.

## Akseptansetester på Windows

1. Legg delta direkte over committet **a19**, ikke over den feilnavngitte
   `a18-fix12`. Bekreft at versjon vises som a20.
2. Kjør hele `test.bat`; kontroller både FAILED og ERRORS lik 0.
3. `1502_024`: åpne `Rapport valgte` → `Vurder ytterår` → `Hele uttrekket`.
   Bekreft at Standard/U1 årsvolum er tilgjengelig selv uten DWM XPath.
   Bevar 2005–2019 som *under undersøkelse* dersom ikke faglig godkjent.
4. Åpne minst to av 43 arkivdeler og kontroller at vurderinger lagres og
   hentes separat. Generer Full med alle vedlegg og HTML/PDF/JSON/CSV.
5. Kontroller én rad per arkivdel i kompakt vedlegg B og at DWM-tall,
   KDRS U2-observasjoner og verifiserte rapportverdier er separate.
6. Generer samlerapport for **1502_023–028** (6 jobber).
7. På IKAMR-K18: trekk/pull committet kode og rapporter **1502_029–056**
   (28 jobber, eksisterende `dwm/a01` der det gjelder).
8. Prøv den blandede jobblisten for **1535/1539/1543/1545/1547**. Manglende
   depotrapport skal vises, ikke føre til at jobben fjernes fra utvalget.

Ingen punkt i 3–8 skal automatisk utløse nye store XPath-/Arkade-kjøringer.

## a20.1 – Innholdsprofil fra eksisterende Noark 5-tester

**Baseline:** a20-deltaen er lagt på committet a19, og `test.bat` er godkjent
av brukeren med 2219 tester, 0 feil, 2 hoppet over. Dette er en videreføring
av a20 før commit; `version.py` forblir `0.1.7-a20`.

**Ny adapter:** `report_content_a201.py` kobles til `report_service_a20.py`
uten nye tunge analyser. Den leser bare resultatfiler som allerede er lagret
under denne jobbens kjente `noark5_tests/xpath/JOB-...__RUN-.../results`.
Kjøringens `index.json` må være `execution_profile=normal`.
Rapportens `evidence.source_xpath_run` avgjør primært hvilken kjørekatalog
som brukes. Etter diskflytting kan samme RUN-navn gjenfinnes under gjeldende
arbeidsrot, uten generell rekursiv skanning. Manglende kilder er **ukjent**,
ikke 0; U01/U02-regresjon brukes aldri som DWM-master.

**Innhold:** eksisterende C08/C13 (mapper, type/status), C14 (registreringstyper),
C15/C20 (journalposttype og status), C21/C23 (dokumenttype, tilknytning og
status), C24 (variantformat, registrert format) og F01–F13 (part, merknad,
kryssreferanse, avskrivning, korrespondanseparter, skjerming, kassasjon,
konvertering og sletting). Kildens verdi-/typekoder vises som observert;
`format_counts` er **ikke** PRONOM-resultat. KDRS Query og Arkade beholdes
separat; ikke semantisk verifiserte importerte kategorier blir ikke blandet inn.

**Fordeling i rapportene:**

- `Enkel`: uendret – hovedoversikt.
- `Medium` med **Hovedtall**: kompakte typefordelinger, særlig JP-type,
  mappetype, registreringstype og variantformat. Hovedrapporten viser en
  kildeavgrenset JP-aggregatfordeling med dekningsbrøk (`5/6 uttrekk` osv.).
- `Full` med **Hovedtall**: kildedekning og alle tilgjengelige kategorier.
  Hvis Vedlegg A ikke er valgt, kommer uttrekksdetaljene i hovedrapporten.
- `Vedlegg A – Uttrekk`: full kategoriliste per uttrekk når valgt, med
  test-ID og eksakte kildeverdier.
- `Vedlegg B – Arkivdeler`: egne type- og statusfordelinger koblet kun
  via native `system_id`. Full viser alle, Medium et kjerneutvalg.
- `JSON`: `a20_report_snapshot.jobs[].content_profile` bevarer hele
  strukturert kildegrunnlag med `data_role`, kildekjøring og test-ID.
- `CSV`: i tillegg til eksisterende CSV-er produseres `innholdsprofil.csv`
  når innholdsdata finnes og Hovedtall er med. Langformat med én rad per
  uttrekk/arkivdel/typeverdi, inkludert kildekjøring og test-ID. Ingen
  eksisterende CSV-kolonner eller rapportfilnavn er endret.
- `PDF`: genereres fra akkurat samme ferdige HTML som vises i nettleseren.

**Presiseringer:** Type-/statusfordelinger viser *hva kildetesten faktisk
gruppere*; en delsummert fordeling er ikke nødvendigvis identisk med et
hovedtall om verdier ikke er oppgitt. En journalposttype med kode I/U/N/X eller
fullt tekstnavn beholdes slik den er lagret. Dokumentbeskrivelser tilknyttet
som `Hoveddokument` er ikke det samme som antall journalposter med hoveddokument.

**Avgrensning:** For et uttrekk som bare har importert KDRS Query uten
DWM normal XPath, kan hoved- og evidenstall allerede være tilgjengelige
andre steder i rapporten. Denne a20.1-funksjonen **gjetter ikke** en
kategorifordeling fra dem. En senere utvidelse kan lese semantisk verifiserte
KDRS-kategorier, men må dokumentere kildetilhørighet og mapping individuelt.

**Windows-akseptanse:** Kjør `test.bat`. Test først ett uttrekk med fullført
normal DWM XPath, deretter samlerapport 1502_023–028, så 1502_029–056 og
blandet jobbliste. Kontroller JP-type per uttrekk og per arkivdel, deretter
CSV/JSON mot HTML/PDF. Test også 1502_024 uten DWM XPath; kategorier skal
da merkes manglende, men KDRS-hovedtall og periodeevidens beholdes.

## a20.2 – lesbarhet i store samlerapporter (2026-10-19)

**Status:** Presentasjonsendring som installeres over a20.1. `report_service_a20.py`
bruker `report_layout_a202.improve_report_html()` som **siste felles HTML-steg**
etter gjeldende a19/a20/a20.1-generatorer. Dette er ikke en ny evidensleser.

Felles tabellregler for alle fem rapportdelene:

- `JOB-001` osv. vises på **én linje**; jobbkolonnen får minst 88 px.
- Tabellen identifiseres på `Jobb`/`JOB` i første kolonne, ikke blindt på alle
  tabellers første kolonne. Headertekst for lange måltall kan gå over to linjer.
- Tabeller med minst åtte kolonner får sin **egen horisontale rulling** i HTML,
  slik at navn, system-ID og tall ikke klemmes sammen. Ingen data kuttes.
- Store arkivdellister i hovedrapportens jobboversikt kan ekspanderes; hele
  teksten blir værende i dokumentet og den strukturerte JSON/CSV-kilden.

**Vedlegg C:** Et uttrekksregister øverst og før kildematrisene; hvert jobbområde
har en tydelig uttrekksoverskrift som blir værende synlig ved rulling.
Arkade 5 sine 54 kontrollrader kan foldes ut, mens kontroll-ID og rapporterte
feil vises uten å åpne detaljene. KDRS Standard/U1/U2 kan foldes ut samlet.
U2-postene får identifikasjonen **kildearkivdelens nummer og tittel fra linje 1**,
uten at dette tolkes som DWM sin `system_id`. Ingen KDRS/U2-kobling er endret.

**Vedlegg D:** Detaljerte KDRS-kildetabeller med formatet `Datokilde / måltall`,
`År`, `Antall` får et **stolpediagram per metrikk**, separat for hver import og
Standard/U1-kilde. Tre sentrale metrikker vises direkte; andre årskategorier
kan ekspanderes. Hver opprinnelig tabell er bevart under «Vis opprinnelig
årsopptelling». Diagrammene plotter utelukkende eksisterende verdier; manglende
år får aldri verdien null. Endringslogg holdes utenfor arkivperiodegrunnlaget.
Den eksisterende PDF-konverteren leser de nye `.year-chart`-metadataene, men
printer fortsatt de fulle detaljtabellene. PDF-lesbarhet må kontrolleres separat.

Den eldre, snevre XPath-statusen `Kan ikke vurderes` korrigeres på Vedlegg D
bare når a20-modellen dokumenterer KDRS som tilgjengelig. Dette er en ren
**tekst-/visningsrettelse**: et lagret årsspenn uten status `godkjent` blir
fortsatt ikke faglig godkjent, og faglige vurderingsfiler blir ikke skrevet om.

**Tester:** `tests/test_a20_2_report_readability.py` + alle a20/a20.1
regresjonstester. Forhåndsvisning av de fem vedlagte rapportene er laget med
samme visningsadapter. Verken XPath-kjøring, KDRS-import eller gamle CSV/JSON
skjemaer er endret. Kjør full `test.bat` i Windows før commit.

## a20.3 – Robust rapporteksport ved frakoblet/ustabil disk (IKAMR-K18)

**Problemstilling:** Samlerapport for 28 uttrekk (1502_029–056) avbrøt med
`[Errno 22] Invalid argument` i GUI. Feilkoden alene dokumenterer **ikke**
frakoblet disk. Den kan også skyldes ugyldig/for lang filsti eller feil i
rapportfunksjonene. Rapportmotoren beholder derfor reell traceback i lokal logg
og forsøker ikke å tolke alle feilkoder som diskavbrudd.

**Ny felles tjeneste:** `noark5_workflow/reporting/report_recovery_a203.py`
bygger videre på eksisterende `report_service_a20.write_report_package` og
opptrer som en gjenbrukbar rapport-eksportkoordinator. Den kjører verken
XPath, Arkade 5 eller nye importer, og skriver aldri til kildemappene.

1. GUI kaller koordinatoren på en **bakgrunnstråd**; Tk-interaksjoner sendes
   på kø og håndteres av vinduets normale `after()`-sløyfe. Operatøren kan
   trykke **Stopp eksport**. Ved heng i operativsystemets egen fil-I/O kan
   stopp først gjennomføres når operativsystemet returnerer fra I/O-kallet.
2. Eksisterende rapportmotor lager hele HTML/JSON/PDF/CSV-rapportsettet i
   sesjonens lokale cache på klienten, under
   `%LOCALAPPDATA%\IKAMR\DWM\report_operations\cache-<session>\files`.
   JSON bygges internt til verifikasjon selv når operatøren bare velger HTML.
3. Før publisering sjekkes jobbantall, lokal jobb-ID, depotrapportgrunnlag og
   kilde-/arbeidsområdets tilgjengelighet. Hvis en tidligere lesbar rapport
   eller importmappe fremstår som manglende etter et diskbrudd, forsøkes
   rapportgenereringen på nytt. En kilde som faktisk mangler skal fortsatt
   kunne vises som `ikke tilgjengelig`, aldri automatisk `0`.
4. Ved registrert diskbrudd venter koordinatoren på at lagringsstedet kan
   nås ved to etterfølgende kontroller. Der Windows tilbyr volumserienummer,
   avvises en *annen* disk med samme stasjonsbokstav. Samme faktiske disk og
   filstier forutsettes ved gjenopptakelse.
5. Først når lokal rapport er komplett, publiseres filene til valgt mappe.
   Det brukes midlertidige filer og atomisk navnebytte per fil, deretter
   SHA-256-kontroll. Ved brudd på **måldisken** fortsetter kopieringen fra
   lokale ferdige filer. Allerede verifiserte filer kopieres ikke på nytt.
   Det er ikke et samlet atomisk katalogbytte: bruk rapporten først etter
   at eksportvinduet viser «ferdig».
6. Dersom **kildedisken** faller ut under den sentrale rapportgeneratoren,
   må *rapporten* bygges på nytt fra de **lagrede** resultatene etter
   gjenoppkobling. Det finnes ennå ikke per-jobb checkpoint inne i a19 sin
   monolittiske HTML-bygger, men ingen av de 28 XPath-/Arkade-jobbene kjøres om.
   Når lokal rapport er komplett, er kildedisken ikke lenger nødvendig for
   å kopiere resultatet til en frisk måldisk.
7. Ved `[Errno 22]` med *tilgjengelige* disker gjøres maksimalt ett ekstra
   bygge-/publiseringsforsøk. Deretter stoppes eksporten med lokal feillogg,
   i stedet for uendelig venting. Ved tydelig midlertidig diskfeil venter
   programmet videre til disken er tilbake eller operatøren velger Stopp.
8. Filkollisjoner i målmappen krever operatørens godkjenning. Godkjent
   overskriving skjer bare for filene denne rapportkjøringen produserer.
   Valgte rapportformater og grunnlagsdata endres ikke.

**Lokal hendelseslogg:**
`%LOCALAPPDATA%\IKAMR\DWM\report_operations\<session>.jsonl`
registrerer oppstart, forsøk, venting, gjenopptakelse, skriving, filnavn,
feil og full Python-traceback. Lokal cache slettes ved fullført eksport;
ved stopp/feil beholdes den for feilsøking og kan inneholde rapportdata som
skal behandles iht. depotets vanlige tilgangs- og sletterutiner. Slett ved
behov når testene er ferdig. Automatisk gjenoppretting *etter programrestart*
er ikke implementert; venting/gjenopptakelse skjer mens DWM kjører.

**Testforslag K18:** Velg først en **lokal** målmappe på C: for 28-jobbsrapporten.
La disken forbli tilkoblet hvis mulig. Dersom den faller ut, kontroller
«Venter på disk/arbeidsmappe» og koble tilbake samme disk på samme bokstav.
Når eksporten er ferdig, sammenlign utvalg/antall, og kontroller indeks og
vedlegg. Dersom `[Errno 22]` vedvarer, send lokal `.jsonl`-logg for analyse,
men ikke start store nye XPath-kjøringer kun for å teste rapporten.

**Avgrensning:** Denne første diskbrudd-beskyttelsen gjelder samlerapporter
og enkeltjobbrapporter fra rapportdialogen. DWM sin generelle operasjonsmotor,
Robocopy og inngest er ikke endret i a20.3.

## a20.4 – Rapportjobb fra eksisterende DWM-mapper

**Formål:** Dersom en `.n5jobs`-fil er borte, skal brukeren kunne lage en ny,
begrenset jobbliste som gjenbruker eksisterende depotrapport, uten ny XPath-
eller Arkade 5-kjøring. Ingen opprinnelige jobblister overskrives.

I `Jobbliste` finnes knappen **Gjenfinn DWM-jobber**. Velg en `dwm`-mappe,
vanligvis under `repository_operations/dwm`, eller en overordnet arbeidsmappe.
Gjenfinning utføres i bakgrunnstråd, med Avbryt. Programmet leter kun i det
forventede `noark5_reports/depot_validation/JOB-nnn__RUN-*/`-mønsteret. Et
lesbart `depot_validation_report.json` er nødvendig for å gjenfinne en jobb.

- Jobb-ID: bevares fra rapportmappen; omnummereres aldri.
- Uttrekksnavn: fra manifestets `source_extraction` når tilgjengelig, ellers
  tydelig angitt uverifisert rapportkilde.
- Work/operations: satt til **eksisterende og funnet DWM-mappe** fremfor gamle
  stasjonsbokstaver i manifestet. Den historiske kildeuttrekksstien aktiveres
  ikke, slik at rapporten kan leses uten å åpne store kildeuttrekk.
- Kjøretillatelser: workflow_ids er tomt. Jobblisten er kun for rapport og
  skal ikke behandles som et fullstendig kjøreoppsett.
- Flere uttrekk: kombineres bare dersom opprinnelige JOB-nnn er ulike.
  Motstridende uttrekksidentiteter/arbeidsrøtter for samme JOB-nnn avvises;
  bruk separate jobblister inntil global identitetsmodell er implementert.
- Gamle rapporter uten manifest: kan gjenfinnes når det finnes én entydig
  rapportkjøring for jobb-ID. Mer enn én uverifisert kjøring for samme JOB-ID
  avvises for å unngå kildeforveksling.
- En ny `.n5jobs` lagres gjennom standard `job_store.save_job_list`; valgt
  mål kan ikke ligge under den gjenfunne `dwm`-mappen, og kan ikke finnes fra før.

**Når depotrapport mangler:** Denne funksjonen kan ikke fremstille tidligere
ikke-lagrede rapportverdier. Dersom normal XPath-test og materialiserte views
finnes, kan en depotrapport bygges fra dem ved å kjøre rapportoperasjonen
(basert på lagrede verdier); det krever ingen ny XML/XPath-kjøring.

**Regresjonstest oppdatert:** `test_a18_fix6_single_job_report.py` validerer
`write_reconnectable_report` fra a20.3 (som kaller felles a20-tjeneste), ikke
lenger det eldre direktekallet til rapportskriveren.

### a20.5: strukturstyrt gjenfinning fra arkiv-noark5-roten

Gjenfinning av rapportjobber kan nå starte fra et overordnet arkivområde som
`G:\arkiv-noark5`. Søket følger kun kjente arkiv-/arbeidsmappetrinn:
`kommunenummer/FFKK_nnn.../repository_operations/dwm/(bXX)/noark5_reports/depot_validation`.
Det går aldri ned i `content`, `DOKUMENT`, XML-data, dokumentmapper eller
uavhengige analysekataloger. Søkedybde og antall kataloger er begrenset, og
GUI viser fremdrift mens lesingen skjer i bakgrunnstråd.

Planen har tre adskilte nivåer: (1) uttrekksmapper som finnes i rotområdet,
(2) jobber med lesbar `depot_validation_report.json`, og (3) uttrekk uten
DWM-depotrapport. Den viser også eksisterende `.n5jobs` og arkiverte
`*dwm*.zip` som spor, men ZIP-filene åpnes ikke og regnes ikke som
kontrollerte depotrapporter. Sikker kildetilordning og kollisjonsstopp for
listelokale `JOB-001` fra forskjellige arbeidsområder er uendret.

K18-testgrunnlaget (Robocopy-filoversikt 2026-10-19) inneholder 9 synlige
uttrekksmapper, 1 komplett DWM-depotrapport i `1535_005/.../dwm/b03`,
en eldre `.n5jobs` på samlingsnivå, samt flere ZIP-arkiver med eldre DWM-data.
Det er **ikke** evidens for 9 ferdige DWM-depotrapporter. Rapportgjenfinning
starter ingen nye XPath- eller Arkade-analyser og skriver ikke til uttrekkene.

### a20.6: deterministisk gjenfinningsdialog uten tidlig bekreftelse

Gjenfinningsdialogen i `gui/jobs_window_v017_a2.py` er justert etter Windows-test
på K18: Den gamle fremdriftsteksten ble stående mens en automatisk ja/nei-
bekreftelse åpnet seg med ferske resultater. Årsaken var at ferdigplanen
(`ok`-hendelsen) ikke ble lagt i statusfeltet før `messagebox.askyesno()`.

Søket og rapportdataene er uendret. UI har nå disse tilstandene: `searching`,
`ready`, `error` og `closed`. Bare `ready` tillater lagring. Bakgrunnstråden
legger både fremdrift og sluttresultat i en kø, og Tk-tråden tømmer køen før
sluttstatus settes. En eldre fremdriftshendelse kan ikke overskrive endelig
resultat. Beskrivelsen med antall jobber, manglende depotrapporter, eldre
jobblister og DWM-ZIP-filer presenteres i en scrollbar tekstboks i samme
vindu. Ingen automatisk ekstra modal bekreftelse åpnes når søket avsluttes.

Brukeren kan eksplisitt velge `Lagre ny jobbliste ...` når et vellykket søk
har funnet rapportjobber. Etter lagring aktiveres `Åpne lagret jobbliste`;
åpning av en ny aktiv liste krever egen bekreftelse. Tidlig lukking setter
avbruddshendelsen og forhindrer videre Tk-oppdateringer. Gjenbruk av knappen
mens dialogen er åpen aktiverer eksisterende dialog, og starter ikke et nytt
parallelt søk. Ingen kildefiler eller tidligere jobblister blir skrevet til.

Regresjonstest `test_a20_6_recovery_dialog_ui.py` tester faktiske hendelses-
og kontrollflyter mot lette CTk-testdobler uten grafisk Windows-sesjon:
gammel progresjon + rask fullføring, feil under søk, lagring ved eksplisitt
brukerklikk, åpning med bekreftelse, enkeltvindu og lukking under pågående
søk. Isolert: 27 a20.4-a20.6-tester bestått. Full `test.bat` på Windows
og faktisk GUI-visning gjenstår.

### a20.7: gjenfinn alle uttrekk som rapportjobber (K18)

**Hvorfor:** a20.4–a20.6 gjenopprettet bare jobbene som allerede hadde en fysisk
`depot_validation_report.json`. Søket på `G:\arkiv-noark5` fant derfor ni uttrekk,
men kunne bare lagre én jobb. Dette gjorde det umulig å lage en samlet
rapportoversikt for de øvrige uttrekkene uten å lage dem manuelt.

**Ny motor:** `report_job_discovery_a207.py` gjenbruker a20.5s avgrensede,
strukturstyrte søk. Den lager nå en **rapporteringskandidat for hver identifiserbar
uttrekksmappe** (`FFKK_nnn...`), uansett om depotrapport finnes. Følgende
kildegrunnlag registreres separat:

- normal DWM depotrapport (`noark5_reports/depot_validation`), beholdt med
  opprinnelig lokal JOB-ID der den er ledig;
- eksisterende DWM XPath-, view- eller external_evidence-mapper;
- eldre jobblister (`.n5jobs`) brukt kun som *identitetshjelp*, uten å hente inn
  workflow eller tilstand;
- eldre KDRS Query- og Arkade 5-resultater under `repository_operations`;
- DWM ZIP under både det aktuelle uttrekkets `repository_operations` og den
  historiske fellesmappen `<arkivrot>/_noark5`, koblet bare ved eksakt `FFKK_nnn`.

ZIP åpnes kun for å kontrollere om den inneholder en lesbar, begrenset DWM-
`depot_validation_report.json`. XML/SIP/DOKUMENT traverseres ikke, andre store
filer pakkes ikke ut. Hvis depotrapport finnes i ZIP, kopieres *kun den lagrede
JSON-rapporten* til en egen, ny rapportcache på den stabile disken som brukes
for ny jobbliste. Kildearkivet forblir uendret, og `recovery_source.json` i
cachen dokumenterer originalt arkiv, ZIP-medlem, original JOB-ID og SHA-256.
Flere originale JOB-ID-er i én ZIP gjør tilordningen tvetydig og avvises som
rapportgrunnlag. Dersom kildefilen endres etter forhåndsvisningen, avvises
caching; det opprettes ikke en misvisende rapport fra den endrede ZIP-filen.

En ny `.n5jobs` opprettes med **unik JOB-ID i den nye listen** og uten kjørbar
workflow. Rapport fra eksisterende DWM-kilde bruker opprinnelig JOB-ID der det
er mulig; kollisjoner mellom flere `JOB-001` løses ved å kopiere den ekstra
lagrede JSON-rapporten lokalt og navngi den med den *nye* unike jobb-ID-en.
Dette er eksplisitt dokumentert i `recovery_source.json`; ingen historisk
kilde eller jobbfil omskrives. En cache er en rapportkopi, **ikke** en ny
fullført DWM-kjøring. Nye `.n5jobs` kan aldri overskrive eksisterende fil,
og lagres utenfor skannet kildeområde.

**Rapportstatus:** Felles a20-rapporttjeneste viser en egen tabell
«Gjenfunne rapportjobber – kildegrunnlag» i HTML og feltet
`report_recovery_sources` i JSON. Manglende DWM-metrikker vises som
«ukjent/ikke tilgjengelig», aldri som 0. Eldre KDRS Query eller Arkade 5
blir ikke automatisk tellende masterdata. For slike uttrekk kan fullere
rapport først produseres når et relevant eksisterende DWM-resultat eller
utvalgt eksternt evidensgrunnlag er koblet til en gyldig rapport.

**K18-fixture:** ni uttrekksmapper (1535_003, 1535_005, 1539_007, 1543_010,
1543_012, 1545_005, 1547_003, 1547_005, 1547_007). Én aktiv DWM-depotrapport
for 1535_005, åtte uten aktiv depotrapport. Gjenfinning lager **ni jobber**,
merker datagrunnlag separat, og gjengir korrekte kildedata på rapportflaten.
Eldre ZIP under `_noark5` kan tilføre ekstra eksisterende depotrapporter *hvis*
ZIP-filen faktisk inneholder gyldig JSON; dette forutsettes ikke ut fra navn.

**Test:** Nye tester dekker ni uttrekk med og uten depotrapporter, gammel
`.n5jobs`, eldre ZIP i begge plasseringer, lokale JOB-ID-kollisjoner,
filendring under ZIP-gjenfinning, kildebevaring, ingen skanning i
`content` og visning av kildestatus i HTML/JSON. Isolert kjøring av hele
a20-testgruppen ga 95 tester, 0 feil og 3 repoavhengige hoppet over.
Full `test.bat` og Windows-GUI-test på K18 må gjennomføres før commit.

### a20.8: rapportjobb uten Work - operations (`Path(None)`)

**Feilen:** Ved rapport fra a20.7-gjenfunne K18-jobber mangler noen av
uttrekkene en DWM-arbeidsmappe. Jobblisten lagrer da `work_operations=null`.
Den eldre periodevurderingsleseren i a19 bruker `Path(job.work_operations)`
selv ved ren rapportlesing, noe som stopper både HTML- og JSON-rapporten med
`TypeError: ... not 'NoneType'`. Dette skjer særlig ved rapport på 1535_003
og 1539_007. At en rapport mangler er forventet, ikke en programfeil.

**Rettelse i felles rapporttjeneste:**
- `write_report_package` oppretter en *midlertidig, ikke-persistent lesekopi*
  av bare jobbobjekter som mangler Work - operations. Kopien peker til en
  ikke-opprettet, lokal sti under eksportens tempområde, slik at eldre
  `Path(...)`-baserte *lesere* ikke krasjer. Originale Job-objekter, `.n5jobs`
  og historiske kilder endres ikke. Denne kopien brukes ALDRI som grunnlag
  for lagring av vurderinger eller kjørbare operasjoner.
- De opprinnelige jobbene brukes fortsatt av a20.3s kilde- og diskovervåking.
- Manglende DWM-depotrapport får eksplisitt diagnostikk i alle JSON-vedlegg;
  en lokalt syntetisk lesesti må ikke presenteres som faktisk depotkilde.
- Innholdsprofilen og andre lesende tillegg bruker samme sikre jobbkontekst.
  Faktiske tall fra andre jobber beholdes; ukjente tall blir fortsatt null-verdi
  (`null`), ikke tallverdien 0.
- Eksisterende gjenfunnede `.n5jobs` fra a20.7 trenger IKKE rekonstrueres
  for å kunne lage rapport.

**For NYE gjenfunnede jobblister:** Når en jobb ikke har noen original
DWM-arbeidsmappe, legges et *fremtidig lokalt skriveområde* ved siden av
`.n5jobs` som `<jobblistenavn>.recovered-dwm/JOB-NNN`. Det opprettes ikke en
fiktiv depotrapport i denne mappen. Dette er kun et sted for depotets egne
senere metadata/vurderinger når nødvendig datagrunnlag er tilgjengelig.
Tidligere lagret `.n5jobs` får ikke denne nye banen automatisk; for å bruke
lokal vedvarende vurderingslagring må jobblisten gjenfinnes og lagres med et
nytt filnavn. Ingen kildedisk eller eldre rapport blir endret.

**Test:** 100 a20-relaterte tester, 0 feil, 3 hoppet over i isolert miljø.
Testene simulerer to 1535-jobber med én manglende arbeidsmappe, ni K18-jobber
med syv depotrapporter og to med ukjent grunnlag, samt fremtidig lokal
arbeidsbane. Full Windows `test.bat` gjenstår.
