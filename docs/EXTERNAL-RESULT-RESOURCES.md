# Eksterne testresultater som resultatressurser

A13 materialiserer importerte eksterne testresultater som en ressursbank.

Hver ekstern rapport eller kjøring beholdes som egen kildegruppe. To Arkade 5-
rapporter med 54 tester hver vises derfor som to separate grupper med 54
resultater hver, ikke som én anonym liste på 108 rader.

Per gruppe beholdes blant annet:

- kildeverktøy og versjon,
- testdato,
- import-ID,
- SHA-256,
- kildefil,
- antall tester og feil/advarsler fra kilderapporten,
- alle normaliserte testresultater.

Den flate `resources`-listen beholdes i JSON for maskinell behandling, mens
`groups` er den eksplisitte kilde-/kjøringsstrukturen.

Eksterne resultater kan supplere DWM-dekning, men overstyrer aldri DWM sine
autoritative interne masterresultater.


## Testdekning ved flere Arkade 5-importer

Når et arbeidsområde har flere importerte Arkade 5-rapporter, viser `Testdekning...` nå en valgliste før dekningen åpnes. Brukeren velger eksakt rapport/kjøring etter testdato, import-ID og kilde. Én import åpnes fortsatt direkte.
