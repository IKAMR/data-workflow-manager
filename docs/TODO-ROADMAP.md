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

## Status etter v0.2.1-a16 og godkjent arbeidsretning

- **a15 (committet):** Felles arbeidsflate for depotets sjekkliste: 49
  manuelle kontrollpunkter, 8 faglige tekstfelter, Work/METS-kildesporing
  og separate mottakere i KS-/depotrapporter.
- **a16 (leveres til testing):** Bevart ytre info.xml og indre DIAS METS
  som separate, SHA-256-verifiserte Work-kilder; komplett tekst-/attributt-
  inventar for kildefiler innenfor dokumenterte størrelsesgrenser; de 47
  Arkade 5-feltene og de fire allerede eksisterende depotfeltene redigeres
  i samme Work-metadata; øvrige XML-forekomster har egne kildebundne Work-
  korreksjoner og append-only historikk. Like verdier vises nøytralt,
  ulike/endrede utheves. Se `docs/NOARK5-DIAS-METADATA-V021-A16.md`.
- **a16.1 (GUI-opprydding etter a16-test):** 47 Arkade-felt som
  standardvisning, separate depotfelt, faglig gruppert tillegg fra METS,
  teknisk XML-inventar i egen visning. Begge METS-representasjonene har
  kildefelt per metadataelement med forventet plassering, faktisk
  forekomst når bevart kilde er importert, kildeidentitet og SHA-256.
  Se `docs/NOARK5-DIAS-METADATA-V021-A16-1.md`. Dette er en retting
  over a16, ikke et nytt funksjonelt hovedtrinn.
- **a17 (plan):** Konfigurerbar **depotprofil** uavhengig av Noark-teknisk
  profil og DWM-brukeridentitet. Standard **Test Depot** med fiktive data,
  logo/ikon og headeroppsett `Small / Medium / Full`. Depotidentitet
  må aldri utledes automatisk fra METS `PRESERVATION` uten vurdering.
- **a18 (plan):** **Én** kanonisk depot-sjekkliste fremfor to parallelle
  DOCX-utkast. Bruk depotprofil for dokumentoppsett og velg eventuelt hvilke
  METS-data som skal vises i header. Sjekkpunktene gjenbruker faktisk evidens,
  men ingen kontroller blir automatisk godkjent.
- **a19 (plan):** Valg mellom en **Enkel**, lineær arbeidsflyt for kontroll
  og validering, og den eksisterende **Avansert** visningen. Begge bruker
  nøyaktig samme jobb, kontrollmotorer, Work og rapportgrunnlag.
- **a20 (plan):** Godkjenningsbrev med depotprofil, KS-/depotgrunnlag,
  dokumenterte restavvik og eksplisitt manuell faglig beslutning.
- **Supplerende:** Strømmebasert håndtering av svært store indre METS,
  arkivskapers svar/avvikshåndtering, differansevisning mellom flere
  kildeperioder, XML-innsyn fra funn, kontrast mellom dialoger og knappen
  `Åpne mappe` for genererte artefakter. Verifisert KDRS/Saxon-paritet
  og historisk Noark 5 v3.1/4.0/5.0-dekning fortsetter separat.

## Senere GUI-forbedringer og etterprøvbarhet (observert i a14-test)

Prioriteres etter pågående Noark 5-rapporter og faglig vurdering, og avklares
med prosjektansvarlig for implementering. Behold eksisterende Qt-rammeverk,
Work-struktur og skrivebeskyttede kildegrunnlag.

- **Åpne selve XML-forekomstene fra kontrollfunn:** Utvid detaljvisningen
  `KS / depot -> N5.15/N5.22 -> Vis XML-linjenumre og kildehenvisninger...`
  med lesbar visning av *faktisk element og noen kontekstlinjer* fra riktig
  `arkivstruktur.xml`, for eksempel de 20 registreringene for N5.22.
  Koble til test-ID, arkivdel/system-ID, dokumentert fil, linjenummer og
  riktig run/evidensversjon. Vis rad/linjevis navigasjon, evt. kopier
  utdrag. Original Source forblir uendret og skrivebeskyttet; verifiser
  tilhørighet og filidentitet for navigering, og si tydelig fra hvis
  kildefilen ikke er tilgjengelig eller er endret siden kontrollen.
  Ingen stille linjeoppslag mot en annen versjon av XML-filen.
