# DWM – resultatvisning, avviksbehandling og depotprosess: implementasjonskart

**Kartlegging:** 24. november 2026  
**Kodegrunnlag:** `IKAMR/data-workflow-manager`, `main` ved commit `03342788e627c8d9a09cb35c4538c709cd3c519c` (**v0.2.6**)  
**Status:** Kodegjennomgang og grunnlag for videre produktutvikling; **ikke** en godkjent funksjons- eller depotfaglig spesifikasjon.  
**Plassering i repo:** `docs/quality/RESULTATVISNING-AVVIK-OG-DEPOTPROSESS-KODEKART.md`

## 1. Formål, metode og sikkerhet for konklusjoner

Dette dokumentet kartlegger hva Data Workflow Manager (DWM) faktisk har av kode for å gå fra *kjørt kontroll* til *forstått funn*, *dokumentert avvik*, *faglig vurdering* og *rapportgrunnlag for depot*. Det viser også hvor sammenhengen brytes i dagens brukergrensesnitt.

Undersøkelsen omfatter en systematisk oversikt over GitHub-repositoriet, den aktive Qt-oppstartskjeden, sentrale Work-, resultat- og evidenslesere, KS-/vurderingsfunksjoner, rapportbyggerne, relevante historiske GUI-er og utvalgte regresjonstester. Repositoriet inneholder 2 294 oppføringer i Git-treet, inkludert 1 692 Python-filer, hvorav 832 ligger under `tests/`. Mange filer er historiske inkrementer. **Det er ikke det samme som at alle 1 692 Python-filer er gjennomlest linje for linje.** Kodeveiene som er relevante for denne kartleggingen er gjennomgått i dybden og knyttet til konkrete filer og funksjoner.

Kartleggingen er en **statisk kodeanalyse**, ikke en gjennomført operatørtest på reelle uttrekk. Vi har ikke åpnet faktiske Work-mapper fra 1547-uttakene, utført Qt-GUI på Windows eller kjørt `test.bat` i denne undersøkelsen. Den versjonerte testrapporten i repoet for `v0.2.6` rapporterer **4 775 kjørt / 4 741 bestått / 0 feil / 34 hoppet over** (`docs/test-results/v0.2.6.md`). Tallene dokumenterer siste rapporterte testkjøring, ikke praktisk godkjenning av depotflyten.

**Markeringer brukt nedenfor:**

- **Implementert, aktivt koblet:** konkret funksjon og koblingspunkt er funnet i standard Qt-kjeden.
- **Implementert i annen flyt:** funksjonen finnes og har et API eller eldre grensesnitt, men er ikke dokumentert som integrert i den aktuelle standard-Qt-flyten.
- **Delvis/avgrenset:** deler virker, men dekning, navigasjon, skalering eller sammenstilling har kjente grenser.
- **Ikke påvist:** vi har ikke funnet dokumentasjon på at funksjonen er ferdig integrert; dette er ikke bevis for at ingen beslektet kode eksisterer.

**Viktig skille:** *Teknisk teststatus*, *evidensens tilstedeværelse og integritet*, *avviksgrad*, *faglig vurdering*, *depotets beslutning*, *periodevurdering* og *rapportutkast* er ulike størrelser. DWM forsøker gjennomgående å holde dem atskilt. Et teknisk fullført arbeidsløp er aldri i seg selv en faglig godkjenning.

## 2. Hovedkonklusjon

DWM har allerede et omfattende teknisk grunnlag for depotfaglig arbeid: selvstendige kontrollkilder, kanonisk evidens, kildeverifiserte enkeltfunn, sidevis håndtering av store funnregistre, brukerbundne og historiserte vurderingshendelser, manuelle observasjoner, hel-uttak- og arkivdelvurdering, periodevurdering, sjekklister og rapportutkast med komplette registre.

**Det største produktmessige gapet er sammenhengen mellom disse funksjonene i arbeidsflaten**, ikke fraværet av grunnleggende datamodeller. Brukeren kan gå inn via Resultatvisninger, Depotvurdering, Avvik/KS/godkjenning, Veiledet KS, XPath-katalog og rapportbygger – men får ikke én gjennomgående, arbeidsorientert fremdrift fra funn til konklusjon.

Særlig vesentlige forhold:

1. **To KS-grensesnitt med ulik skaleringsmodell.** Den direkte «Avvik / KS / godkjenning»-dialogen bygger en tabell fra et materialisert snapshot, mens «Veiledet KS» bruker en komplett SQLite-basert sideindeks. Begge benytter i prinsippet samme vurderingsregister, men gir ulik navigasjon og rapportløp.
2. **Vanlige Resultatvisninger har lavere filgrenser enn nye KS-lesere.** Den vanlige oversiktsleseren begrenser depot-JSON til 12 MB og vanlige evidens-JSON til 16 MB. Nyere QA-moduler har strømmelesing og sidevis tilgang. Et stort Work kan dermed ha gyldig data som ikke dukker fullstendig opp i de tradisjonelle fanene.
3. **Vurdering er ikke én samlet status.** Det finnes særskilte journaler for vurdering av enkeltfunn, manuelle avvik, hele uttrekk, arkivdeler, perioder, sjekklister og – i eldre løsninger – annotasjoner og vurderingsområder. Modeller og hensikt er forskjellige, og ingen samlet saksbehandlingsoversikt er påvist.
4. **Arbeidsflyten avsluttes med rapport*utkast*.** Det finnes komplette eksportløp for KS- og depotrapport, men ingen automatisk formell godkjenning. En eventuell formell beslutningsprosess må defineres særskilt.
5. **Faglig gjennomgang under pågående validering er begrenset.** Den aktive åpningen av Veiledet KS blokkerer når en jobb kjører. Read-only resultatvisning og varig vurdering av stabilt kildegrunnlag bør derfor skilles eksplisitt i neste design.

## 3. Faktisk kjørekjede: hvilket GUI er aktivt?

Standard Qt-start er: `start.bat` / `python -m gui_qt` → `gui_qt/__main__.py:main()` → den siste klassen `gui_qt/main_v025_a3.py:DwmMainWindow`. Denne **arver tidligere Qt-inkrementer**, helt tilbake til `gui_qt/main_window.py`. Den er ikke en separat app fra de eldre modulene.

### 3.1 Resultatvisninger

`gui_qt/main_window.py:_a12_open_result_center()` oppretter konkret `gui_qt/result_center_v0110_a4.py:ResultCenterWindow`. Arverekken er:

```text
ResultCenterWindow (result_center_v0110_a4.py)
  └─ ResultCenterWindow (result_center_v019_a1.py)
       └─ ResultCenterWindow (result_center_v018_a13.py)
            └─ Qt-dialog med opprinnelige resultattabeller og Work-lesing
```

