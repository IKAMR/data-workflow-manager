
# Arkade 5 – portabel evidenspakke

Fra v0.1.5-a8 kan Data Workflow Manager eksportere all importert Arkade 5-evidens
for ett uttrekk som en selvstendig ZIP-pakke.

## Formål

Pakken skal kunne leses av DWM, revisjons-/depotverktøy og andre prosjekter uten
å være avhengig av GUI-et eller den opprinnelige `work_operations`-strukturen.

Eksporten endrer ikke betydningen av dataene:

- Arkade 5 er ekstern evidens.
- Arkade-resultater blir ikke DWM-masterresultater.
- Et likt N5-testnummer innebærer ikke automatisk semantisk ekvivalens.
- `partial` og `complementary` skal beholde begge kilder.
- Pakken gjør ingen automatisk depotgodkjenning eller avvisning.

## Pakkeinnhold

Roten inneholder:

- `manifest.json` – teknisk pakkemanifest med formatversjon, prinsipper,
  importgrupper og SHA-256/filstørrelse for eksporterte filer.
- `README.md` – kort menneskelesbar forklaring.
- `knowledge/arkade5_test_catalog.json` – kildekodeverifisert Arkade 5 v2.13.0
  Noark 5-testkatalog.
- `knowledge/dwm_arkade5_mapping.json` – kvalitetssikret DWM ↔ Arkade-mapping.
- `knowledge/combined_coverage_model.json` – modell for samlet dekningsstatus.

For hver import-ID:

- `imports/<id>/source/<originalfil>` – original bevart Arkade-rapport.
- `imports/<id>/normalized/arkade5_results.json` – tapsfri DWM-normalisering.
- `imports/<id>/reconciliation/arkade5_dwm_reconciliation.json` – når
  reconciliation finnes fra importen.
- `imports/<id>/combined_coverage.json` – combined coverage mot DWM-testene
  som finnes i depotrapporten brukt ved eksport.
- `imports/<id>/import_manifest.json` – portabel kopi av importmanifestet.

## Sporbarhet

`manifest.json` registrerer SHA-256 og filstørrelse for alle nyttedata i pakken.
Original Arkade-rapport har i tillegg den opprinnelige importens SHA-256 i
importmanifestet.

Kunnskapsfilene eksporteres som faktiske kopier av filene som ligger i den
aktive DWM-versjonen. Dermed følger den semantiske tolkningen resultatpakken.

## Videre bruk

Andre prosjekter bør:

1. lese `manifest.json`,
2. bruke `knowledge/arkade5_test_catalog.json` for hva Arkade-testen betyr,
3. bruke `knowledge/dwm_arkade5_mapping.json` for relasjonen til DWM,
4. lese original og normalisert Arkade-resultat som separate lag,
5. ikke anta ekvivalens ut fra N5-nummer alene.
