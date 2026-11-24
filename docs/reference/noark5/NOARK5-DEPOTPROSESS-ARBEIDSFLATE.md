# DWM – samlet resultat- og depotprosess

**Grunnlag:** [Kodekart for resultatvisning og depotprosess](../../quality/RESULTATVISNING-AVVIK-OG-DEPOTPROSESS-KODEKART.md) fra 24.11.2026, mot v0.2.6 (`03342788`).
**Første implementasjon:** v0.2.7-a1. **Status:** utvikling, operatørtest gjenstår.

## 1. Mål

Gi en sammenhengende, kildebundet arbeidsflate fra teknisk kontroll til
faglig vurdering og rapportutkast, **uten** ny valideringsmotor, ny historikk
eller automatisk depotgodkjenning.

Beslutningsprinsippene er:

- **Kjøring:** deljobb fullført/stoppet, adskilt fra resultatet av en kontroll.
- **Evidens:** kilder finnes og er verifisert, adskilt fra faglig vurdering.
- **Funn:** tekniske eller menneskelig registrerte observasjoner; et funn er ikke et vedtak.
- **Faglig kommentar:** uforanderlig hendelse i eksisterende KS-register.
- **Depotvurdering:** separat registrering for uttrekk/arkivdel, med bruker og begrunnelse.
- **Rapport:** kildebundet utkast; en publisert HTML/CSV/JSONL-pakke er ikke et formelt vedtak.

## 2. Brukerprosess – trinnvis

| Trinn | Spørsmål for operatør | DWM-grunnlag og ønsket handling |
|---|---|---|
| 1. Velg | Hvilket uttrekk/Work vurderes? | Work-UID og valgt JOB, flere uttrekk støttes i Resultatvisninger |
| 2. Teknikk | Hva er utført, og hva ble rapportert? | A100–A200, teknisk status, kontrollnavn og kilde |
| 3. Evidens | Har vi dokumentasjon fra valgte kilder? | A210/A220/A230, manglende kilder med navn, ingen implisitt PASS |
| 4. Avvik | Hvor mange fullstendige, individuelle funn finnes? | A260 manifest + CSV/JSONL, verifisert mot originalrapport/A230 |
| 5. Undersøk | Hvilke XML-objekter og metadata gjelder funnet? | Eksisterende Veiledet KS, kilde/linje/M-nummer/Noark-versjon |
| 6. Vurder | Hvordan forklares og behandles hvert funn? | Eksisterende append-only vurderingshendelser, bruker og rapportmottaker |
| 7. Oppsummer | Hvordan vurderes uttrekk/arkivdel/periode? | Eksisterende depot- og periodejournaler; ikke automatisk propagasjon |
| 8. Rapporter | Hva deles med arkivskaper og depot? | Eksisterende komplett KS/depot-eksport; tydelig UTKAST |
| 9. Følg opp | Hva gjenstår etter avklaring? | Senere faglig krav til ansvar, svar, frist, lukking og journalhenvisning |

## 3. Hva v0.2.7-a1 faktisk leverer

Det legges til en **Depotkontroll**-fane i eksisterende **Resultatvisninger**.
Alle tidligere faner, vurderingsdialoger, eksterne kildevisninger og rapportbyggeren beholdes.

Depotkontroll viser en rad per uttrekk og en barnrad per arkivdel med:

- **Jobbens kjørestatus:** `job-state.json` for valgt Work, separat fra rapportstatus.
- **Teknisk status:** nøyaktig rapportert status, eller `Ukjent` ved manglende grunnlag.
- **Evidens A230:** faktisk A230-status, inkludert navn på manglende kilder.
- **Funn A260:** fullstendig totalantall kun når manifest, depotrapportens SHA-256,
  A230-SHA og begge eksportfilenes SHA-256 stemmer. Ingen beregning fra HTML-forhåndsvisning.
- **Faglig depotstatus:** lest fra eksisterende rapportversjonsbundne
  `depot_assessment.json` og `depot_assessment_parts.json`.
- **Kilde og advarsler:** Work-UID, grunnlagsrapport, usikre/manglende filer,
  eldre rapport som er valgt som fallback, og status for ikke-verifiserte kilder.