`gui_qt/main_v020_a6.py:_a12_open_result_center()` installerer deretter støttefunksjoner i dette vinduet:

- `gui_qt/result_navigation_v020_a6.py` – fire kortere navigasjonsgrupper.
- `gui_qt/noark5_xpath_audit_v021_a1.py` – egen XPath-/KDRS-katalog og kilde-/kjørekontroll.
- `gui_qt/qa_workflow_v022_a3.py` – inngang til avvik, kommentarer og rapportutkast i Depotvurdering.
- `gui_qt/checklist_v021_a15.py` – depotets manuelle sjekklister.

`gui_qt/result_center_v0110_a4.py` legger videre til valg av datert filformatpolicy og lesbar PRONOM-presentasjon. Historisk RAF-klassifisering skal ikke fremstilles som gjeldende bevaringsregel.

### 3.2 Innganger til kvalitetssikring

**Inngang A – «Avvik / KS / godkjenning…»:**

`gui_qt/main_v020_a6.py:_a3_install_qa_shortcuts()` legger handlingen i Rapport-menyen i Avansert og en knapp i Enkel oversikt. `gui_qt/qa_workflow_v022_a3.py:open_active_job_qa()` åpner Resultatvisninger på Depotvurdering og starter `QaFindingReviewDialogV022A3` for aktiv jobb. Denne arver `gui_qt/qa_review_v021_a13.py:QaFindingReviewDialog`, og bruker `noark5_workflow/reporting/qa_workflow_v022_a3.py:build_review_snapshot_v022_a3()`.

**Inngang B – «Veiledet KS»:**

`gui_qt/main_v023_a4.py:_a12_open_ks_workshop()` åpner `gui_qt/ks_paged_v023_a12.py:KsWorkshopDialog`, videreutviklet fra `ks_guided_v023_a4.py`, `ks_value_inspection_v023_a3.py`, `ks_inspector_v023_a1.py` og `ks_workshop_v022_a12.py`. Dette er den nyere, **sidevise** arbeidsflaten med funninspeksjon, kildekontekst, vurderingshistorikk og komplett rapporteksport. Åpning er sperret mens jobben kjører.

**Betydning:** «Avvik / KS / godkjenning» og «Veiledet KS» er ikke bare to navn på ett vindu. De er forskjellige presentasjons- og eksportløp over nært beslektet Work-evidens og samme append-only vurderingsregister. Dette er det viktigste stedet for funksjonell konsolidering.

### 3.3 Eldre CustomTkinter-GUI

`main.py` og `gui/persistent_app_*.py` representerer et fortsatt eksisterende eldre GUI. Det inneholder blant annet `gui/depot_result_views.py`, `gui/depot_assessment_dialog.py`, `gui/result_history_dialog.py` og `gui/result_versions_dialog.py`. Eldre API-er og enkelte visninger lever videre, men de skal **ikke automatisk beskrives som brukervennlig tilgjengelige i det nåværende Qt-vinduet**. Vi må skille «kode finnes» fra «dagens operatør finner funksjonen».

## 4. Resultatvisninger: implementerte sider og datagrunnlag

Fanene er samlet i fire navigasjonsgrupper gjennom `app/result_tabs_v020_a6.py` og `gui_qt/result_navigation_v020_a6.py`. Underliggende faner beholdes og er programmatisk tilgjengelige.

| Gruppe | Fane | Konkret datagrunnlag og funksjon | Operatørhandling / avgrensning |
|---|---|---|---|
| **Oversikt** | Oversikt | Work-depotrapport, oppsummerte volum, teknisk status og rapportert vurderingsstatus | Velg flere uttrekk; ikke en fullstendig avviks-/vedtakskø |
| **Oversikt** | Arkivdeler | `archive_parts` fra depotrapport, `system_id`, volum, periodeevidens | Les detalj per arkivdel, men detalj i ordinær fane er ikke en komplett KS-forekomstinspeksjon |
| **Oversikt** | Årsfordeling | Arkivdels- og uttrekksbaserte årsserier fra lagret depot-/KDRS-grunnlag | Tabell, diagram og CSV; manglende serie er *ukjent*, ikke null |
| **Oversikt** | Tekniske kontroller | Lagrede DWM-testresultater i depotrapporten | Test-ID, Noark-punkt, status, antall/avvik og detaljer; teknisk teststatus, ikke depotvedtak |
| **Eksterne kontroller** | Arkade 5 | Importerte normaliserte Arkade-resultater | Test, kilde, import-ID, status; normal JSON-leser har størrelsesgrense |
| **Eksterne kontroller** | PRONOM | Importert Arkade-statistikk og valgt formatregelprofil | PUID, format, antall, historisk RAF og separat datert vurdering; ingen automatisk bevaringsgodkjenning |
| **Eksterne kontroller** | KDRS Query | Importmanifester, rapporter og kildehenvisninger | Kilde-/SHA-visning, filtrering på Standard/U1/U2, valg av evidens |
| **Eksterne kontroller** | Arkade-dekning | Dokumentert kobling mellom Arkade-tester og DWM-testkandidater | Søk/filter; ingen automatisk påstand om at testene er normative ekvivalenter |
| **Rapporter og evidens** | Depotrapporter | Lagrede rapportfiler fra Work | Åpne rapport; rapport eksisterer ikke lik faglig godkjenning |
| **Rapporter og evidens** | Evidensfiler | Kjent filinventar i Work | Filsti, størrelse og kildeåpning; avgrenset inventar, ikke fullstendig traversal |
| **Rapporter og evidens** | Kildeoversikt | Samlet oversikt over kildesystem, import, status, telling og SHA | Søk/filter og eksport CSV/HTML/JSON |
| **Faglig vurdering** | Periodevurdering | Uttrekks- og arkivdelsvurderinger, årstall og observasjoner | Vurder periode via lagret jobb/Work; dette er en separat faglig vurdering |
| **Faglig vurdering** | Depotvurdering | Hele uttrekket og arkivdeler, teknisk/periodisk/faglig status og kildegrunnlag | Søk, filtrer, vurder, se historikk, åpne rapport, sjekkliste og avviksdialog |

**Nøkkelfiler:** `gui_qt/result_center_v018_a13.py`, `gui_qt/result_center_v019_a1.py`, `gui_qt/result_center_v0110_a4.py`, `gui_qt/result_navigation_v020_a6.py`, `app/result_evidence_v018_a13.py`, `app/evidence_workbench_v019_a1.py`.

### 4.1 Skalering og lesbarhet – en reell forskjell mellom visningene

