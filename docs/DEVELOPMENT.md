# Utviklingsregler

## Obligatorisk leserekkefølge før utvikling

Følgende nummererte liste er en arbeidsrekkefølge, ikke kapittelnummerering i dette dokumentet.

1. Les `docs/DEVELOPMENT.md`.
2. Les `docs/ARCHITECTURE.md` der den er relevant.
3. Les `docs/INTERFACE.md` ved endringer i grensesnitt eller kontrakter.
4. Les `docs/CLI.md` ved endringer i offentlig CLI-syntaks, argumenter, flags, exit codes eller CLI-brukeradferd.
5. Les `docs/DEFINITIONS.md` ved endringer som berører begreper og lagdeling.
6. Les `docs/TESTING.md` ved endringer som krever ny eller endret validering.
7. Les `docs/CODE-MAP.md` for å finne riktig lag og dataflyt.
8. Les `docs/NOARK5-DEPOT-PRESENTATION-AND-ASSESSMENT.md` ved endringer i Noark 5 Resultatvisninger, Oversikt, Arkivdeler, depotvurdering, vurderingspunkter eller KI-assistert førstegjennomgang.
9. Les `docs/RUNTIME-ENVIRONMENTS.md` ved endringer i installasjon, oppstart, filstier, brukerdata, eksterne programmer, packaging, server/worker eller plattformstøtte.
10. Les `docs/SHARED-DEVELOPMENT.md` og `docs/SHARED-ROADMAP.md` før generiske workflow-/depotendringer som også kan være relevante for SIARD Workflow Manager.
11. Les `docs/METHOD-OBSERVATIONS.md` ved start og avslutning av et utviklingsincrement. Nye erfaringer som kan ha generell verdi for utviklingsmetodikken registreres der uten at metodikk-repositoriet automatisk endres.
12. Behandle dokumentert arkitektur som målbildet. Kontroller samtidig den faktiske koden før endringer gjøres.

## AI-assistert samarbeids- og leveransekontrakt

Denne kontrakten er obligatorisk ved AI-assistert utvikling av prosjektet og skal leses før nye kodeendringer planlegges eller leveres.

1. **GitHub er delt baseline.** AI leser gjeldende offentlig repository-tilstand og relevante dokumenter før arbeid starter. Etter at brukeren har commitet og pushet, er den pushede tilstanden ny autoritativ baseline.
2. **Dialog før endring.** Bruker og AI avklarer behov, scope og ønsket adferd før et nytt increment implementeres. Nye tanker skal ikke automatisk utvide scope.
   - **Vesentlige strukturendringer skal alltid diskuteres før implementasjon.** AI skal ikke flytte, erstatte eller omorganisere etablerte hovedflater, arbeidsflyter eller informasjonsstruktur uten at retningen først er avklart med brukeren.
   - **Visuell kreativitet er ønsket innen avklart struktur.** Når AI ser en reell mulighet for en betydelig visuell forbedring, skal forbedringen foreslås proaktivt. Når et bilde/målbilde vil gjøre valget vesentlig enklere å vurdere, skal AI foreslå å lage et slikt bilde før implementasjon. Små, reversible presentasjonsforbedringer kan fortsatt gjøres inkrementelt innen avtalt scope.
