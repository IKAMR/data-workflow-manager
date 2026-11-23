# Teststatus v0.2.2-a1.1

Delta over v0.2.2-a1, uten endring av programversjon eller produksjonskode.

- Feillogg fra Windows viste 3918 tester, 10 feil, 20 hoppet over: fem
  historiske v0.2.1-versjonslåser og fem feil i ny overgangstest.
- Hele den opprinnelige teksten i hver av de fem berørte testfilene ble
  rekonstruert fra Windows-loggens `assertIn`-feil og bevart.
- Fem versjonslåser ble erstattet med `assert_release_at_least(...)`;
  hver fil fikk nøyaktig én fjernet assert og én import + én ny assert.
- Den nye v0.2.2-versjonstesten er endret slik at senere alphaer og
  ferdige releaser godtas uten å endre funksjonelle kontroller.
- Lokal validering: AST for alle modifiserte filer, diffs for fem
  historiske tester, milepælsgrenser samt targeted versjonstester.
- Full `test.bat` kan ikke kjøres i dette miljøet uten komplett
  DWM-repo og Windows-/Qt-integrasjoner. Dette gjenstår hos operatøren.

Dette deltaet inneholder ferdig korrigerte filer. Kjør **`test.bat`**
direkte. Ikke kjør et ekstra installasjonsskript.