| Implementasjon | Dokumentert kodegrense | Konsekvens |
|---|---|---|
| `app/result_center_v018_a12.py:discover_results` | `MAX_ITEMS=700`, `MAX_PER_GROUP=250`, depotrapport som JSON `MAX_REPORT_BYTES=12_000_000` | Ordinær filoversikt kan bli avkortet; stor rapport blir ikke innlest som gyldig oversiktsmodell |
| `app/result_evidence_v018_a13.py:safe_json` | `MAX_EVIDENCE_BYTES=16_000_000` | Store normaliserte Arkade-resultater kan utebli fra den ordinære Arkade-fanen selv om de ligger i Work |
| `app/result_evidence_v018_a13.py:_arkade_manifests` | Maks 250 importmapper undersøkes; KDRS-rader bruker tilsvarende øvre grenser | Tradisjonelle tabeller er ikke en komplett historisk importoversikt ved høyere antall |
| `app/depot_review_v019_a2.py:_original_report` | `MAX_REPORT_BYTES=16_000_000` | Direkte depotvurdering av for stor originalrapport kan blokkeres |
| `noark5_workflow/reporting/qa_paged_v023_a8.py` | Full kildekontroll til SQLite; presentasjonsforhåndsvisning 250, sidegrense 1 000 | Store Arkade-kilder kan gjennomgås uten å legge alle forekomster i GUI-minne |
| `noark5_workflow/reporting/qa_paged_review_v023_a12.py` | Full kildebundet indeks; Qt bruker 100 rader per side, API maks 250 | Sidevis, søkbar gjennomgang av alle verifiserte funn; ingen avkortet indeks publiseres |
| `noark5_workflow/reporting/qa_a260_v023_a6.py` | Fullstendig JSONL/CSV; HTML-forhåndsvisning 250 | Forhåndsvisningens grense gir ikke tap i det komplette funnregisteret |

Dette er **ikke** ensbetydende med at kildeevidensen er tapt. Men det er et brukerproblem når én fane viser «ingen» eller manglende data, mens et annet vindu kan finne dataene. Neste design bør samle dem på den komplette, kildebundne sidenormalen og vise tydelig «ikke lest/for stor/ukjent» når datagrunnlag ikke kan åpnes.

## 5. Prosesseringskjeden som produserer grunnlaget

`app/workflow_dependencies_v022_a7.py` definerer **stabile operasjonsnummer**. Nummer er identifikator, ikke nødvendigvis deljobbnummer i en hvilken som helst valgt profil.

| Operasjon | Oppgave | Betydning for senere depotbehandling |
|---|---|---|
| A100 | Metadata-inventar | Kilde-/uttakskontekst |
| A110 | XML/XSD-validering | Teknisk skjemaresultat |
| A120 | Arkivstruktur | Arkiv- og arkivdelgrunnlag |
| A130 | DWM XPath-tester | Intern teknisk testmaster |
| A140 | Direkte Siegfried/PRONOM | Selvstendig filidentifikasjon |
| A150 | Arkade 5 Noark 5-test | Ekstern Noark-kontrollkilde |
| A160 | Arkade 5 PRONOM-analyse | Ekstern filformatkilde |
| A170 | DWM Noark 5-kjerneanalyse | Intern analyse |
| A180 | DWM U1-analyse | Intern utvidet analyse |
| A190 | XPath-regresjon | Kontroll av testutvikling/resultat |
| A200 | Arkade-import | Eksterne rapporter normaliseres i Work |
| A210 | Kanonisk Noark-evidens | Kildebundet intern master og eksterne referanser |
| A220 | Koble ekstern evidens | Analyse av valgte Arkade-/Siegfried-kilder |
| A230 | Evidensdekning | Identitet, hash, manglende kildefamilier, teknisk dekning |
| A240 | Analysevisninger | Avledede oversiktsmodeller |
| A250 | Depotvalideringsrapport | Lagret samlet teknisk/faglig grunnlag |
| A260 | KS-grunnlag/utkast | Komplett kildebundet funnregister og rapportgrunnlag |
| A900 | DIAS-pakking | Valgfritt pakkesteg; ikke det samme som depotvedtak |

A210/A230 i `noark5_workflow/operations/canonical_evidence_v026_a3.py` retter fra v0.2.6 enkelte tilfeller der verifisert Arkade PRONOM-evidens finnes i en annen import i samme jobb/Work. A230 kan ved entydig kildetreff oppdatere **avledede** A210/A220-indekser og beholde historikken. Manglende eller feilaktig kildekobling skal fortsatt være et reelt avvik. Det kan ikke brukes som en generell «ignorer A230»-funksjon.

`noark5_workflow/reporting/qa_control_coverage_v023_a18.py` kontrollerer faktisk opptalt status fra separate DWM-/Arkade-kilder. Resultatet er ikke en påstand om full normativ kravdekning.

**Avgrensning:** En jobb kan være ferdig teknisk, uten alle faglige vurderinger. En kilde kan være importert uten at alle individfunn er verifisert. En rapport kan være generert uten depotets vedtak.

## 6. Work som kildesystem og de ulike datalagene

`app/work_persistence_v018_a10.py` og `noark5_workflow/core/work_job_store.py` legger autoritativ jobbdefinisjon, tilstand og hendelser i **Work**; `.n5jobs` er en indeks. Resultatvisning og KS skal ikke skrive tilbake til originale Source-filer.

| Datatype | Eksempel i Work | Funksjon / endringsregel |
|---|---|---|
| Jobbidentitet/plan | `job.json` | Vedvarende jobb-UID, kilde, arbeidsflyt |
| Tilstand/hendelser | `job-state.json`, `job-events.jsonl` | Fremdrift, avbrudd og fortsettelse |
| Operasjonshistorikk | `run_history/operations.jsonl` | Teknisk kjøring, eget proveniensspor |
| Råresultater | `wf/results/raw-results.jsonl` | Resultat-ID og kilde per operasjon |
| XPath/master | `noark5_tests/xpath/<run>/master-results.json` | Intern kontrollresultatkilde |
| Arkade/Siegfried | `external_evidence/arkade5/...`, `external_evidence/siegfried/...` | Ulike eksterne resultater og importmanifest |
| Kanonisk evidens | `noark5_evidence/canonical-results.json` | Avledet kildebundet indeks, **ikke** eneste originale evidenskilde |
| Ekstern sammenstilling | `noark5_evidence/canonical-external-analysis.json` | Avledet kildebundet analyse |
| Evidensrevisjon | `noark5_evidence/evidence-audit.json` | Dokumenterer tilgjengelige og manglende kilder |
| Depotrapport | `noark5_reports/depot_validation/<run>/depot_validation_report.json` | Grunnlag for flere vurderings- og rapportvisninger |
| A260 funnregister | `noark5_evidence/a260_exports_v023_a6/<run>/funn.jsonl`, `funn.csv`, `manifest.json` | Alle individfunn; rapportforhåndsvisning er bevisst avgrenset |
| Arkade sideindeks | `noark5_evidence/qa_index_v023_a8/*.sqlite` | Avledet og gjenbyggbar, ikke autoritativ originalkilde |
| KS sideindeks | `noark5_evidence/qa_review_index_v023_a12/*.sqlite` | Avledet komplett funnindeks bundet til kildehash |
| Vurderte funn | `noark5_evidence/qa_review_events_v021_a13/<uuid>.json` | **Append-only** faghendelse med bruker, kildeversjon og SHA |
| Manuelle avvik | `noark5_evidence/qa_manual_findings_v022_a3/<uuid>.json` | **Append-only** menneskelig observasjon, ikke maskinell test |
| Manuell sjekkliste | `noark5_evidence/depot_checklist_events_v021_a15/...` | Kildebundet Ja/Nei/Ikke relevant |
| Heluttak-vurdering | `depot_assessment.json` ved original depotrapport | Historisert status, begrunnelse og bruker; bevarer teknisk originalrapport |
| Arkivdelvurdering | `depot_assessment_parts.json` ved depotrapport | Historisert per **entydig native system-ID**, samme rapportversjon |
| Periodevurdering | `noark5_reports/period_assessments/<job_id>.json` | Separat vurdering per uttrekk/arkivdel |
| Eldre annotasjoner | `depot_annotations.json` ved depotrapport | Tilgjengelig i eldre GUI/API; ikke dokumentert som samlet inn i dagens Qt-KS |
| Eldre områdevis vurdering | `depot_review_status.json` ved depotrapport | Period/content/documents/formats-status i separat API; Qt-kobling ikke avklart |

