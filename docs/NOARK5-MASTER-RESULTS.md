# Noark 5 masterresultater

Fra v0.1.3-a11 er premisset eksplisitt: **resultatene fra de individuelle Noark 5-testpunktene er master for videre operasjoner**.

## Master

Den ordinære Noark 5-testkatalogen kjører små, individuelle tester mot arkiv, arkivdel, klassifikasjonssystem, klasse, mappe, registrering, journalpost, dokumentbeskrivelse, dokumentobjekt og øvrige Noark 5-elementer. Hver test skriver sitt eget strukturerte JSON-resultat.

`master-results.json` er bare en indeks over disse filene. Den kopierer ikke og beregner ikke testverdier på nytt. Dette gjør at views, depotrapport og senere reconciliation kan peke tilbake til nøyaktig test-ID og original resultatfil.

## Ikke master

Følgende er kontroll-/sammenligningskilder og skal ikke overstyre individuelle masterresultater:

- historisk standard XPath-kjøring
- U1, samlet for hele uttrekket
- U2, per arkivdel
- utviklings-/regresjonskjøring mot U1/U2
- Arkade 5-rapporter
- andre eksterne testverktøy

Disse kan ha samme, delvis overlappende eller annen semantikk. Mapping og reconciliation skal derfor være eksplisitt og sporbar.

## U1 og U2

U1 og U2 ble laget ut fra tidligere tekniske behov ved XPath-kjøring: U1 ga samlet oversikt for hele uttrekket, mens U2 ga tilsvarende informasjon per arkivdel. U1 har naturlig også en kort oversikt over hvilke arkivdeler uttrekket inneholder.

Disse strukturene er fortsatt verdifulle som regresjons- og sammenligningsgrunnlag, men de er ikke beregningskilde for nye views eller rapporter når tilsvarende individuelle mastertester finnes.

## Arkade 5 og andre eksterne kilder

Arkade 5 behandles som ekstern evidens. En eksisterende Arkade 5-rapport kan importeres og normaliseres. Senere skal Workflow Manager også kunne kjøre Arkade 5 via CLI, hente den genererte rapporten og automatisk sammenligne relevante verdier mot de individuelle mastertestene.

Det samme mønsteret skal kunne brukes av andre eksterne testkilder.

## Materialisering

Ved ordinær `Noark 5-tester`-kjøring materialiseres:

```text
noark5_tests/xpath/<run>/
  index.json
  master-results.json
  results/
    kdrs_....json
```

`master-results.json` inneholder test-ID, status, Noark-entitet(er), kildefil og relativ referanse til den individuelle resultatfilen. Tester som ikke ga et tilgjengelig resultat beholdes som `master_test_unavailable`; de blir ikke silently behandlet som masterverdier.

En regresjonskjøring kan aldri materialiseres som masterresultatsett.
