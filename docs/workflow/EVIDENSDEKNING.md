# A210/A230: kildebundet Arkade PRONOM-evidens i v0.2.6

## Feil og årsak

Ved flere Arkade-importer i samme Work valgte A210 tidligere bare det siste
Arkade Noark-manifestet. A160 kan ha koblet PRONOM-statistikken til et annet,
eldre manifest. Da kunne A160 fullføres og A220 behandle to kilder, mens A230
stoppet med `missing_expected_sources: arkade_pronom`. Dette er en
kildekoblingsfeil, ikke en dokumentert XPath- eller parsergrense.

## Rettet atferd

- A210 beholder den nyeste validerte Noark-importen og kan hente PRONOM-statistikk
  fra en annen, verifisert import med *samme jobb-ID og Work*.
- Ekstra PRONOM-kilde godtas bare når normalisert statistikk, bevart CSV,
  importmanifest og den opprinnelige Arkade Noark-rapporten er SHA-256-verifisert.
  Et `A160 OK` alene er ikke tilstrekkelig bevis.
- A230 for eksisterende stoppede jobber kontrollerer først tidligere A210/A220.
  Når **bare** `arkade_pronom` mangler og kontrollert, entydig eldre evidens
  finnes, oppdateres **avledede** A210/A220-filer og revisjonen gjennomføres
  på nytt. Tidligere versjoner bevares under `noark5_evidence/history/`.
- Gjenkoblingen kjører ikke A100–A220-operasjonene, Arkade 5 CLI eller
  Siegfried på nytt, og endrer ikke jobbmarkør, Source eller originale
  eksterne resultatfiler. Oppdatert A230-rapport viser kildesti og hash.
- Manglende, tvetydig, korrupt eller feiltilknyttet PRONOM blokkerer fortsatt
  A230. Meldingen gir en konkret årsak og `evidence-audit.json` registrerer
  `missing_source_reasons`. Ingen automatisk faglig godkjenning.

## Avgrensninger og kontroll

Gjenkobling utføres bare når det lagrede A220-resultatet er konsistent med den
opprinnelige kanoniske A210-referansen. Et annet avvik krever egen faglig
undersøkelse; A230 hopper ikke over kontrollen. Ved uventet feil under
oppdatering forsøkes tidligere avledede A210/A220-filer tilbakeført.

Regresjonstester: `py -m unittest discover -s tests -p "test_v026_a3*.py" -v`.
Full `test.bat` og Windows-/Work-test kreves før commit. Test et Work med
flere Arkade-importer, et uten verifisert PRONOM og et med endret CSV-hash.
En stoppet jobb kan fortsette fra A230 med den ordinære **Fortsett**-handlingen
når programmet er oppdatert, uten å nullstille jobben eller kjøre A100–A220 om igjen.