Dette er **flere forskjellige hendelses- og beslutningsregistre**, ikke én database med én universell status. Deres identitets- og historikkontrakter må bevares ved en eventuell felles brukerflate.

### 6.1 Viktige identitetsregler

1. Knyt Work-snapshot til `job_uid`, ikke bare lokalt `JOB-001`-nummer.
2. Knyt faglige funn til faktisk `finding_key` og **SHA-256 for original depotrapport**; tidligere hendelser ved endret kilderevisjon beholdes, men skal ikke uten videre tolkes som vurdering av nytt funn.
3. Knyt arkivdelvurdering til opprinnelig `system_id`, ikke visningsrad, tittel eller KDRS U2-indeks.
4. Behold DWM XPath, Arkade Noark, Arkade PRONOM, Siegfried, XSD og KDRS som **separate** kilder, med eksplisitt mapping når en sammenligning faktisk er dokumentert.
5. Manuelle avvik har menneskelig opprinnelse og skal aldri telles som maskinell Noark-validering.
6. Skille mellom kilde-/reporthash, vurderingshendelse og avledet visningsindeks; en ugyldig cache er ikke i seg selv et ugyldig arkivuttrekk.

## 7. Funn, avvik og faglig vurdering – det som er implementert

### 7.1 Maskinelle funn og klassifisering

- `noark5_workflow/reporting/qa_workflow_v022_a3.py:build_review_snapshot_v022_a3()` samler registrerte funn, inkludert ordinært Work uten optional kanonisk projeksjon; henter også manuelle funn, DWM-status og relevante RAF-kandidater.
- `noark5_workflow/reporting/qa_delivery_v023_a11.py` kobler komplette individuelle DWM-avleveringsfunn fra kildebundet JSONL til KS. Ufullstendige registre kan ikke presenteres som komplette.
- `noark5_workflow/reporting/qa_paged_v023_a8.py` og `qa_paged_review_v023_a12.py` legger kildebundne Arkade-/DWM-funn i SQLite for sidevis gjennomgang.
- Alvorlighetsnivåene er **ERROR, WARNING, REVIEW, NOTE, INFORMATION**. Disse er ikke automatisk «feil som krever ny avlevering»; faglig betydning bestemmes separat.
- `app/ks_inspector_v023_a1.py`, `app/ks_xml_evidence_v023_a19.py` kan vise lagret Arkade-forekomst, XML-fil og rapportert linje, og undersøke konkret original-XML *read-only* når stien og grunnlaget er verifiserbart. Rapportert linjenummer er et **ankerpåstand**, ikke bevis for at Source-filen aldri er endret.
- `app/ks_metadata_v023_a2.py` og `app/ks_value_inspection_v023_a3.py` kan knytte XML-navn, registrerte metadata og avleveringsbetingelser mot **valgt** Noark-versjon (3.1/4.0/5.0). Et tekst-/feltmatch alene er ikke en godkjent normativ regel.

### 7.2 Vurdering av enkeltfunn – eksisterende fagjournal

`noark5_workflow/reporting/qa_review_v021_a13.py:record_review()` lagrer en **ny, uforanderlig JSON-hendelse** per vurdering. Den lagrer brukerprofil, tidspunkt, funnidentitet, depotrapportens kildehash, fagstatus, kommentar og om kommentaren skal inngå i KS- eller depotrapport. Den tekniske kildeposten endres ikke.

Følgende fagstatus er kodet i `STATUSES`:

| Lagret kode | Synlig betydning |
|---|---|
| `requires_clarification` | Krever avklaring |
| `context_documented` | Kontekst dokumentert |
| `acceptable_deviation` | Akseptabelt avvik – faglig merknad, **ikke** godkjenning |
| `not_relevant` | Ikke relevant – begrunnet |

**Egenskaper:** kommentar er påkrevd (maks 5 000 tegn), registrert brukerprofil kreves, tidligere hendelser beholdes. Nyeste gyldige hendelse for rett jobb/rapport/funn vises. `with_selected_reviews()` tar kun eksplisitt valgte fagkommentarer med i rapportgrunnlaget. Statusen gir ikke maskinell PASS og ikke formelt vedtak.

**Ved store uttrekk:** `noark5_workflow/reporting/qa_paged_review_v023_a12.py:save_review_for_page()` lagrer via **det samme a13-registeret**, etter å ha kontrollert at funnet faktisk finnes i den komplette, verifiserte indeksen. Dette er en viktig eksisterende konsistensegenskap som bør beholdes.

### 7.3 Manuelle observasjoner

`noark5_workflow/reporting/qa_workflow_v022_a3.py:record_manual_finding()` registrerer menneskelig dokumentert funn med alvorlighetsnivå, beskrivelse, kontekst, eventuell kildehenvisning og bruker. Hendelsen er append-only og SHA-kontrollert, og knyttes til den eksakte Work-/rapportversjonen. 

Denne kan opprettes i både den eldre avviksdialogen og KS-arbeidsflaten (`gui_qt/qa_workflow_v022_a3.py`, `gui_qt/ks_workshop_v022_a12.py`). En merknad til en arkivdel er **en manuell KS-observasjon**, ikke automatisk en endret teknisk arkivdelstatus.

### 7.4 Veiledet KS – ferdig teknikk, men egen arbeidsflate

Dagens `gui_qt/ks_paged_v023_a12.py:KsWorkshopDialog` støtter:

- Fullstendig sideindeksert funnregister, vanlige sider på 100 rader; «Forrige side», «Neste side» og hopp til sidenummer.
- Filter på kontrollkilde, alvorlighetsnivå, vurdert/ikke vurdert og tekst (inkludert kildereferanser).
- «Feil først» eller «Alle funn» og veiledet «Forrige/Neste» funn.
- Kildebundet Arkade-forekomstoversikt med arkivdel, XML-fil, linje og objektsystem-ID.
- XML-kontekst og utvidet inspeksjon; metadata/M-nummer og valgt Noark-versjonsreferanse.
- Lagre status/kommentar, velge rapportmottaker, «Lagre og neste».
- «Alle tester», «Arkivdeler», «Kilder og evidens», «Rapportutkast».
- Lagring av faglig *innstilling* og komplett rapporteksport, uten å gjøre innstillingen til vedtak.

Dette er en god teknisk kjerne for videreutviklingen. Funksjonen er ikke ennå samlet med all depotvurdering og øvrig rapportnavigasjon i én gjennomgående arbeidsflate.

### 7.5 Depotvurdering av hele uttrekk og hver arkivdel

`gui_qt/depot_review_v019_a2.py:DepotReviewPanel` er aktivt inne i Resultatvisninger. Den viser uttrekk som foreldre og arkivdeler som barn, med separate kolonner for **faglig depotstatus**, **teknisk status**, **periodevurdering**, **vurderingspunkter** og sist vurdert. Det finnes søk, filter for vurdert/ikke vurdert/manglende grunnlag, stor detaljvisning, brukerprofil, vurderingsdialog og kildeåpning.

- **Hele uttrekket:** `noark5_workflow/analysis/depot_assessment.py:record_depot_assessment()` lagrer `depot_assessment.json` ved originalrapporten, med begrunnelse, bruker og historikk; kan materialisere separat vurdert JSON/HTML, men originalrapporten endres ikke.
- **En arkivdel:** `app/depot_review_v019_a2.py:record_part_decision()` lagrer `depot_assessment_parts.json`, bundet til rapportens SHA og entydig native `system_id`, med egen historikk.

Tillatte fagstatus for disse vurderingene er `accepted`, `accepted_with_deviation`, `requires_clarification` og `new_extraction_required` – **andre verdier enn enkeltfunnets KS-status**. Valget er en eksplisitt menneskelig vurdering og krever begrunnelse og identitet.

Viktig: Overordnede avvik fra hele uttrekket flyttes ikke automatisk til hver arkivdel. Eksterne kildetellinger vises som kilder på uttrekksnivå. Manglende/duplisert `system_id` gjør arkivdelvurderingen skrivebeskyttet.

### 7.6 Periodevurdering, sjekkliste og øvrige annotasjoner

- `noark5_workflow/reporting/period_assessment_a16.py` tilbyr manuell periodevurdering for hele uttrekk og per arkivdel, separat fra opprinnelige årstallsobservasjoner. Qt Resultatvisninger har egen fane og dialog (`gui_qt/result_center_v018_a13.py`). KDRS Standard/U1/U2 er selvstendige periodiske evidenskilder.
- `noark5_workflow/reporting/qa_checklist_v021_a15.py` implementerer kildebundet sjekkliste med `yes` / `no` / `not_applicable`, egne vurderingshendelser, og METS-henvisninger. `gui_qt/checklist_v021_a15.py` legger «Sjekkliste / METS…» inn i Depotvurdering. Dette er utkast-/kontrollstøtte, ikke normativ garanti.
- `noark5_workflow/analysis/depot_annotations.py` har API for note, deviation, question, follow_up og accepted_deviation, med active/resolved/closed og rapportbinding. Koblet til eldre `gui/depot_result_views.py`. **Samlet eksponering i dagens Qt-KS er ikke påvist.**
- `noark5_workflow/analysis/depot_review_status.py` har en egen statusmatrise for period/content/documents/formats og approved/rejected/pending. Det er en teknisk implementasjon, men **ikke verifisert som felles statusmodell i dagens Qt-vurdering**.

Det er derfor feil å legge alle disse statusene i én enkel «Godkjent»-kolonne uten å bevare kontekst, omfang og kilde.

## 8. Rapportering: minst tre eksisterende løp

| Løp | Inngang | Hva det genererer | Avgrensning |
|---|---|---|---|
| **A260 automatisk KS-grunnlag** | Deljobb `build_noark5_qa_draft` | Fullstendige `funn.jsonl`/`funn.csv`, manifest, `qa-basis-draft.json/.html` | Etterbehandlingsgrunnlag, *UTKAST*, ikke fagsaksbehandling eller vedtak |
| **Veiledet KS – komplett KS/depot-pakke** | `gui_qt/ks_paged_v023_a12.py` → `qa_complete_report_v023_a13.py` | Separate mottakertilpassede HTML-rapporter, sidevis **alle** funn, komplette CSV/JSONL og SHA-manifest, rapportgrunnlag | Krever kildeverifisert komplett indeks og låser kilde-/vurderingsrevisjon ved eksport; *UTKAST_IKKE_GODKJENT* |
| **Avvik / KS / godkjenning-dialog** | `gui_qt/qa_workflow_v022_a3.py` → `qa_export_v022_a3.py` | KS-/depotutkast, avviksregister og kobling til eksisterende rapporttjeneste | Eldre materialisert tabell/snapshot; ikke identisk navigasjon eller nødvendigvis samme skaleringsløp som Veiledet KS |
| **Generell rapport/samlerapport** | `gui_qt/report_selected_v018_a12.py` → `report_service_a20.py` | Valgte jobber/formatene HTML, PDF, JSON, CSV | Teknisk/sammenstilt rapport, ikke automatisk depotvedtak |

`noark5_workflow/reporting/qa_complete_report_v023_a13.py:export_complete_reports()` er særlig viktig: den går gjennom alle kildebundne rader i SQLite, legger dem i både KS- og depotregister, reviderer originalhash og vurderingsrevisjon før publisering, skriver først til staging, og publiserer rapportmappen atomisk. En avbrutt/feilet eksport skal ikke se ferdig ut. Rapportutdrag og fullstendige registre skilles eksplisitt.

**Viktig videre skille:** `recommendation` (`pending`, `clarify`, `accept`, `conditional`, `followup`, `reject`) i rapportgrunnlaget er en **faglig innstilling**, ikke endelig beslutning. `depot_assessment.json` for hele uttrekket er et annet, brukerregistrert vurderingsspor. Dette må avstemmes i neste UI uten å omskrive historikk.

## 9. Hva er støtte for en reell depotprosess i dag?

Prosessene nedenfor er **analyse av tilgjengelig funksjonalitet**, ikke en påstand om at DWM allerede er et komplett saksbehandlingssystem.

