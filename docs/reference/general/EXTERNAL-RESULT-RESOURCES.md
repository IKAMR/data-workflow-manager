# Eksterne testresultater som resultatressurser

Eksterne testresultater materialiseres som en ressursbank.

Hver ekstern rapport eller kjøring beholdes som egen kildegruppe. To Arkade 5-
rapporter med 54 tester hver vises derfor som to separate grupper med 54
resultater hver, ikke som én anonym liste på 108 rader.

Per gruppe beholdes blant annet:

- kildeverktøy og versjon,
- testdato når kilden oppgir den,
- import-ID,
- SHA-256,
- kildefil,
- antall tester og feil/advarsler når kilden oppgir dem,
- normaliserte testresultater.

Den flate `resources`-listen beholdes i JSON for maskinell behandling, mens
`groups` er den eksplisitte kilde-/kjøringsstrukturen.

Eksterne resultater kan supplere DWM-dekning, men overstyrer aldri DWM sine
autoritative interne masterresultater.

## Arkade 5

Når et arbeidsområde har flere importerte Arkade 5-rapporter, viser
`Testdekning...` en valgliste før dekningen åpnes. Brukeren velger eksakt
rapport/kjøring etter testdato, import-ID og kilde. Én import åpnes fortsatt
direkte.

## KDRS Query

Fra v0.1.7-a2 kan historiske tekstresultater fra KDRS Query / XML Queries
importeres for den aktive jobben som ekstern evidens. Importen startes fra
jobbens hovedbilde, ikke fra flerjobb-handlingsdialogen. Importen støtter inntil
én fil av hver type i samme kildegruppe:

- standard XPath-output,
- U1 / U01 for hele uttrekket,
- U2 / U02 per arkivdel.

Alle KDRS Query-filer lagres under jobbens effektive DWM-workområde: først
Setup sin `app_work_subfolder` (standard `dwm`), deretter eventuell ekstra
jobbliste-undermappe. Originalfilene kopieres uendret til
`external_evidence/kdrs_query/<import-id>/source/` under dette området. Hver fil normaliseres til
JSON under `normalized/`, og en `manifest.json` binder kildefil, SHA-256,
rapporttype og normalisert fil sammen.

Standardrapporten kobler gjenkjente historiske `job_id`/N5-testpunkt til DWM
sin XPath-katalog 2026. U1 og U2 beholdes som historisk/regresjonsbasert
referanse. U2 forsøkes samtidig delt i eksplisitte arkivdelseksjoner. Alle
kildelinjer beholdes i de normaliserte resultatene også når en linje ikke kan
mappes til et individuelt DWM-testpunkt.

Definisjonsgrunnlaget som importen refererer til er:

- `docs/reference/kdrs-query/xml-queries_noark5_2026-05-26.txt`
- `docs/reference/kdrs-query/xml-queries_noark5_2026-05-26_U1.txt`
- `docs/reference/kdrs-query/xml-queries_noark5_2026-05-26_U2.txt`

KDRS Query-data legges også inn i `external_evidence/result-bank.json` som
eksterne resultatressurser. En mapping til samme DWM test-ID er ikke det samme
som at verdiene er verifisert som like; eksplisitt reconciliation er et eget
lag og eksterne resultater gjør aldri et feilet eller manglende DWM-masterresultat
til et internt OK-resultat.