3. **AI endrer ikke Git-historikken.** AI committer eller pusher ikke med mindre brukeren uttrykkelig ber om det. Brukeren eier lokal working tree, commit og push.
4. **Kun delta siden forrige leveranse.** Hver ny ZIP eller fillesleveranse skal normalt inneholde bare filer som er nye eller endret **siden forrige ZIP/leveranse i samme increment**. En fix etter en tidligere leveranse skal derfor bare inneholde fix-deltaet, ikke hele det kumulative incrementet, med mindre brukeren uttrykkelig ber om en komplett/kumulativ pakke.
5. **Repository-relative stier.** ZIP-delta skal bevare repository-relative stier og være klare til å kopieres over working tree.
6. **Ingen leveranse-notatfiler som standard.** Ikke legg ved egne `README.txt`, endringslogg-tekstfiler, `DELETE-FILES.txt` eller tilsvarende bare for å forklare leveransen. Forklar endringer og eventuelle manuelle slettinger i samtalen. Ved en uvanlig stor eller teknisk sletteliste kan en eksplisitt hjelpefil eller `.bat` brukes når det faktisk er mer praktisk og brukeren er orientert.
7. **Tester følger samme delta.** Når produksjonskode endrer en kontrakt, skal nødvendige nye eller oppdaterte tester leveres i samme delta. Foreldede tester skal oppdateres samtidig.
8. **`test.bat` er brukerens hovedtestinngang.** AI skal kontrollere berørte tester og `test.bat` før levering så langt miljøet tillater det, og rette feil AI selv kan oppdage før pakken sendes. `test.bat` skal bare følge deltaet når selve filen faktisk er endret siden forrige leveranse.
9. **Brukeren validerer lokalt.** Brukeren kopierer inn deltaet, kjører `test.bat` og gjør relevant praktisk test, normalt via `start.bat` for GUI.
10. **Fix leveres som nytt lite delta.** Dersom testen avdekker feil, analyserer AI faktisk testutskrift og leverer bare filene som må endres siden forrige leveranse. Produksjonskode skal ikke svekkes for å tilfredsstille en foreldet test.
11. **Brukeren godkjenner og pusher.** Når automatisert og praktisk test er akseptert, committer og pusher brukeren.
12. **AI verifiserer push før neste increment.** Før videre arbeid skal AI lese den pushede GitHub-tilstanden og kontrollere at forventede filer, versjon og sentrale endringer faktisk er med.
13. **Metodikk-kandidater holdes lokalt først.** Generelle erfaringer registreres i `docs/METHOD-OBSERVATIONS.md`. `IKAMR/incremental-ai-development-method` skal ikke endres automatisk; overføring skjer først når bruker og AI eksplisitt blir enige om en egen metodikkendring.

Normalløkken er derfor:

```text
AI leser GitHub/repository
→ bruker og AI avklarer increment
→ AI leverer bare nytt delta
→ bruker kopierer inn
→ bruker kjører test.bat
→ AI leverer eventuelt fix-delta
→ bruker gjør praktisk test
→ bruker committer og pusher
→ AI verifiserer pushet tilstand
→ neste increment
```

## Endringsprinsipp

- Bevar fungerende funksjonalitet og gjør den minste nødvendige endringen.
- Ikke erstatt et etablert GUI-panel i sin helhet bare for å legge til en kontroll eller funksjon.
- Noark 5-uttrekket og DIAS SIP/AIC er separate lag.
- Mottatt Noark 5-uttrekk behandles som bevaringsbevis og skal som hovedregel analyseres, valideres og dokumenteres uten å endres.
- Nye funksjoner skal ha automatiserte tester når det er praktisk mulig.
- Før commit av en alpha: kjør `test.bat`, deretter praktisk test via relevante implementerte grensesnitt. GUI-endringer testes via `start.bat`; CLI-endringer testes også med relevante `n5wf`-kommandoer.

Nye tanker eller framtidsretninger skal normalt legges til som avgrensede arkitektur-/designpresiseringer. Eksisterende dokumentasjon skal ikke omskrives bredt dersom den fortsatt er korrekt.

## Obligatorisk regresjonskontroll før kode leveres

Dette er en fast utviklingsregel, spesielt etter at en eksisterende implementasjon er erstattet av en sterkere eller mer generell variant.

