# Noark 5: kanonisk resultatmodell i Work

## v0.1.15-a1: implementert første kontrakt

`noark5_workflow.analysis.canonical_results` kan materialisere en **lokal, kildesporbar resultatprojeksjon** fra eksplisitt valgte DWM-masterindekser, råresultatlogg og/eller ekstern resultatbank i **samme jobb-Work**. Ingen kildefiler flyttes, normaliseres i stedet for originalene eller oppdateres. Dette er et første maskinlesbart datagrunnlag, ikke ferdig rapportmotor, samlet kvalitetsstatus eller depotgodkjenning.

**Bevart rollefordeling:** Individuelle ordinære DWM-tester er master for egne verdier. `master-results.json` er fremdeles en indeks. DWM-råresultater har egen, historisk append-only-logg. Arkade 5 og KDRS Query er *ekstern evidens* og får ikke intern masterrolle. Faglige vurderinger ligger fortsatt i separat Work-ledger.

### Støttede input

- Eksisterende autoritativ DWM-jobb i valgt Work: `job.json` (`job_uid`).
- En eller flere eksplisitt angitte `master-results.json` fra ordinær individuell Noark 5-testkjøring, med referanser til de individuelle JSON-resultatene.
- Valgfri `wf/results/raw-results.jsonl`, eksplisitt valgt.
- Valgfri versjon 2 `result-bank.json`, eksplisitt valgt, med Arkade 5/KDRS Query-ressurser.

Det gjøres **ikke** rekursiv scanning, ingen automatisk inkludering av eldre resultater, og ingen import fra eksterne mapper. Alle input må være under valgt Work. Manglende input betyr *ukjent / ikke representert*, ikke null og ikke godkjent.

### Lagret resultat

`<valgt jobb-Work>/noark5_evidence/canonical-results.json`

Resultatfilen har `schema_version: "1.0"` og `model_id: "noark5.canonical-results.v1"`. JSON Schema ligger i `config/noark5/canonical_results_v1.schema.json`. Hver observasjon har UUIDv5, kildekategori, test-ID, tilgjengelighet, status, eksplisitt masterrolle og evidenslokator i Work. Individuelle resultater refereres med relativ sti og SHA-256. Råresultater refereres via sin `result_id`; eksterne via `resource_id`. Normaliserte skalarverdier fra DWM-mastertester kan vises, men *kan ikke summeres statistisk uten kontroll av definisjoner og overlapp*.

`extraction.stable_id` er foreløpig **varig DWM-jobb-UUID**, ikke verifisert hash for arkivuttrekket. Arkiveier, arkivskapere, leverandør/system og Noark-versjon står `null` inntil kildebelagt uthenting implementeres. Historiske kjøringer med samme test-ID beholdes som ulike kilder, uten feilaktig summering. Metadata-ID `M300` og regler er foreløpig ikke automatisk utledet av KDRS-test-ID-er.

For hvert kall bygges et nytt komplett øyeblikksbilde av bare de eksplisitte inputene. Filen erstattes atomisk. Dette er **ikke** append-only kildelogg, og tidligere øyeblikksbilder kan arkiveres separat ved senere behov. Rå evidens og vurderingshistorikk berøres ikke.

### Kjøring (frivillig, uten GUI-endringer)

Fra repo-roten, med en eksisterende Work-jobb og en faktisk masterindeks:

```powershell
py -m noark5_workflow.analysis.canonical_results --work "I:\arkiv-noark5\1525\1525_004_E-1525-2025-0001\repository_operations\dwm2\a03" --master "noark5_tests\xpath\RUN-XXXX\master-results.json" --dry-run
```

Fjern `--dry-run` når indeksplassering og oppsummering er kontrollert. Legg eventuelt til `--raw "wf\results\raw-results.jsonl"` og `--external-bank "<relativ sti til result-bank.json>"` når filene finnes i samme Work. **`RUN-XXXX` er et eksempel som må erstattes med en reell undermappe.** DWM skriver ikke data i Source.

### Ikke ferdig i a1

Automatisk GUI-materialisering, skalerbar indeks over mange uttrekk, rapportadaptere, bevaring/godkjenning, sammenligning, aggregerte statistikker, kildebelagt uttrekksidentitet, dokumentlenker og utvidet metadata-ID-/regeltilknytning. Disse bygges videre på den lokale kontrakten etter brukerens test av a1. Ingen sentral synkronisering eller GitHub-publisering av data.
