# XPath-regresjon: resultatkontrakt og feiltilstand

**Gjelder:** Data Workflow Manager, A190 / `run_noark5_xpath_regression_2026`.
**Oppdatert:** v0.2.7-a16.

## Problem observert i stort uttrekk

Ved `1502_024` ble 60 av 60 XPath-tester forsøkt, men mange ga teknisk `error`.
Den eldre regresjonsaggregatoren antok at `kdrs.u02` alltid inneholdt `values`
og brukte `u02["values"]` uten statuskontroll. En test som ga `status=error`
uten `values` utløste `KeyError: 'values'` etter testløpet. Dette er en feil i
regresjonsaggregatoren; det betyr **ikke** at de underliggende testfeilene er
rettet eller at Noark-kravene er oppfylt.

## Kontrakt etter a16

- Hver individuell test beholder opprinnelig `status`, `error` og eget resultat-JSON.
- Aggregering bruker bare `values` fra en faktisk tilgjengelig dict og gyldig
  resultatstatus. Feilstatus blir `not_comparable`, ikke null eller match.
- Ved utilgjengelig `kdrs.u02` lagres `archive_part_reference` med konkret
  årsak, mens `archive_parts` er tom. Tomme arkivdelresultater må aldri tolkes
  som at uttrekket ikke har arkivdeler.
- Sammendraget er `review` når referansen mangler; det blir aldri `match`
  bare fordi sammenligningslisten ble tom.
- `legacy-regression-comparison.json` og `index.json` skal kunne publiseres
  etter fullført testkatalog også ved ikke-sammenlignbare resultater.
- A190 returnerer teknisk feil når katalogen inneholder testresultater med
  `status=error`, men beholder alle lagrede resultater i Work for feilsøking.
- Ved en **motorfeil** i katalog/aggregator skrives `runner-error.txt` med
  traceback i kjøringens Work-mappe. Feiltypen og stien vises i kjørelogg.
- Korrekt fortsettelse forblir fra A190 så lenge operasjonen har teknisk feil.
  Tidligere A100–A180-resultater skal ikke nullstilles.

Dette skillet gjelder **teknisk kjøring og regresjon**, ikke depotgodkjenning.

## Gjenstående arbeid

1. Finn årsaken til de individuelle A190-testfeilene i `results/*.json` og
   `performance-diagnostics.json`; a16 håndterer resultatfeilen, ikke nødvendigvis
   ressursproblemet eller alle XPath-uttrykkene i et 4,4 GB XML-dokument.
2. Vurder ressursbegrensninger og om regresjonskjøringen skal være valgfri i
   ordinær produksjonsprofil, etter egen beslutning og regresjonstest.
3. Kjør syntetisk test, full `test.bat` på Windows, og praktisk fortsettelse
   med samme jobb fra 8/17.
4. I Avansert modus er splitterhåndtaket mellom historikk og lagret jobbstatus
   gjort synlig med eget stilmål. Ingen andre paneler eller lagrede størrelser
   skal endres.

## Kode

- `noark5_workflow/analysis/legacy_regression.py`
- `noark5_workflow/analysis/xpath_test_engine.py`
- `noark5_workflow/operations/run_noark5_xpath_tests.py`
- `gui_qt/advanced_splitter_v027_a16.py`
- `tests/test_v027_a16_xpath_regression.py`
- `tests/test_v027_a16_splitter_and_wiring.py`
