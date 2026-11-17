# DWM v0.2.2-a5 – Parallell Siegfried med kildebundne kontrollpunkter

**Delta mot GitHub main `a4486b6b33c86f7858dc407e8909fdd47f3386e9` (v0.2.2-a4).**
Intern `VERSION` og distribusjonsversjon er oppdatert til `0.2.2-a5` / `0.2.2a5` i separat a5-versjonsdelta. Historiske tester og `test.bat` er uendret. Ingen Git-operasjoner er utført.

## Arkitektur: hva SIARD Workflow Manager faktisk gjør

Kontrollert mot `IKAMR/SIARD-Workflow-Manager` på GitHub:

- `siard_workflow/core/workflow.py`: Den ytre operasjonsløkken er sekvensiell.
- `siard_workflow/core/identifiers/siegfried.py`: `ThreadPoolExecutor` styrer flere samtidige **eksterne `sf`-prosesser** med 100 stier per batch, `sf -multi 64 -json` og en begrenset worker-pool (vanlig standard 4–16). Python bruker *tråder til prosessadministrasjon*, ikke en `ProcessPoolExecutor` for å beregne filformater.
- `siard_workflow/operations/blob_convert_operation.py`: Andre arbeidsoppgaver, blant annet dokument-/LOB-konvertering, har også egne tråd-/prosesspooler.
- `siard_workflow/operations/anonymize_operation.py`: Parallelle tabelloppgaver via `ThreadPoolExecutor`.
- `siard_workflow/operations/pipeline_operations.py`: ZIP-forhåndslesing med egen arbeidergrense (maks. 4).
- Flere adaptere benytter SIARDs felles konfigurasjonsverdi `max_workers`, men de bruker **ikke én felles prosesspool** som kjører alle workflow-operasjonene parallelt.

**Valg for DWM a5:** Parallell kjøring implementeres nå *kun* i Siegfried-adapteren. En senere, felles DWM-ressurspolicy kan samordne grenser for Siegfried, Arkade, filkopiering og andre tunge operasjoner, uten å dele prosesspool eller endre dagens sekvensielle Noark 5-arbeidsflyt.

## Kodeendring

1. `noark5_workflow/operations/siegfried_stream_v022_a4.py`
   - Beholder strømmende inventar, maksimal batchstørrelse 100, SHA-256, a4-kontrollpunkter og skjulte `.partial-*`-mapper.
   - Begrenset `ThreadPoolExecutor` med maksimalt N aktive `sf`-batcher; fremtidige batcher opprettes fortløpende, ikke i en ubegrenset futures-liste.
   - Resultater fra arbeidere skriver aldri direkte til Work. Kun koordineringstråden skriver JSONL, `fsync` og atomisk `checkpoint.json` **i opprinnelig filrekkefølge**.
   - Validerer filnavn per batch og reordner faktisk Siegfried-JSON til inventarordenen, også dersom `sf -multi` returnerer radene i annen rekkefølge.
   - Avbrudd eller feil stopper andre aktive prosesser og publiserer aldri en delvis kjøring som fullført.
   - A4-kontrollpunkter kan gjenopptas selv om arbeidertallet endres.
2. `noark5_workflow/operations/run_siegfried_pronom.py`
   - Bruker `siegfried_max_workers` fra runtime-innstillinger, med standard **2** og tillatt intervall **1–8**.
   - Legger antall konfigurerte arbeidere i `OperationResult` og evidensmanifest.
   - Beholder fremdriftstekstene fra tidligere versjoner slik at eldre test- og GUI-kontrakter består.
3. `tests/test_v022_a5_siegfried_parallel.py`: Tester parallellitet, faktisk `Popen` (POSIX testprogram), ordnet persistens, feil, avbrudd, gjenopptakelse og konfigurering.

## Endre antall samtidige Siegfried-prosesser

Standard er **2**. Dette er en bevisst konservativ startverdi for store uttrekk på eksterne disker; hver `sf`-prosess bruker fortsatt `-multi 64` internt. Økt parallellitet er ikke automatisk raskere ved treg lagring.

Valgfritt kan `config.json` i DWM-installasjonen inneholde:

```json
"siegfried_max_workers": 4
```

Dette er én nøkkel **inne i det eksisterende JSON-objektet** (ikke en separat JSON-fil). Gyldige verdier: `1`–`8`; `1` gir gammel sekvensiell kjøring. Endringen leses ved neste start av DWM. Det er foreløpig **ikke lagt til et nytt Qt-felt i Setup**, for å holde a5 avgrenset og unngå nye GUI-risikoer.

Ikke legg lokale `config.json`, jobblister, Source eller Work-filer i Git.

## Evidens og gjenopptakelse

En `sf`-prosess kan fullføre en senere batch før en tidligere batch. Den senere batchen **kan ikke** øke `files_processed` før alle foregående batcher er lagret. Ved stopp gjentas eventuelt allerede analyserte, men *ikke kontrollpunktlagrede* batcher. Det er forventet og hindrer både dobbeltelling og feil rekkefølge i råevidensen.

Ferdige kjøringer beholder:

- `external_evidence/siegfried/<run-id>/siegfried_files.jsonl`
- `external_evidence/siegfried/<run-id>/pronom_statistics.json`
- `external_evidence/siegfried/<run-id>/manifest.json`

Ufullstendige kjøringer ligger i skjult `.partial-<run-id>` under samme Work-område. Ferdige, historiske resultater skrives ikke over; originaluttakets `DOKUMENT` åpnes bare for lesing.

**Gjelder ikke:** Parallelle DWM-jobber, automatisk kjøring av deljobb 7–10 etter tidligere feilet arbeidsflyt, Arkade 5 eller andre verktøy. Disse er uendret.

## Test og installasjon

- Målrettede tester i utviklingsmiljøet: **10 nye a5 + 15 eksisterende a4 = 25 bestått**. Lokalt miljø har begrensede teststubber for øvrige DWM-moduler; Windows/PySide6 og ekte `sf.exe` er ikke testet her.
- Nytt testprogram starter flere virkelige lokale `sf`-lignende subprocesser på POSIX og måler tidsmessig overlapp; Windows-varianten tester prosessgrensen med mocker og må praktisk verifiseres.
- Pakk ut a5 ZIP-en **over committet a4**, fra repo-roten. Alle andre filer beholdes.
- **Ikke endre programfiler mens en jobb kjører.** La pågående `1543_012`-kjøring fullføre på a4 før a5 installeres.
- Test deretter en ny Siegfried-kjøring i valgt jobb/Work, og kontroller logglinjen som viser antall samtidige `sf`-prosesser, fullstendige PRONOM-resultater og manifest.
- For `1502_024` med eksisterende fem fullførte deljobber: velg selektiv **Siegfried – PRONOM** dersom du ikke vil kjøre tidligere analyser om igjen. Gjenopptakelse av a4-batcher innen Siegfried er uavhengig av workflow-cursoren.

Ingen originalfiler eller eksisterende Work-resultater inngår i ZIP-en. Ingen commit eller push gjort av assistenten.
