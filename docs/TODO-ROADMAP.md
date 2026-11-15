# ToDo og videre plan

Dette dokumentet samler konkrete åpne punkter og beslutninger som skal følges opp i videre utvikling.

## Prioritert Noark 5-kvalitetssikring og godkjenning (uke 16.–20. november 2026)

**Hovedprioritet:** Fullføre pågående v0.2.1-arbeid med Noark 5 v3.1/4.0/5.0,
KDRS Query Standard/U1/U2, XSD-/XPath-verifikasjon og faktisk Saxon/lxml-
sammenligning før arbeidet med rapportene ferdigstilles. Ikke fremstille
teksttreff, XSD-validitet eller intern DWM-regresjon som normativ godkjenning.

1. **KDRS-paritet (aktiv):** Sammenlign identisk kildeuttrekk og dokumenterte
   KDRS/Saxon-resultater med DWM/lxml. Kartlegg Standard, U1 og U2 og spor
   avvik, ikke-sammenlignbare felt, historiske regelvarianter og filhash.
   a11.1 er foreløpig sammenligningsmotor; faktisk Saxon-kjøring og komplett
   resultatkartlegging er ikke verifisert.
2. **Kvalitetssikringsrapport (prioritert):** Bruk en frosset, identifisert
   resultatversjon til å dokumentere uttrekkets identitet, proveniens,
   datadekning, tekniske og faglige kontroller, avvik, begrunnede merknader,
   spørsmål til arkivskaper og svar/bekreftelser. Uavklarte eller ikke kjørte
   kontroller må fremgå; rapporten er ikke automatisk depotgodkjenning.
3. **Godkjennings-/ferdigstillingsrapport (prioritert):** Depotets beslutning
   bygger på kvalitetssikringsrapporten, kontrollplan, arkivskapers uttalelser,
   restavvik og eksplisitt faglig vurdering. Registrer beslutningsmyndighet,
   godkjent/ikke godkjent/med forbehold, forutsetninger, dato, journalreferanse
   og videre bevaringsløp. Ingen teknisk PASS gir automatisk aksept.
4. **Felles rapportgrunnlag:** Gjenbruk kanonisk resultat-/evidensmodell og
   eksisterende rapporttjeneste; ingen parallelle rapportdatabaser, ingen
   omskriving av Source eller tidligere Work-rapporter.

**Utsatt ToDo – skal ikke utvide aktivt a11-scope:**

- **Arkade 5 sine Noark 5-tester:** Den kildekodeverifiserte katalogen over
  54 tester er dokumentert i `docs/ARKADE5-NOARK5-TESTS.md`. Gjennomgå
  import, faktisk kjøring, feil-/advarselsresultater, manglende dekning og
  sporbar kobling til DWM-kontroller og rapporter. Bevar forskjellen mellom
  Arkade-test, KDRS-jobb og normativ Noark-krav-ID.
- **Flertrådet/multiprosessor-kjøring:** Planlegg ressursstyrt parallellitet
  både per uttrekk, per operasjon og eventuelt per test; vurder CPU-bundet
  XPath/XML, I/O og eksterne prosesser separat. Krav om deterministiske
  resultater, kontrollert samtidighet, beskyttet Source, avbrytelse uten
  ødelagt kjøring, og isolering av resultatfiler/logg. Benchmark og test
  før standardoppsett endres. Ingen implementasjon i a11.

Se `docs/NOARK5-CONTROL-TO-PRESERVATION-ROADMAP.md` for prosesskjeden
kontroll -> kvalitetssikring -> godkjenning -> bevaring.

## Operasjonssynlighet og modenhet

- Modenhet defineres per operasjon som `alpha`, `beta` eller `stable`.
- GUI bruker forståelige valg: `Alle (inkl. Alpha)`, `Beta og stabile`, `Kun stabile`.
- Workflow-raden bruker kompakt prefiks `(A)`, `(B)` eller `(S)` slik at én operasjon fortsatt vises på én rad.
- Generell operasjonsmetadata ligger under `config/`, ikke under `noark5_workflow/`.
- `config/operations.json` er generell policyfil.
- Ukjent/udefinert operasjon skal behandles konservativt som Alpha.

## Jobber og identitet

- Dagens `JOB-001`-ID-er er midlertidige tekniske ID-er.
- Senere modell skal skille intern ID, kort label (f.eks. `1525_001`) og full label (f.eks. `1525_001 Velferd (1998-2018)`).
- Aktiv jobb skal være tydelig i hovedvindu og Jobber-vindu.
- Samme source kan brukes i flere jobber.
- Forskjellige jobber i samme jobbliste skal ikke bruke samme output-root.
- Eksisterende jobber skal kunne redigeres og kjøres på nytt uten tap av tidligere historikk.
- Jobbens `operation_params` skal være autoritativ; mutable operasjonsobjekter må ikke lekke konfigurasjon mellom jobber.