| Depotaktivitet | Kodefunksjonalitet | Status i operatørflyten |
|---|---|---|
| Velge ett/flere uttrekk og se samlet status | Felles `.n5jobs`, Work-UUID, Resultatvisninger, oversikt | **Aktivt**, men svakere handlingsorientering enn en samlet depotkø |
| Kontrollere kjøringens tekniske resultat | Jobblogg, råresultater, A100–A260, kontrollstatus/rapport | **Aktivt**; flere statusuttrykk må tolkes riktig |
| Se fullstendighet og integritet for evidens | A210–A230, SHA-koblinger, kildeoversikt | **Implementert**, ikke én intuitiv kontrollskjerm for alle forklaringer |
| Se avvik og sortere på alvorlighetsgrad | Funnregister, tekniske kontroller, Veiledet KS, filter | **Aktivt**; ulike UI-er viser ikke alltid samme omfang ved store data |
| Inspisere konkret feil mot XML/kilde | Arkade-forekomster, XML/linje, metadata og versjon | **Aktivt i Veiledet KS**, med forsiktige kilde-/stiavgrensninger |
| Registrere faglig vurdering av funn | Append-only KS-event med status, kommentar, bruker | **Aktivt**; ikke automatisk løsnings-/oppfølgingsstyring |
| Registrere nytt manuelt avvik | Append-only manuelt observasjonsregister | **Aktivt**; godt kilde-/provenienskille fra maskintest |
| Vurdere hele uttrekket | Egen depotvurderingssidecar og historikk | **Aktivt i Depotvurdering**, men ikke integrert som siste trinn i Veiledet KS |
| Vurdere enkeltarkivdel | System-ID-bundet egen journal/historikk | **Aktivt**, forutsatt lesbar og identitetsverifisert rapport |
| Vurdere periode/ytterår | Eget per-jobb/per-arkivdel register | **Aktivt**, separate innganger og status |
| Utføre depotets sjekkliste | Arbeidsflate, hendelser og METS-grunnlag | **Aktivt**, men egen status/kontekst |
| Lage KS-rapport til arkivskaper | Fullt funnregister, fagkommentarer og HTML/CSV/JSONL | **Implementert**, rapporten er fortsatt et utkast |
| Lage depotets interne rapport | Mottakertilpasset, kildebundet rapportutkast | **Implementert**, eget rapportløp og innstilling, ikke vedtak |
| Følge korrespondanse/svar fra arkivskaper med ansvar, frist og hendelseskjede | Eldre annotasjonskoder tilbyr *spørsmål/oppfølging*; ingen samlet sakskø ble påvist i undersøkte aktive Qt-kjeder | **Ikke påvist som sammenhengende arbeidsflyt** |
| Sikre endelig signert/formell depotbeslutning og journalkobling | Fagstatus/utkast finnes; ingen helhetlig beslutnings-/journalprosess påvist | **Ikke påvist som fullført ende-til-ende-funksjon** |

## 10. Kodegjennomgangens funn: risiko, konsekvens og anbefalt retning

Prioriteter her er **forslag til videre arbeid** og er ikke allerede implementerte feilrettinger.

| Prioritet | Konkret observasjon | Risiko/brukerkonsekvens | Anbefalt retning |
|---|---|---|---|
| **P0** | Vanlig Resultatvisninger leser kun inntil 12 MB depotrapport og 16 MB standard evidens-JSON | Et stort uttrekk kan oppfattes som uten fullstendig resultat, selv om Work/KS har kildegrunnlaget | Innfør felles kildebundet, strømbasert/sidevis resultatadapter; vis eksplisitt «delvis», «ikke lastet» og årsak |
| **P0** | To forskjellige Qt-KS-innganger: eldre avviksdialog og nyere Veiledet KS | Inkonsistent navigasjon, rapportvalg og skalering; flere steder å dokumentere samme prosess | Én foretrukket inngang til sidevis KS og depotbehandling; bevar samme append-only ledgers |
| **P0** | Resultatstatus, kildekvalitet, funnstatus, periode, depotvurdering og innstilling er separate | Lett å forveksle «ferdig», «OK», «vurdert» og «godkjent» | Samlet statusmodell **for visning** med eksplisitte dimensjoner og kildehenvisning; ikke skriv om de eksisterende registrene |
| **P1** | Manuell vurdering av heluttak, arkivdel, periode, sjekkliste og enkeltfunn foregår i egne paneler | Brukeren mister kontekst og neste steg, spesielt ved mange arkivdeler | Arbeidsorientert «Depotkontroll»-oversikt med navigasjon uttrekk → arkivdel → avvik → vurdering → rapport |
| **P1** | Veiledet KS blokkerer åpning under aktiv jobb | Vanskelig å følge teknisk kontroll og se avvik mens validering pågår | Tillat *read-only* inspeksjon av allerede stabile kilder; faglig lagring/rapport kun mot verifisert kildeversjon |
| **P1** | Flere rapportbyggerløp (A260, eldre QA, komplett KS, a20 samlerapport) | Brukeren forstår ikke hvilken rapport som er kildetro og fullstendig | Én «Rapportgrunnlag og eksport»-inngang med tydelige valg av mottaker, innhold, kilde-/omfangsstatus og dokumentert eksportformat |
| **P1** | Funnjournaler og hel-/arkivdelbeslutninger er ulike registre | Kommentar på funn får ikke automatisk synlig plass i helhetsvurderingen | Samlet lesbar referanse-/vurderingsoversikt, med original vurderingshendelse som autoritativ; ingen automatisk statuspromotering |
| **P1** | Kilde-/rapportversjon er strengt SHA-bundet | Riktig fail-closed kan se ut som «manglende vurdering» etter ny analyse | Vis «eldre vurdering finnes, men gjelder forrige rapportrevisjon», med trygg eksplisitt sammenligning |
| **P2** | Historisk annotasjon/områdejournal og eldre CustomTkinter-moduler eksisterer parallelt | Dobbeltfunksjoner og uoversiktlig vedlikehold | Kartlegg eksisterende data i faktiske Work-filer; avtal kanonisk visningsmodell og migrerings-/lesestrategi før kodeendring |
| **P2** | Mange versjonerte Qt-klasser/incremental hooks | Høyere kompleksitet ved navigasjonsendringer | Behold atferd mens en felles presentasjons-/navigasjonskomponent gradvis konsolideres |
| **P2** | Ingen integrert oppfølgingskø med ansvar, frister, svar og lukking er påvist | Avvik som skal til arkivskaper risikerer å bli løse fritekstmerknader | Vurder senere sak/oppfølging som **egen faglig domenemodell**, ikke som automatisk godkjenning eller omskriving av funn |

## 11. Foreslått brukerprosess som neste utviklingsmål

