# DWM v0.2.2-a4 – Siegfried på store Noark 5-uttrekk

**Utgangspunkt:** GitHub `IKAMR/data-workflow-manager`, commit `b386487d0201302ef883a54e827b815821cf20a4` (v0.2.2-a3). Deltaen inneholder fullstendige endrede filer. Internt `VERSION = 0.2.2-a1` og historiske versjonstester endres ikke. Ingen commit/push utføres av leveransen.

## Bakgrunn

JOB-001 / `1502_024` (~2 TB) stoppet i eksisterende Siegfried-operasjon med meldingen «Uttrekket har flere enn 250000 dokumentfiler». Dette var en villet adaptergrense, ikke et påvist filformatproblem. Tidligere adapter samlet alle filstier og alle Siegfried-resultater i minne før ferdigstilling, selv om `sf` allerede ble kjørt med opptil 100 filer per prosess.

**Sjekket mot SIARD Workflow Manager:** `IKAMR/SIARD-Workflow-Manager`, `siard_workflow/core/identifiers/siegfried.py`, metodene `pre_scan` og `_scan_file_list`. SIARD bruker eksplisitte Siegfried-batcher på 100 filstier (Windows-kommandolinjelengde) og har en persistérbar cache med filstørrelse, endringstid, Siegfried-signatur og kildeidentitet. SIARD bruker ofte flere prosesser parallelt. DWM a4 bruker samme forsiktige batchstørrelse, men velger **sekvensiell kjøring**, kontrollpunkt etter hver batch og minnebegrenset resultataggregering fordi arbeidet går mot store Noark 5-SIP-er. Ingen kode eller filer kopieres fra SIARD WM.

## Endret

- **250 000-filgrensen fjernet** for operasjonen som kjører Siegfried. Filopptelling med `os.walk` er strømmende; ingen global Python-liste med filene opprettes.
- Filinventar lagres i Work (`file_inventory.jsonl`) med relativ filsti, størrelse og endringstid for hvert funn. Inventaret får SHA-256.
- Hvert `sf`-kall får **maks 100 filstier** og en kommandolinje under ca. 20 000 tegn. Kall kjøres **sekvensielt** med maksimalt 600 sekunder per batch.
- Resultatene skrives fortløpende i `siegfried_files.jsonl`. Etter hver batch gjennomføres flush/fsync av råresultater, før et atomisk `checkpoint.json` med antall ferdige filer, råfil-offset og SHA-256 skrives. Dette gir gjenopptakelse ved påfølgende forsøk med samme kilde og sf-installasjon.
- Ved restart sammenlignes **hele inventaret**, Work/job-ID, UID, absolutt Source- og Work-sti, sf.exe-sti, versjon og signatur. Lagrede råbytes/filidentiteter etterprøves. Endret kilde eller manipulert kontrollpunkt blir **ikke** gjenbrukt. Den gamle `.partial-*` beholdes urørt og en ny kjøring startes.
- Et avbrudd/feil kan ikke publisere ufullstendige resultater. Ferdig resultat mappe får samme format og nøkkelnavn som før (`manifest.json`, `pronom_statistics.json`, `siegfried_files.jsonl`). Eksisterende Siegfried-/PRONOM-lesere er derfor ikke endret.
- Ingen Source-fil redigeres. Work-resultater for tidligere fullførte kjøringer overskrives ikke. DWM gjetter ingen RAF-godkjenning fra PRONOM PUID-er.

## På disk

Mens en jobb pågår eller har stoppet, finnes en katalog:

`<Work>/external_evidence/siegfried/.partial-<run-id>/`

Her lagres `session.json`, `file_inventory.jsonl`, `checkpoint.json` og `siegfried_files.jsonl`. **Ikke slett eller flytt `.partial-*` før du har bestemt om du skal fortsette kjøringen.** Resultatvisningene skjuler den med hensikt.

Ved 100 % får katalogen navnet `<Work>/external_evidence/siegfried/<run-id>/` og inneholder i tillegg `pronom_statistics.json` og `manifest.json`. `files_total`, `identified`, `unidentified`, `ambiguous` og `format_groups` beholder tidligere rapportkontrakt.

## Praktisk videreføring av 1502_024 som stoppet før a4

Den gamle v0.2.1-kjøringen stoppet **før** det ble skrevet et a4-kontrollpunkt. Siegfried må derfor starte fra første dokumentfil én gang med a4. De fem deljobbene som ble fullført før Siegfried er fremdeles lagret i Work.

I **Avansert modus**: velg jobben, marker deljobben `Siegfried – PRONOM filidentifikasjon`, og bruk **Kjør → Kjør valgt deljobb…** med eksisterende Source/Work. Dette omgår ikke andre kontroller, men unngår å starte XSD/XPath/Arkade Noark-jobbene på nytt bare for å komme frem til Siegfried. Ikke klikk «Kjør valgt jobb» på en jobb med status Feil og anta at de fem første operasjonene hoppes over: dagens workflow-runner kan starte hele listen på nytt. Selektiv kjøring gjenopptar bare Siegfried-operasjonens a4-kontrollpunkter; den markerer **ikke** automatisk resten av workflow (deljobb 7–10) som fullført. Disse må håndteres videre som egne kontroller eller i et senere forbedret workflow-gjenopptak.

På nye jobber brukes a4 automatisk når `Siegfried – PRONOM` er valgt. Etter et avbrudd kan Siegfried-deljobben startes på nytt for å gjenbruke kontrollpunkter, forutsatt at kildene ikke er endret.

## Validering og grenser

- 15 isolerte Python-tester: normal publisering, 205 faktiske testfiler i batcher på 100+100+5, syntetisk 250 001-filers inventar, feil etter første batch, kontrollert avbrudd, endret Source, endret sf-versjon, manipulert SHA-256, ugodkjent Work-identitet, symlenker, ufullstendig råhale og flere komplette kjøringer.
- Python-syntakskontroll bestått.
- Ingen 2 TB-kjøring eller faktisk Windows-`sf.exe` er kjørt i utviklingsmiljøet; forventet ressursbruk ved en slik kjøring er derfor ikke målt. SIARDs parallelle arbeidere er ikke innført i denne hurtigrettingen.
- Opptelling må kjøres på nytt for å verifisere at en tidligere delvis skanning fortsatt gjelder eksakt de samme filene. Dette innebærer filsystem-I/O, men gir ikke RAM-vekst proporsjonal med antall filer.
- Det finnes fortsatt en **600 sekunders tidsgrense per 100-filbatch**. Ved timeout bevares alle ferdige batcher; samme batch forsøkes igjen ved neste oppstart.
- Ufullstendige eldre `.partial-*` uten korrekt a4-kontrollpunkt gjenbrukes ikke, og slettes heller ikke automatisk.

## Endrede / nye filer

1. `noark5_workflow/operations/run_siegfried_pronom.py` (erstatter listebasert operasjon)
2. `noark5_workflow/operations/siegfried_stream_v022_a4.py` (ny strømming, kontrollpunkt, gjenopptakelse)
3. `tests/test_v022_a4_siegfried_large_resume.py` (ny regresjonstest)
4. `docs/SIEGFRIED-LARGE-BATCH-V022-A4.md` (denne dokumentasjonen)

**Ingen GUI, testversjon, jobbmodell, Arkade-/XPath-motor eller Source/Work-definisjon endres.** Dette er en avgrenset a4-delta over a3, ikke en release.
