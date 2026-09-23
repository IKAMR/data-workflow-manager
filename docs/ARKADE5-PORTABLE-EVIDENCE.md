
# Arkade 5 – portabel evidenspakke

Fra v0.1.5-a8 kan Data Workflow Manager eksportere all importert Arkade 5-evidens
for ett uttrekk som en selvstendig ZIP-pakke. Fra v0.1.5-a11 følger også komplett
statisk gap-/overlappkunnskap og gjeldende dekningspolicy med pakken.

## Formål

Pakken skal kunne leses av DWM, revisjons-/depotverktøy og andre prosjekter uten
å være avhengig av GUI-et eller den opprinnelige `work_operations`-strukturen.

Eksporten endrer ikke betydningen av dataene:

- Arkade 5 er ekstern evidens.
- Arkade-resultater blir ikke DWM-masterresultater.
- Et likt N5-testnummer innebærer ikke automatisk semantisk ekvivalens.
- `partial` og `complementary` beholder begge kilder.
- Dokumenterte DWM-gap kan dekkes av Arkade uten intern DWM-reimplementering.
- Pakken gjør ingen automatisk depotgodkjenning eller avvisning.

## Pakkeinnhold

Roten inneholder:

- `manifest.json` – teknisk pakkemanifest med formatversjon, prinsipper,
  importgrupper og SHA-256/filstørrelse.
- `README.md` – kort menneskelesbar forklaring.

`knowledge/` inneholder:

- `arkade5_test_catalog.json`
- `dwm_arkade5_mapping.json`
- `combined_coverage_model.json`
- `gap_overlap_model.json`
- `arkade5_coverage_policy.json`

`analysis/` inneholder:

- `gap_overlap_analysis.json` – materialisert statisk implementasjonsanalyse.
- `coverage_policy_validation.json` – kontroll av at policy og gapmodell stemmer.

For hver import-ID:

- `imports/<id>/source/<originalfil>` – original bevart Arkade-rapport.
- `imports/<id>/normalized/arkade5_results.json` – tapsfri DWM-normalisering.
- `imports/<id>/reconciliation/arkade5_dwm_reconciliation.json` – når
  reconciliation finnes.
- `imports/<id>/combined_coverage.json` – faktisk coverage mot DWM-testene i
  depotrapporten brukt ved eksport.
- `imports/<id>/import_manifest.json` – portabel kopi av importmanifestet.

## Statisk analyse versus kjøring

`analysis/gap_overlap_analysis.json` beskriver hva DWM og Arkade er dokumentert
å implementere.

`imports/<id>/combined_coverage.json` beskriver hva som faktisk finnes av
evidens i den konkrete importen/kjøringen.

Disse må ikke blandes.

## Sporbarhet

`manifest.json` registrerer SHA-256 og filstørrelse for alle eksporterte
nyttefiler. Kunnskapsfilene er faktiske kopier av filene i aktiv DWM-versjon,
slik at den semantiske tolkningen følger evidenspakken.