En målprosess for depotets operatør kan bygges på **eksisterende kode**, og bør ta én stabil jobb-/kildeidentitet med seg hele veien:

1. **Velg uttrekk eller jobbliste.** Vis tilgjengelig Work, sist valgte kontrollkjøring, komplett/delvis teknisk kjøring, og om A210–A260 er utført.
2. **Se vurderingsbehov på ett nivå.** Ett dashboard med tekniske statusindikatorer, kildekvalitet, antall individuelle funn per alvorlighetsgrad og kontrollkilde, faglig vurderte/uvurderte, arkivdeler og restpunkter. *Ikke summer forskjellige kilder som likeverdige tester.*
3. **Gå inn på avvik.** Sidevis funnregister (`qa_paged_review_v023_a12`) med kilde, test, objekt, arkivdel, original status og referanser. Filtrer FEIL, WARNING, REVIEW, ikke vurdert og kilde.
4. **Kontroller evidens.** Vis faktisk rapportert forekomst, den relevante XML/linjekonteksten og eventuelt dokumentert Noark-regel/betingelse. Skille mellom kildeordlyd, historisk mapping og faktisk oppfyllelse.
5. **Registrer faglig behandling.** Eksisterende append-only `record_review()` med begrunnelse, bruker og rapportmottaker. «Lagre og neste» og oversikt over resterende funn.
6. **Oppsummer på arkivdel og uttrekk.** Les samlet vurderingsstatus, egne manuelle avvik, periodevurdering og sjekkliste. *Ikke* konverter faglig funnstatus til automatisk arkivdelbeslutning.
7. **Dokumenter arkivskaperoppfølging.** Synlige spørsmål, svar og restavvik med kilde- og vurderingsreferanse. Dette krever en designbeslutning om oppfølgingsmodell.
8. **Generer målrettede rapportutkast.** Bruk det komplette, SHA-bundne a13-eksportløpet; velg arkivskaper/depot, gi eksplisitt fullstendighetsstatus, og bevar referanser/historikk.
9. **Registrer separat depotfaglig beslutning.** Bruk eksisterende heluttak-/arkivdeljournal der den er relevant; formelle beslutnings- og journalrutiner avgrenses i et senere spesifikasjonstrinn.

**Designprinsipp:** Resultatvisning er først og fremst *forståelse og navigasjon*; vurderingsjournal er *dokumentasjon av menneskelig vurdering*; rapport er en *kildebundet projeksjon*; vedtak er en *særskilt prosess*. Fire ting, ikke én statusknapp.

## 12. Anbefalt prioritering og akseptansekriterier for neste kodearbeid

Dette er forslag, ikke gjennomførte endringer:

### Første leveranse: konsistent og komplett oversikt

1. Lag en felles lesemodell for «Depotkontroll / Resultater» som bygger på Work-UUID, kjent rapportrevisjon og de sidevise QA-indeksene.
2. Bruk eksplisitte felt for `teknisk_kjorestatus`, `evidensdekning`, `kildefamilie`, `testfunn`, `faglig_vurdering`, `depotvurdering`, `periode`, `rapportstatus` og `kompletthetsgrad` – med egne nivåer for uttrekk, arkivdel og funn.
3. Gi «Åpne funn», «Vis XML-kilde», «Vurder», «Åpne arkivdel», «Åpne rapport» og «Fortsett manglende teknisk deljobb» bare når riktig tilstand tillater det.
4. Verifiser at en **stor** kilde ikke blir tom i Resultatvisninger på grunn av den gamle 12/16-MB-leseren. «Ukjent/ikke lest» er lov, feilaktig null er ikke lov.
5. Ikke lag enda en faglig vurderingsjournal; gjenbruk `qa_review_events_v021_a13` og de eksisterende heluttak-/arkivdeljournalene.

### Andre leveranse: samlet operatørarbeidsflyt

1. Samordne navigasjon mellom Resultatvisninger → Veiledet KS → Depotvurdering → Rapportutkast, uten å miste valgt jobb, arkivdel, funn og filter.
2. Vis alle individuelle funn fra komplette kilder også ved store uttrekk, samtidig som rapport-/kildeidentiteten kontrolleres.
3. Skill «faglig innstilling», «vurdering lagret» og «endelig depotstatus» synlig.
4. Dokumenter hvilken mottaker som ser hvilke kommentarer; vis utkast/fullstendig register uavhengig av HTML-forhåndsvisning.

### Tredje leveranse: saksflyt og beslutningsgrunnlag

1. Avklar ansvar, frist, arkivskapers svar, restavvik, lukking og beslutningsreferanse **før** eventuell ny sak-/oppfølgingsjournal innføres.
2. Finn en sikker måte å sammenholde tidligere rapport- og vurderingsrevisjoner, uten å gjenbruke konklusjoner om nye kilder automatisk.
3. Vurder til slutt samlet konklusjons-/dokumentflyt i tråd med faktisk depotpraksis; ingen automatisk «godkjent» ved 17/17 teknisk fullført.

**Testtilfeller som bør inngå i godkjenning av neste steg:** lite og stort uttrekk, flere arkivdeler, flere Arkade-importer, KDRS Standard/U1/U2, stor XPath/depotrapport, manglende Arkade PRONOM, endret kildehash, avbrutt kjøring, delvis Work, tidligere vurderingsrevisjon, manuell observasjon og brukerbasert rapportutkast. Bruk syntetiske testdata i CI og verifiser med reelle uttrekk i kontrollert lokalt testmiljø.

## 13. Sporbar kildekart – sentrale moduler

Dette er de sentrale kildeinngangene for fremtidig kodearbeid. Filnavnene viser faktisk eksisterende implementasjoner ved angitt commit.