- Før et nytt delta leveres skal endrede produksjonsfiler og funksjoner sammenholdes med **alle eksisterende tester som refererer til dem**.
- Søk eksplisitt etter tester som låser seg til gammel implementasjonsdetalj, for eksempel eksakte strenguttrykk som `self._location_dialog.winfo_exists()` eller direkte modulnavn i en runtime-kjede.
- Når kontrakten er bevart eller styrket, men implementasjonen er endret, skal den gamle testen oppdateres i **samme delta**. Produksjonskode skal ikke svekkes bare for å tilfredsstille en foreldet test.
- Nye tester skal kontrollere ønsket kontrakt/adferd, ikke tilfeldig syntaks, med mindre akkurat syntaksen er en offentlig kontrakt.
- For a17 GUI-kontrakter som brukes av flere tester skal stabile semantiske verdier samles i `gui/ui_contract_a17.py`. Tester skal bruke disse kontraktene i stedet for private grid-kolonner, hjelpefunksjonsnavn eller tilfeldige dokumentformuleringer.
- `tests/test_a17_test_contract_hygiene.py` er obligatorisk regresjonsvern mot kjente foreldede a17-testmønstre. Når en implementasjonsdetalj erstattes, skal det gamle testmønsteret legges til denne kontrollen samtidig.
- GUI-kode skal ikke referere til udefinerte `theme`-symboler. Kompatibilitetsalias kan brukes når to etablerte navn uttrykker samme semantiske fargeverdi, men én verdi skal være autoritativ.
- Tester av dokumentasjon skal ikke feile på tilfeldige ordvalg eller korte tekstfragmenter når den dokumenterte kontrakten er semantisk den samme. De skal primært låse stabile overskrifter, kontraktsbegreper og nødvendige regler; eksakt formulering brukes bare når ordlyden i seg selv er kontrakten.
- Før levering skal det også kontrolleres at deltaet ikke introduserer filer som eksisterende repository-regler uttrykkelig forbyr, herunder permanente `Axx-*.md`-/alpha-dokumenter i `docs/`.
- Alpha-/delta-dokumentasjon skal innarbeides i eksisterende kanoniske dokumenter (`DEVELOPMENT.md`, `METHOD-OBSERVATIONS.md` osv.) i stedet for å bli liggende som permanente per-alpha-filer.
- Dersom full `test.bat` ikke kan kjøres i utviklingsmiljøet før levering, er en statisk kompatibilitetssjekk av berørte eksisterende tester et minimumskrav; brukeren skal ikke måtte oppdage samme type foreldede testforventning gjentatte ganger.

Denne kontrollen er en del av ferdigstillingen av hvert increment, ikke en valgfri etterkontroll.

## Brukeridentitet og framtidig serverdrift

- Registrert bruker har en permanent intern `user_id` (UUID) som ikke kan redigeres eller gjenbrukes for en annen identitet.
- `username` er den primære menneskelesbare identifikatoren i GUI og daglig bruk. Navn og e-post er registrerte attributter for samme identitet.
- Endring av navn, brukernavn eller e-post skal ikke endre `user_id`. Historiske jobb-/loggdata skal senere kunne bevare både stabil `user_id` og relevante snapshot-verdier fra kjøretidspunktet.
- Brukerprofil lagres foreløpig lokalt per bruker, men kontrakten skal kunne flyttes til en sentral/autoritativ identitetskilde ved serverdrift uten å endre jobb-/loggidentiteten.
- Runtime kan gjøre brukeridentiteten tilgjengelig for generiske kjøre-/loggkomponenter, men personopplysninger skal ikke blandes inn i portable Setup-eksporter uten en eksplisitt beslutning.
- Bunnlinjen viser `Bruker: <username>`; intern `user_id` vises ikke som normal arbeidsidentifikator.

## GUI-konvensjoner

Følgende regler er flyttet hit fra `INTERFACE.md` fordi de beskriver GUI-/utviklingskonvensjoner, ikke datautvekslingsgrensesnitt.

### Profil som eksplisitt spesialiseringsgrense

- Uten valgt profil skal GUI og Source være generiske.
- Formatspesifikk gjenkjenning og formatspesifikke operasjoner skal aktiveres av valgt profil.
- Ny formatspesifikk logikk skal derfor ikke legges inn som generell standardadferd når den egentlig tilhører en profil.

### Idempotente konfigurasjonsvalg

- En brukerhandling som velger samme verdi som allerede er aktiv, er ikke en konfigurasjonsendring.
- Særlig profilvalg skal være idempotent: velges `Noark 5` når aktiv jobb allerede har `Noark 5`, skal det ikke utløse ny deteksjon, endringslogg eller unødvendig persistens.
- Endringslogg skal beskrive reelle tilstandsendringer, ikke gjentatt valg av samme verdi.

### Automatisk lagring av workflow-oppsett

