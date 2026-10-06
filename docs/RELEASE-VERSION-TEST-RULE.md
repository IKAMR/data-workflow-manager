# Releaseversjon og historiske alpha-tester

Denne regelen gjelder ved overgang fra siste alpha til ferdig release, for
eksempel `0.1.6-a39` til `0.1.6`.

## Fast regel

- `version.py` skal alltid inneholde den reelle applikasjonsversjonen. En ferdig
  release skal ikke få skjult alpha-versjon, ekstra kompatibilitetsvariabel eller
  kommentar for å tilfredsstille tester.
- Ferdig `X.Y.Z` er semantisk nyere enn alle `X.Y.Z-aNN` i samme release-serie.
- Historiske alpha-tester er regresjonsvern for funksjonene som ble innført i
  alpha-trinnene. De skal derfor fortsatt være gyldige etter at serien blir
  ferdig release.
- `test.bat` er den autoritative fulltesten før release. Den skal kjøres med den
  endelige release-versjonen i `version.py`.
- Testharnessen kan gi historiske alpha-versjonsvakter en test-only
  kompatibilitetsvisning av `version.py`. Denne visningen skal aldri skrives til
  produksjonsfilen og skal ikke endre `VERSION` som importeres av applikasjonen.
- Egen release-test skal kontrollere den fysiske `version.py` direkte og bekrefte
  at den bare inneholder den rene ferdige versjonen.
- Ved hver framtidig releasepromotering skal release-testen og full `test.bat`
  kjøres før delta leveres til bruker. En versjonsendring skal ikke overlates til
  brukeren som første sted der foreldede testforventninger oppdages.

Dette er en permanent testregel, ikke en release-cleanup-mekanisme i
produksjonskoden.