Operatøren kan gå direkte til **Veiledet KS**, **Depotvurdering** og
**Tekniske kontroller**. Veiledet KS åpner kun den aktivt valgte jobben
via eksisterende sikkerhetssjekk; depotfanen velger tilsvarende uttrekk eller
native arkivdel der det ordinære vurderingsgrunnlaget finnes.

Den nye lesemodellen ligger i `app/depot_process_v027_a1.py` og skriver
**ingen** filer. Qt-delen ligger i `gui_qt/depot_process_v027_a1.py`.
Arbeid med store rapporter og eksporthash utføres i bakgrunnstråd; GUI-en
viser at innlesing pågår i stedet for å oppgi feilaktige nullverdier.

### 3.1 Hva denne første versjonen ikke hevder

- Den erstatter **ikke** den eldre, størrelsebegrensede resultatsiden.
  Ved store depotrapporter kan Depotkontroll derfor ha grunnlag som ikke
  vises i de ordinære Arkivdeler-/Tekniske-kontroller-fanene.
- Individuelle funn og **nåværende** vurdert/ikke-vurdert-fremdrift vises
  fortsatt i **Veiledet KS**. A260-antallet er et verifisert register ved
  genereringstidspunktet, ikke en sanntidsindikator for faglig behandling.
- Det gis ikke egne funntall per arkivdel før en komplett, verifisert
  kobling av `archive_part_id` til funnregisteret er definert.
- Den viser ikke arkivskapers svar/frister eller en samlet avvikssak.
- Den produserer ingen beslutning, rapport eller ny vurderingsjournal.
- Det er ingen støtte for faglig redigering mens teknisk jobb kjører.

## 4. Kildekontrakter og kontroll av store rapporter

1. Autoritativ identitet er `job.json` sin `job_uid`; lokalt `JOB-001` er ikke unikt.
2. Originalrapport må ligge under valgt Work og ha `report_type=noark5_depot_validation`.
3. Små rapporter parses fra nøyaktig de bytene som hashes; filens metadata kontrolleres før og etter lesing.
4. Rapporter over ordinær visningsgrense bruker **eksisterende** `project_depot_report()`
   (`qa_depot_stream_v023_a17.py`) med `ijson`, ingen ny XML-/XPath-parser.
5. Nyeste ugyldige rapport kan ikke stilletiende erstattes av en eldre;
   fallback markeres eksplisitt i Depotkontroll.
6. A230-metadata kontrolleres mot Work-UID, og `missing_expected_sources`
   vises med faktisk listen over manglende kilder.
7. A260-tall vises bare med eksakt matching rapport-SHA, A230-SHA,
   A260-manifest og komplette JSONL-/CSV-bytehasher.
8. Vurderingsjournalene kontrolleres mot original rapportrevisjon; ved
   SHA-avvik vises **kontroller rapportrevisjon**, ikke en gjeldende vurdering.
9. Manglende/duplisert `archive_part.system_id` kan ikke brukes til en
   gjeldende arkivdelvurdering.
10. `Ukjent` betyr **ikke** `0`, og teknisk `ok` betyr **ikke** depotgodkjent.

## 5. Eksisterende API-er som er gjenbrukt

| Ansvar | Modul |
|---|---|
| Work-utvalg | `app/result_evidence_v018_a13.py:open_work_job` |
| Søk etter kjente rapportfiler | `app/result_center_v018_a12.py:discover_results` + avgrenset Work-søk |
| Stor depotrapport | `noark5_workflow/reporting/qa_depot_stream_v023_a17.py:project_depot_report` |
| Eksisterende evidens | `noark5_evidence/evidence-audit.json` fra A230 |
| Komplett funnregister | `noark5_evidence/qa-basis-draft.json` + A260 `manifest.json` |
| Uttrekksvurdering | `noark5_workflow/analysis/depot_assessment.py:load_depot_assessment` |
| Arkivdelvurdering | `app/depot_review_v019_a2.py:load_part_decisions` |
| Veiledet KS | `gui_qt/main_v023_a4.py:_a12_open_ks_workshop` |
| Depotvurdering | `gui_qt/depot_review_v019_a2.py:DepotReviewPanel` |
| Navigasjon mellom resultatfaner | `gui_qt/result_navigation_v020_a6.py` |