- Når aktiv jobbliste allerede har en autoritativ `.n5jobs`-fil, skal brukerens endringer i aktiv jobb lagres automatisk når operasjoner legges til, fjernes eller hele workflowen tømmes.
- Rekkefølgeendringer, konfigurasjonsendringer og andre eksisterende eksplisitt persisterte workflow-endringer beholder samme prinsipp: aktiv jobb og jobblistefil skal være synkronisert etter brukerhandlingen.
- Workflowens synlige operasjonsliste skal synkroniseres til aktiv `Job` umiddelbart ved legg til, fjern og tøm. Persistens skal ikke være avhengig av `after_idle` eller annen utsatt GUI-timing.
- Når jobblista allerede har en autoritativ fil, skal workflow-endringen skrives til denne umiddelbart. Konfigurerbare operasjoner kan skrive på nytt når deres parametre/metadata er ferdig lagret.
- **Jobbskifte er en eksplisitt persistensgrense:** jobben som forlates synkroniseres og lagres før ny jobb åpnes, og den nye aktive jobb-ID-en lagres etter skiftet.
- **Applikasjonslukking er en eksplisitt persistensgrense:** aktiv workflow synkroniseres og jobblista lagres før hovedvinduet destrueres.
- Dersom jobblista ennå ikke er lagret, beholdes endringen i aktiv jobb/minne, men det opprettes ikke en fil implisitt; statuslinjen skal gjøre dette tydelig.
- Gjenåpning/restart skal derfor returnere brukeren til siste lagrede aktive jobb og workflow-oppsett, inkludert tidkrevende operasjonskonfigurasjon.
- Endring av en tidligere kjørt eller ventende workflow skal fortsatt markere jobben som klar for ny kjøring etter gjeldende rerun-regler.

### Statuslinje og aktiv jobbliste

- Venstre felt i hovedvinduets bunnlinje viser den **aktive autoritative jobblistefilen**, ikke temp-katalogen.
- Når en jobblistefil er åpen eller lagret, skal full sti vises som `Jobbliste: <full sti>`.
- Når aktiv jobbliste ennå ikke er lagret, skal feltet vise `Jobbliste: [ikke lagret]`.
- Visningen skal oppdateres etter restart/gjenåpning, `Åpne jobbliste`, `Lagre`, `Lagre som` og `Ny jobbliste`.
- Temp-katalog er konfigurasjon og trenger ikke permanent plass i hovedvinduet; den finnes i Innstillinger.
- Midtfeltet i bunnlinjen beholdes for løpende status, og høyrefeltet for runtime-/lagringsinformasjon.

### Stabil header-layout

- Topp-headerens endelige a17-handlingsgruppe er `Mapper`, `Jobber`, `Setup`, `A-`, `A+`, `?`.
- `Endre temp-mappe` skal ikke være egen hovedknapp; temp-mappe konfigureres i `Setup`.
- `Setup` erstatter `Innstillinger` i hovedheaderen og som dialogtittel.
- `Jobber` skal alltid være eksplisitt synlig mellom `Mapper` og `Setup`.
- Den endelige handlingsgruppen skal eies av én dedikert header-frame. Arvede/foreldede handlingsknapper skjules før den nye gruppen bygges, slik at runtime-lag ikke kan kollidere i separate grid-kolonner.
- Setup-dialogen skal beholde eksisterende innhold og funksjoner; a17 legger bare til tydelig navn og `Velg…` for Temp-mappe uten bred omskriving av dialogen.

### Dialogplassering og fler-skjermsoppsett

- Egne Tk/CustomTkinter-dialoger og hjelpevinduer skal åpnes relativt til det vinduet som eier eller utløser dem, ikke på en fast skjermposisjon.
- Når hovedvinduet eller et foreldrevindu står på en ekstern skjerm, skal nye egne dialoger normalt åpnes på samme arbeidsområde/skjerm.
- En dialog som åpnes fra en annen dialog skal bruke nærmeste synlige foreldrevindu som referanse når det er praktisk mulig.
- Felles plassering skal implementeres sentralt og gjenbrukes; nye dialogklasser skal ikke innføre egen tilfeldig eller hardkodet skjermplassering.
- Posisjoneringslogikk skal være defensiv: feil ved beregning av vindusposisjon skal ikke hindre dialogen i å åpnes.
- Endringer i felles dialogplassering skal praktisk testes med minst hovedvindu + ett hjelpevindu på et fler-skjermsoppsett når slik test er tilgjengelig.

### Enkeltinstans for dialoger

