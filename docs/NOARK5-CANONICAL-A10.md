# Kanonisk eksternresultatanalyse – v0.1.15-a10

## Formål

Bygge en eksplisitt, etterprøvbar bro fra eksterne resultatfiler i **valgt Work** til kanonisk dokumentasjon. Analysen er ikke teknisk eller depotfaglig godkjenning. `canonical-results.json` og `canonical-context.json` forblir uendret. Ingen rekursiv Source-skanning, ingen skjult automatisk kildevalg.

## Bruk

I GUI: **Rapport → Kanoniske resultatdata → Analyser eksterne resultater...**. Velg én eller flere eksisterende kildefiler i Work, bekreft opprettelse. Resultat: `noark5_evidence/canonical-external-analysis.json` med jobbindentitet, SHA-256 for kanonisk resultatindeks, individuelle Work-relative kildefiler og SHA-256, en begrenset tolkning per kilde og eksplisitt status for hva som ikke er verifisert.

## Støtte og grenser

- **Siegfried JSON**: Bare JSON med faktisk Siegfried-signatur og fil-/matchstruktur, gjenkjent av eksisterende a5-adapter. Tallene gjelder formatidentifikasjon, ikke integritet, Noark-samsvar eller godkjenning.
- **Arkade 5 normalisert JSON**: Filsti må slutte på `normalized/arkade5_results.json`, og JSON må inneholde en eksplisitt `tests`- eller `results`-liste med tekstfeltene `test_id` eller `id` og `status` per post. Bare ID og original statustekst registreres. Status oversettes **ikke** til OK/FEIL, bestått/ikke bestått eller avvik; skjemaet er ikke formelt verifisert mot brukerens rapportfil.
- **Arkade native XML / øvrige JSON og CSV**: Markeres `not_parsed`, også når filen er funnet i Work. Ingen oppdiktede resultater.
- Kildestier må ligge under valgt Work; filstørrelse, antall filer og poster er avgrenset. Eksisterende bevis endres ikke.

## Neste verifisering

Prøv først `external_evidence/arkade5/.../normalized/arkade5_results.json` og deretter en faktisk Siegfried JSON-fil hvis tilgjengelig. Dersom Arkade-resultatet merkes `not_parsed`, trengs et eksempel på den faktiske **maskinlesbare** resultatstrukturen, før vi kan lage en korrekt Arkade-adapter. Dette er tilsiktet sikker oppførsel, ikke grunn til å anta at testen feilet.

## Videre plan

1. Verifisere Arkade normalisert/oppstrøms skjema med faktiske filer og testdata; implementere detaljerte testposter med evidenslenker og eventuelle klare, dokumenterte statuser.
2. Koble eksterne resultater til versjonert kontrollprofil med konkret krav/test/evidens og vurdering av fullstendighet.
3. Bevare arkivskapers KS-bekreftelser, avklaringer og depotvedtak separat fra tekniske resultater.
4. Generere KS-rapport, godkjenningsrapport og deretter AIP med utvalgt evidens, manifest og sjekksummer.

Se også `docs/NOARK5-CONTROL-TO-PRESERVATION-ROADMAP.md` og `docs/DWM-BACKLOG-CONSOLIDATED.md` fra a4.

## Korrigert adapter mot virkelig Arkade 5-normalisering

`external_validation_report` format_version 2 identifiseres ved kildeformat, ikke bare filnavn. Testene leses fra `tests[]` med `test_id`, `source_status`, `number_of_errors` og `results[]`. For funn med `result_type=Error/Warning` beholdes melding, lokasjon og `result_set_path` (arkivdel). Original rapportert status endres ikke. Overordnet `summary` beholdes som oppgitt, og kan ikke tolkes som DWM-godkjenning.

`arkade5_pronom_format_statistics` format_version 1 leses fra `csv.rows[]` og beholder `Format-ID`, navn, formatversjon, `RAF-220301` og `Antall`. Summen er kun et rapportert filantall fra ekstern statistikk, ikke et dokumenttall som kan summeres med DWM.

Prøvemateriale 1525_004 viste 54 Arkade 5-tester, 52 med `source_status=ok` og to med `source_status=error` (N5.15 og N5.22). Den normaliserte PRONOM-statistikken hadde 12 rader og 704 rapporterte filer. Originaldata er ikke kopiert til repoet.

## Kildevelger (a10-korrigering)

Dialogen finner kjente resultater under `external_evidence`, `external_runs` og `arkade5_v2.13.1` med dybde- og antallsgrenser. Brukeren velger eksplisitt hvilke filer som skal inngå. Forrige kildesett for samme Work gjenkjennes fra `canonical-external-analysis.json`.

Velges både `normalized/arkade5_results.json` og `normalized/pronom_statistics.json`, inneholder samme eksterne analyse både individuelle Arkade-testposter og PRONOM-formatstatistikk. Dette er separate kildeobservasjoner og er ikke grunnlag for å summere testutfall og formatfunn som én kategori. Import erstatter den tidligere *avledede analysen*, men originalfilene endres ikke.