- **Bedre visuell separasjon mellom dialogvinduer:** Operatøren mister
  oversikten når flere mørke vinduer stables. Utred smal, kontrasterende
  ytterramme/aktiv tittellinje (lysere i mørk modus, mørkere i lys),
  tydelig fokus for aktivt vindu og mer dempet inaktivt vindu. Prøv
  fargekontrast og Windows-tittellinjer i både lys og mørk modus.
  Full fargeinvertering av en bred ramme eller egne rammeløse vinduer
  er ikke et vedtatt tiltak. Bevar vanlig dra-/endre størrelse-/lukk-UI,
  dialog-parenting, tastaturnavigasjon og plassering på riktig skjerm.
- **Felles `Åpne mappe`-handling etter generering:** Der DWM lager rapport,
  eksport, evidens eller annen fil i Work/valgt destinasjon, vis en tydelig
  `Åpne rapportmappe` / `Åpne utdatamappe`-knapp ved siden av eventuell
  `Åpne siste rapportpakke`. Knappen skal åpne *den faktiske mappen* i
  filutforskeren, ikke bare `index.html`, og være deaktivert hvis
  stien mangler. Bruk en felles Qt-handling, ikke separate kopier av
  logikken. Ikke endre eller åpne Source for skriving.
- **Tydeligere kildeperiode i rapporter:** a14-testen av `1525_004` viser
  ulike oppgitte perioder: Arkade 5 `2005-01-24 - 2024-01-15`, Work/METS
  `2005-01-01 - 2022-02-01`, mens METS-beskrivelsen har `2008-2022`.
  Vis alle med kilde og datodefinisjon, og tilby faglig avstemming;
  ikke velg ett tidsrom automatisk eller kall forskjellene feil uten
  å dokumentere hvilken periode hvert felt beskriver.
- **Supplerende METS-kontekst også i a20 Full-rapport:** a14/a15 viser
  kildebundet Work/METS i KS-/depotutkastene, ikke i den etablerte
  tekniske a20 Full-rapporten. Vurder en lesbar kildemerket integrasjon
  der uten å duplisere rapportmodell eller påstå bekreftet identitet.

## Videre: gjenbrukbare avvikstilfeller og forslag til håndtering (etter a13)

- Registrer etter hvert **de vanligste, bekreftede avvikstilfellene** som egne,
  gjenbrukbare kasus. Hvert kasus skal angi relevant Noark-versjon, kravgrunnlag,
  test-ID og kontrollkilde, faktisk observert forhold, avvikstype og eksempler.
- Tilby tydelig **forklaring av hvorfor funnet er et avvik**, forslag til
  avvikstekst for kvalitetssikringsrapporten og mulige dokumenterte oppfølginger
  for depotet. Forslag skal kunne velges, redigeres eller forkastes av fagpersonen;
  ikke automatisk konklusjon, endring av uttrekk eller depotgodkjenning.
- Skill mellom en **gyldig metadata-/statusverdi** og et **avvik fra kravene til
  uttrekk/avlevering**. Behold originalt testutfall og uforandret kildeevidens.
- **Bekreftet eksempel N5.22 (1525_004):** Arkade 5 rapporterer korrekt `ERROR`
  for 20 journalposter med status `Journalført`. M053 omfatter `Journalført`
  som gyldig journalstatus, men ved uttrekk/avlevering skal journalpostene ha
  status `Arkivert` eller `Utgår`. At arkivdelen er aktiv gjør ikke funnet til
  en falsk positiv. Eventuell behandling/tilbakemelding til arkivskaper er en
  egen faglig prosess, ikke en omklassifisering av Arkades test.
- **Ikke implementer regel-/tekstbiblioteket i a13.** Ta arkitektur og
  prioritering opp med prosjektansvarlig før nye automatiske regler innføres.
- GUI-idé til senere: Vurdere om `Faglig vurdering` bør vise
  `Periodevurdering` og `Depotvurdering` som tydelige knapper fremfor bare
  nedtrekksmeny. Tilpass vindusstørrelse ved åpning eller tilby `Auto størrelse`.
  Ikke prioriter dette foran kvalitetssikring og rapportering.

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