- En brukerhandling som åpner en egen dialog skal ikke kunne opprette flere parallelle kopier av samme dialog ved raske eller gjentatte klikk.
- Dialogåpning skal ha en eksplisitt enkeltinstans-/reentrancy-vakt som settes før nytt `Toplevel` konstrueres; kontroll av `winfo_exists()` alene er ikke tilstrekkelig som eneste vern mot raske dobbeltklikk.
- Utløsende knapp kan deaktiveres mens dialogen er åpen og aktiveres igjen når selve toppvinduet lukkes.
- `Destroy`-håndtering skal skille mellom dialogens eget toppvindu og underliggende child-widgets, slik at vakten ikke nullstilles for tidlig.
- Nye dialoger som kan åpnes fra gjentatte brukerhandlinger skal følge samme mønster og ha regresjonstest for enkeltinstansadferd når det er praktisk mulig.

### Knappestiler og handlingshierarki

Knappfarge skal uttrykke handlingens rolle konsekvent i hele applikasjonen.

- **Primær (blå):** hovedhandlingen som fullfører eller starter aktuell oppgave, for eksempel `Legg til i workflow`, `Kjør workflow`, `Start alle` eller `Lagre` i en bekreftelsesdialog.
- **Sekundær (mørk):** støttehandlinger som valg, import, åpning, redigering, oppdatering og navigasjon.
- **Stopp/fare:** egen tydelig stil brukes bare når handlingen stopper, sletter eller har en konsekvens som bør fremheves.
- En dialog skal normalt ha bare én visuelt primær handling.
- Farge skal ikke være eneste signal for fare eller status; knappetekst og kontekst skal også være tydelig.

### Operasjonsmodenhet

Operasjoner har eksplisitt modenhetsnivå definert i `config/operations.json`.

- `Alpha`: eksperimentell og kan endres betydelig.
- `Beta`: funksjonell, men fortsatt under utvikling og testing.
- `Stabil`: klar for normal bruk.

Innstillingen for operasjonssynlighet bruker `Alle (inkl. Alpha)`, `Beta og stabile` og `Kun stabile`. Internt kan verdiene `0`, `1` og `2` beholdes for bakoverkompatibilitet.

Workflow-listen bruker kompakt modenhetsmerking på én rad:

- `(S)` = Stabil
- `(B)` = Beta
- `(A)` = Alpha

### Jobbliste

- Rekkefølgen på jobbene i `.n5jobs` er den sekvensielle batchrekkefølgen. GUI-et kan endre denne rekkefølgen med Opp/Ned.
- Sletting av en jobb fjerner bare jobbposten fra jobblista. Kilde, utdata og tidligere resultatmapper på disk skal ikke slettes som sideeffekt.
- Flytting og sletting av jobber er deaktivert mens batch kjører.
- Når en tidligere kjørt jobb redigeres slik at gjeldende konfigurasjon må kjøres på nytt, kan den interne statusen være `Klar`. GUI-et skal samtidig synliggjøre dette som `Klar – endret etter kjøring`. Kravet om eksplisitt rerun-godkjenning beholdes.

### Lagre som – én eksplisitt skriveoperasjon

- `Lagre som` skal ikke skrive noen `.n5jobs`-fil før brukeren har valgt mappe og bekreftet filnavn.
- Selve `Lagre som`-transaksjonen skal skrive nøyaktig ett eksplisitt mål.
- Automatisk persistens til tidligere aktiv jobbliste skal utsettes mens `Lagre som`-dialogflyten pågår.
- Etter vellykket `Lagre som` blir den valgte filen ny aktiv jobbliste; tidligere fil skal ikke kopieres eller flyttes som sideeffekt.

### Jobbidentitet og full reset av jobbliste

- Sletting av én jobb skal aldri renummerere andre eksisterende jobber.
- En jobb som har fått reell konfigurasjon, workflow, operasjonsparametre, kjøringsstatus eller logghistorikk har historisk identitet; jobbnummeret skal ikke gjenbrukes etter sletting.
- En **ubrukt kladdejobb** kan frigjøre nummeret sitt når den slettes dersom den er det siste/høyeste opprettede jobbnummeret. Dette gjelder en jobb uten source-/lagringsroller, workflow, operasjonsparametre, checkpoint, egendefinert navn eller kjøringshistorikk. Profilvalg alene gjør ikke kladden historisk signifikant.
- Hull i midten av en eksisterende jobbliste fylles aldri automatisk. Bare det umiddelbart siste/høyeste ubrukt kladdenummeret kan gjenbrukes.
- Den siste gjenværende jobben skal fortsatt ikke slettes med `Slett`; bruk `Ny jobbliste` når hensikten er å starte helt på nytt.
- `Ny jobbliste` etablerer en ny aktiv identitetskontekst: den aktive jobblista tømmes, GUI-/visningsloggen tømmes, og første nye jobb skal få `JOB-001`.
- Full reset av aktiv jobbliste skal ikke slette persistente kjørelogger, råresultater, PREMIS-filer eller andre historiske filer på disk.
- GUI-tekst og tester skal gjøre skillet tydelig mellom individuell sletting, gjenbruk av siste ubrukt kladde-ID og full reset av jobblista.