## Jobblister, autosave og recovery

- `.n5jobs` er brukerens eksplisitte, varige jobblistefil.
- Implementer separat crash-safe autosave/recovery under app-workspace, som standard `<temp_dir>/joblists/recovery/`.
- Recovery skal ikke overskrive original `.n5jobs` automatisk.
- Recovery skal oppdateres ved relevante jobb-/workflow-endringer.
- Ved oppstart skal nyere recovery kunne oppdages og brukeren tilbys gjenoppretting eller forkasting.
- Recovery må knyttes til original jobbliste og ha tidspunkt/revisjonsinformasjon.
- Etter eksplisitt lagring skal tilhørende recovery kunne ryddes eller markeres håndtert.

## Workflow og kontrollpunkter

- Flere kontrollpunkter i samme workflow.
- Fortsett fra lagret execution cursor.
- Praktisk ende-til-ende-test av kontrollpunkt krever minst to reelle operasjoner i workflow.
- Senere: kjør valgte operasjoner, retry, pause/resume og mer avansert scheduler.

## Resultater, kjøringer og AIC

- Innfør gjennomgående run-ID per operasjonskjøring og resultatregister per jobb.
- Overordnet single-/batchkjøring har én egen run-logg per kjøring; samme format brukes for single og batch.
- Overordnet run-logg skal være sammendrag og referere til jobb/output, ikke duplisere detaljert operasjonslogg/PREMIS.
- Innfør eksplisitt output-policy per operasjon, f.eks. `unique`, `append`, `versioned`, `replace`, `fail`.
- Skill arbeidsresultater/testhistorikk fra det som finaliseres til AIC.
- Resultatregister skal gjøre det mulig å markere hvilke resultater som er kandidater for finalisering.
- Gjør AIC-finalisering til eksplisitt workflow-steg med manifest/subset-valg.
- PREMIS og andre historikkfiler skal ikke overskrives stille ved rerun. PREMIS-historikk skal bevares/akkumuleres.

## App-workspace, setup og huskede mapper

- `temp_dir` er rot for appens arbeidsområde, ikke én flat temp-katalog.
- Standardstruktur: `logs/runs/`, `setup/`, `joblists/`, `work/`, `cache/`.
- `run_log_dir`, `setup_dir` og `job_list_dir` kan overstyre standardplasseringene.
- Tom verdi / `Bruk standard` betyr fallback til undermappe under `temp_dir`.
- Skill konfigurert standardmappe fra `last_*`-verdier som bare betyr sist brukte dialoglokasjon.
- Standardiser huskede mapper: Noark source, DIAS output, METS-import, Legg til fil/mappe, setup og jobblister.
- Setup eksport/import bruker plattformuavhengig JSON-format.
- Reset skal gi dokumenterte standardinnstillinger.
- Profiler for arbeidsoppsett vurderes senere; huskede mapper er generell brukerkomfort og er ikke det samme som profiler.
- På sikt flyttes runtime-state og brukerinnstillinger til plattformriktig per-user application-data-område.

## Repositorystruktur

- Repo-root skal bare inneholde filer med klar root-rolle.
- Generell applogikk legges under `app/`.
- Generell konfigurasjon og policy legges under `config/`.
- `noark5_workflow/` skal bare brukes for Noark 5-spesifikk logikk.
- `settings.py` og `version.py` kan vurderes flyttet senere som en egen bevisst refaktorering, ikke midt i et funksjonelt fix-trinn.
- Midlertidige versjons-wrappere bør ryddes ved en kontrollert konsolidering; canonical runtime-filer foretrekkes.

## UI-konsistens

- Bruk knappereglene i `INTERFACE.md` konsekvent i nye dialoger.
- Gjennomgå resterende GUI ved senere UI-opprydding slik at primær, sekundær og stopp/fare har samme semantikk overalt.
- DIAS-dialog: rydd senere plassering av `Utdatamappe` / `Velg mappe…` / METS uten å prioritere kosmetisk ombygging foran funksjonelt arbeid.
- Workflow-listen skal fortsatt være kompakt med én rad per operasjon.

## Kjøremiljø og videre arkitektur

- Windows desktop er nåværende testede hovedmiljø.
- Test Windows RDS/Terminal Server før dette erklæres støttet.
- Headless worker/server på Windows/Linux er prioritert senere.
- `LocalExecutor` skal kunne suppleres med `RemoteExecutor`.
- Store kilder skal normalt refereres via delt lagring, ikke lastes opp til worker.
- Senere Linux/macOS-launchere og testmatrise ved behov.
- Docker/Podman er naturlig for backend/worker, ikke som erstatning for desktop-GUI.