| Ansvar | Modul og viktig API |
|---|---|
| Qt-oppstart/aktiv klasse | `gui_qt/__main__.py:main`; `gui_qt/main_v025_a3.py:DwmMainWindow` |
| Resultatvinduets konstruksjon | `gui_qt/main_window.py:_a12_open_result_center`; `gui_qt/main_v020_a6.py:_a12_open_result_center` |
| Resultatvindu, kjerne | `gui_qt/result_center_v018_a13.py:ResultCenterWindow` |
| Resultatvindu, kilde/depot | `gui_qt/result_center_v019_a1.py:ResultCenterWindow` |
| Resultatvindu, policy/detalj | `gui_qt/result_center_v0110_a4.py:ResultCenterWindow` |
| Gruppemeny og lesbare sidepaneler | `app/result_tabs_v020_a6.py`; `gui_qt/result_navigation_v020_a6.py`; `gui_qt/result_side_layout_v020_a6.py` |
| Inventar/volum/kontroller | `app/result_center_v018_a12.py:discover_results`; `app/result_evidence_v018_a13.py` |
| Kilde-/Arkade-dekning | `app/evidence_workbench_v019_a1.py:source_inventory`, `arkade_coverage` |
| XPath-/KDRS-katalog | `gui_qt/noark5_xpath_audit_v021_a1.py`; `app/noark5_xpath_audit_v021_a1.py` |
| Inngang KS (eldre) | `gui_qt/qa_workflow_v022_a3.py:open_active_job_qa`, `QaFindingReviewDialogV022A3` |
| Inngang Veiledet KS | `gui_qt/main_v023_a4.py:_a12_open_ks_workshop`; `gui_qt/ks_paged_v023_a12.py:KsWorkshopDialog` |
| KS-visning og redigering | `gui_qt/ks_guided_v023_a4.py`; `gui_qt/ks_workshop_v022_a12.py` |
| KS-kildeinspeksjon | `app/ks_inspector_v023_a1.py`; `app/ks_xml_evidence_v023_a19.py`; `app/ks_metadata_v023_a2.py`; `app/ks_value_inspection_v023_a3.py` |
| Heluttak/arkivdel depot | `gui_qt/depot_review_v019_a2.py`; `app/depot_review_v019_a2.py`; `noark5_workflow/analysis/depot_assessment.py` |
| Funnjournal, kildebinding | `noark5_workflow/reporting/qa_review_v021_a13.py:record_review`, `latest_reviews` |
| Manuelle funn/snapshot | `noark5_workflow/reporting/qa_workflow_v022_a3.py:record_manual_finding`, `build_review_snapshot_v022_a3` |
| Stor Arkade-indeks | `noark5_workflow/reporting/qa_paged_v023_a8.py:build_arkade_index`, `page_arkade_index` |
| Sidevis full KS og lagring | `noark5_workflow/reporting/qa_paged_review_v023_a12.py:build_paged_index`, `review_page`, `save_review_for_page` |
| Full DWM-individfunn | `noark5_workflow/reporting/qa_delivery_v023_a11.py:iter_verified_delivery` |
| Stor depot-/XPath-lesing | `noark5_workflow/reporting/qa_depot_stream_v023_a17.py`; `qa_xpath_master_v023_a16.py` |
| DWM/Arkade kontrollavstemming | `noark5_workflow/reporting/qa_control_coverage_v023_a18.py:reconcile_controls` |
| A210/A230 | `noark5_workflow/operations/canonical_evidence_v026_a3.py` og basis `canonical_evidence_v022_a7.py` |
| A260 komplett register | `noark5_workflow/reporting/qa_a260_v023_a6.py:build_qa_basis_a6` |
| Komplett KS/depot-eksport | `noark5_workflow/reporting/qa_complete_report_v023_a13.py:export_complete_reports` |
| Eldre KS/depot-eksport | `noark5_workflow/reporting/qa_export_v022_a3.py:export_review_bundle_v022_a3` |
| Generell rapportgenerator | `gui_qt/report_selected_v018_a12.py`; `noark5_workflow/reporting/report_service_a20.py` |
| Periodevurdering | `noark5_workflow/reporting/period_assessment_a16.py` |
| Sjekkliste | `noark5_workflow/reporting/qa_checklist_v021_a15.py`; `gui_qt/checklist_v021_a15.py` |
| Separat eldre annotasjonsmodell | `noark5_workflow/analysis/depot_annotations.py`; `gui/depot_result_views.py` |
| Separat områdevis status | `noark5_workflow/analysis/depot_review_status.py` |
| Work-kilde/tilstand | `app/work_persistence_v018_a10.py`; `noark5_workflow/core/work_job_store.py` |
| Råresultater og operasjonshistorikk | `noark5_workflow/core/raw_result_store.py`; `noark5_workflow/core/operation_history_a11.py` |
| Avhengigheter | `app/workflow_dependencies_v022_a7.py` |
| Depot-/organisasjonsprofil | `app/depot_profiles_v022_a1.py`; `gui_qt/depot_profile_v022_a1.py` |

### 13.1 Regresjonstester relevante for videre arbeid

- `tests/test_v019_a2_depot_review.py` – depotvurdering og omfang.
- `tests/test_v021_a13_review_and_reporting.py` – fagjournal/rapportvalg.
- `tests/test_v022_a3_qa_workflow.py` – manuelle funn og integrert KS-snapshot.
- `tests/test_v022_a12_ks_workshop.py` – KS-arbeidsflate.
- `tests/test_v023_a4_guided_review.py` – Veiledet KS.
- `tests/test_v023_a8_paged_qa.py` – stor Arkade/sideindeks.
- `tests/test_v023_a12_paged_review.py` – fullstendig sidevis KS.
- `tests/test_v023_a13_complete_report.py` – komplett rapportering.
- `tests/test_v023_a14_review_scale.py` – stor vurderingshistorikk.
- `tests/test_v023_a6_a260_large.py` – A260 store funnregistre.
- `tests/test_v026_a3_a230_evidence.py` – A230, verifisert gjenkobling/feiltilfeller.
- `tests/test_v026_release_final.py` – sluttversjons- og koblingskontroll.

Ved videreutvikling bør vi **legge til** tester for de nye sammenhengene og storfilvisning, ikke fjerne historiske tester eller senke kontrakter for å få en grønn kjøring.

## 14. Bevisnivå, åpne spørsmål og anbefalt neste diskusjon

Det som er **bekreftet i kode**: eksisterende moduler, API-er, sentrale statusfelt, lagringskontrakter, Qt-innganger, opplastede rapport-/evidensformater, strømmelesere/SQL-sideindekser og de oppgitte eksplisitte størrelsesgrensene.

Det som **gjenstår å verifisere med faktisk bruk**: om en bestemt jobb gjengir *alle* relevante funn i hver fane; hvor mange avvik en bruker opplever i 1547_003/005/007; hvordan vinduer oppleves ved normal/høy skjermoppløsning; responstid for store Work; om eldre rapport-/vurderingsrevisjoner kan gjenbrukes korrekt; og hvordan depotets praksis for arkivskaperdialog, vedtak og journalføring ønskes støttet.

**Neste produktavklaring anbefales å være én konkret arbeidsflate:**

> «Når en Noark 5-jobb er teknisk ferdig eller delvis utført, skal depotmedarbeideren umiddelbart se hva som er dokumentert, hvilke avvik som krever handling, hvor hvert avvik kan inspiseres og vurderes, og hva som gjenstår før et kildebundet rapportutkast kan genereres.»

Hvis dette blir styrende for neste inkrement, kan vi lage et presist skjerm-for-skjerm kravgrunnlag **basert på eksisterende Work-API-er**, fremfor å starte enda en separat resultat-/KS-motor.

---

**Endringer utført ved denne kartleggingen:** Kun dette Markdown-dokumentet er opprettet for gjenbruk. Ingen DWM-produksjonskode, tester, Source, Work, eksisterende releasehistorikk eller vurderingsdata er endret.