## Innstillinger og mappeadferd

Dialoger som åpner eller lagrer filer og mapper skal huske siste relevante lokasjon med egne, tydelig navngitte innstillinger.

- `last_noark_source_dir`
- `last_dias_output_dir`
- `last_mets_import_dir`
- `last_dias_add_file_dir`
- `last_dias_add_folder_dir`
- `last_setup_dir`
- `last_job_list_dir`
- `last_job_list_file`

Ved import av setup skal `last_setup_dir` settes til mappen setup-filen faktisk ble lest fra på denne maskinen.

Konfigurerte standardmapper og sist brukte dialogmapper er forskjellige begreper.

- `setup_dir` bestemmer standardplassering for setup.
- `job_list_dir` bestemmer standardplassering for jobblister.
- `run_log_dir` bestemmer standardplassering for overordnede kjørelogger.
- `last_setup_dir` og `last_job_list_dir` beskriver hvor brukeren sist faktisk åpnet eller lagret noe.

Tom eksplisitt standardverdi eller `Bruk standard` betyr fallback under `temp_dir`:

- kjørelogg: `<temp_dir>/logs/runs`
- setup: `<temp_dir>/setup`
- jobblister: `<temp_dir>/joblists`

Se også `APP-WORKSPACE-AND-RUN-LOGS.md`.

## CLI-konvensjoner

- Offentlige CLI-kommandoer, subcommands, argumenter og flags skal være korte, presise og på engelsk.
- `docs/CLI.md` er autoritativ brukerreferanse for implementert `n5wf`-syntaks og exit codes.
- `noark5_workflow/cli.py` skal være et klient-/adapterlag over delte tjenester/core, ikke en parallell workflow-implementasjon.
- Jobb-, preflight- og batchsemantikk som både GUI og CLI trenger skal ligge i delte komponenter som `JobPreflight`, `JobRunner` og `BatchRunner`.
- Menneskelesbar terminaltekst kan være lokalisert selv om kommandosyntaksen er stabil og engelsk.

## Installasjonskonvensjoner

- Brukeren velger `GUI + CLI`, `GUI` eller `CLI`; Core er en intern felleskomponent og ikke et separat menyvalg.
- Installering av GUI eller CLI skal bevare den andre allerede installerte profilen.
- Core regnes som aktiv så lenge minst én av GUI/CLI er installert.
- Installert profilstatus lagres per bruker i `install-state.json` under Workflow Managers `%LOCALAPPDATA%`-område.
- Installasjonsstatus er teknisk metadata og skal ikke blandes med jobb-/workflowdata.
- Deinstallasjon skal kreve eksplisitt `Ja` før endringer utføres.
- Deinstallasjon av ett grensesnitt skal beholde Core dersom det andre fortsatt er installert.
- Generelle Python-avhengigheter (`lxml`, `psutil`, `customtkinter` osv.) skal ikke avinstalleres automatisk fordi de kan være delt med andre programmer.
- Installer/deinstaller skal ikke slette repository, jobblister, logger, config eller andre brukerdata.
- `install.bat`, `deinstall.bat`, `requirements*.txt` og `pyproject.toml` beholdes i repository-roten.

## Kjøremiljø og portabilitet