## 6. Tester i første inkrement

`tests/test_v027_a1_depot_process.py` dekker blant annet:

- Manglende rapport er ukjent, ikke null/godkjent.
- Eget heluttak og separate native arkivdeler.
- Duplisert system-ID hindrer entydig arkivdelbeslutning.
- Arkivdelaksept blir ikke automatisk heluttakaksept.
- A230 viser `arkade_pronom` som manglende og avviser feil Work-UID.
- Jobbstatus fra `job-state.json` holdes adskilt fra eldre teknisk depotrapport.
- A260-total vises bare med gyldig manifest og originale kildehasher.
- A260 endret CSV/JSONL eller annen rapportrevisjon merkes som uverifiserbar.
- Utrygge evidensstier og symlenker avvises.
- Strømmeleseren brukes for rapporter over den eldre visningsgrensen.
- Eldre rapportfallback blir synlig og identiske Work-UID-er telles én gang.
- Ny Qt-inngang og `v0.2.7-a1`-versjon er tilkoblet.

### 6.1 Lokal akseptansekontroll

Kjør fra repo-roten i Git Bash på Windows:

```bash
py -m unittest tests.test_v027_a1_depot_process -v
MSYS_NO_PATHCONV=1 cmd.exe /c test.bat
```

Bekreft i GUI med minst ett lite og ett stort Noark 5-uttrekk:

- Åpne `Resultatvisninger` -> gruppe `Oversikt` -> `Depotkontroll`.
- Se samme Work/uttrekk som i hovedvinduet og velg én arkivdel.
- Kontroller at A230-mangler oppgis med kildenavn.
- Kontroller at A260-antall ikke vises når manifest/hashes er feil.
- Åpne Veiledet KS og Depotvurdering; ingen tidligere deljobber skal kjøres om igjen.
- Bekreft at tidligere vurderinger, originalrapport og Source er uendret.

**Begrensning:** Denne dokumentasjonen bygger på statisk kodeanalyse og
målrettede lokale enhetstester. Windows/Qt-operatørtest og full `test.bat`
kreves før funksjonen kan regnes som praktisk verifisert.

## 7. Neste kodeinkrementer – ikke implementert i a1

**A2 – komplett, filterbar avvikskø i samme arbeidsflate.** Gjenbruk den
SHA-bundne SQLite-indeksen fra `qa_paged_review_v023_a12.py`, filtrer på
ERROR/WARNING/REVIEW, kilde, vurdert/ikke vurdert, og drill ned til
XML-evidens uten ny journal. Vis også riktig total per arkivdel bare når
funnene har verifisert native arkivdelidentitet.

**A3 – sammenhengende navigasjon og arbeidskontekst.** Samme valgt
uttrekk, arkivdel, funn-ID og filter ved overgang fra Depotkontroll til
Veiledet KS, Periodevurdering, Depotvurdering og Rapportutkast. Undersøk
funksjonelt samspill med allerede eksisterende GUI i stedet for å opprette
enda ett konkurrerende KS-vindu.

**A4 – oppfølging av avvik med arkivskaper.** Definer først på depotfaglig
nivå hva en avvikssak skal inneholde: avsendt spørsmål, mottatt svar,
ansvarlig, frist, restavvik, kilde-/revisjonsbinding og ekstern
saks-/journalreferanse. Avklar regler for lukking og gjenåpning før det
innføres ny vedvarende saksmodell.

**A5 – samlet rapport-/beslutningsgrunnlag.** Presenter eksplisitte valg
for mottaker, fullstendighet, rapportrevisjon og faglig innstilling. Bruk
eksisterende `export_complete_reports`; hold rapportutkast og formelle
beslutninger/vedtak strengt adskilt.

## 8. Ikke berørt

Originale Noark 5-uttrekk, Work-journalene, tidligere rapporter,
A100–A260-kjøring, Arkade 5, Siegfried, KDRS Query, XSD/XPath,
resultatversjoner, depotprofiler og nåværende KS-/rapporteringskontrakter.

**Ingen GitHub-commit eller push utføres av denne deltaen.**