- Windows desktop er dagens testede hovedbaseline; lokal `n5wf` CLI er også praktisk verifisert på Windows.
- Ikke dokumenter Linux, macOS, server eller andre miljøer som støttet før installasjon, oppstart og relevant praktisk test er etablert.
- Ikke legg ny domenelogikk i `.bat`, `.sh` eller packaging.
- Unngå hardkodede Windows-stier i core/operations.
- Bruk plattformuavhengige Python-API-er og `pathlib` når mulig.
- Runtime-state og brukerinnstillinger skal på sikt ligge i egnet per-user application-data-område, ikke være avhengig av repository/installasjonsmappen.
- Eksterne programmer skal kapsles i adaptere med konfigurerbar executable/path.
- Core/operations skal ikke avhenge av GUI.
- Jobb- og workflowfunksjoner som skal brukes fra GUI, CLI og senere API skal ligge i delte tjenester/core og ikke bare i GUI- eller CLI-handlere.
- Lokal og framtidig remote kjøring skal bevare samme operations/executor-kontrakt.

Se `docs/RUNTIME-ENVIRONMENTS.md`.

## Workflow logging, proveniens og loggformater

- **Alle operasjoner/tester** skal fremgå av vanlig intern workflow-/kjørelogg. Den interne hendelses-/loggmodellen er formatnøytral og er ikke definert av PREMIS.
- PREMIS er ett valgbart proveniensformat. `enable_premis_provenance` styrer om PREMIS produseres; andre formater, inkludert CSV/JSON, kan legges til senere uten å endre workflowmotorens grunnmodell.
- Relevante bevarings-, validerings-, migrerings-, slettings- og pakkingshendelser kan registreres som PREMIS-hendelser når PREMIS er aktivert.
- PREMIS håndteres av `noark5_workflow/core/premis_logger.py` og executor-/workflowlaget. En operasjon skal aldri bygge sin egen separate workflow-PREMIS XML.
- PREMIS skal registrere programvaren som software-agent og kan i tillegg registrere aktiv bruker som person-agent.
- Standard PREMIS agent-identifikator for bruker er `username`. Setup kan velge `user_id` når en stabil teknisk identifikator er ønsket. Den interne `user_id` beholdes uansett hvilket PREMIS-valg som brukes.
- Gyldige `eventType`-verdier følger DIAS_PREMIS v2.0: `Creation`, `Ingestion`, `Migration`, `Adjustment`, `Deletion`, `Disposal`.
- Teknisk kjørelogg, råresultater og PREMIS har ulike formål og skal ikke ukritisk kopieres over i hverandre.
- Noark 5-kilden skal ikke endres for å produsere PREMIS eller andre logg-/proveniensformater.

## Versjonering og releasehistorikk

Stabil baseline startet med `0.1.0`. Utviklingsserier bruker alpha-suffiks, for eksempel `0.1.1-a3`.

Alpha-/fikstrinn er midlertidige utviklingsidentifikatorer. Permanente release-notater samles per ferdig versjon i `docs/RELEASES.md`; det skal normalt ikke opprettes én permanent releasefil per `a1`, `a2`, `a3`, `a3.1` osv.

## Utdataområder og bevaringskilde

- Mottatt Noark 5-uttrekk er kilde/evidens og skal behandles som read-only.
- Genererte filer skal bare skrives i eksplisitt valgte arbeids-/utdataområder.
- Workflow-PREMIS skal følge eksplisitt workflow-/operasjonsutdata.
- Skill mellom arbeidsområde og finaliseringsområde for AIP.
- Ikke anta at alt i arbeidsområdet skal bevares i AIP.

## Generisk kode mot SIARD Workflow Manager

- Generiske forbedringer skal vurderes opp mot `SHARED-DEVELOPMENT.md` før de gjøres domenespesifikke.
- `SHARED-ROADMAP.md` skal oppdateres når en funksjon implementeres i ett prosjekt og er kandidat for det andre.
- Et eget felles GUI/core-repository opprettes ikke nå; kodebasene holdes løst koblet gjennom dokumenterte kontrakter, referanseimplementasjoner og tester.

### Testkontrakter ved refaktorering

Tester skal primært verifisere stabil, semantisk kontrakt og observerbar adferd. Når implementasjon flyttes bak en stabil adapter/sink/provider-grense, skal eldre tester oppdateres til den nye kontraktseieren i samme delta.

Det er ikke tillatt å beholde tester som bare søker etter en bestemt implementasjonsstreng i en historisk fil dersom funksjonen fortsatt finnes korrekt bak en ny, dokumentert grense. Før levering skal AI derfor skanne eksisterende tester for slike forventninger når kode flyttes mellom filer eller lag.
