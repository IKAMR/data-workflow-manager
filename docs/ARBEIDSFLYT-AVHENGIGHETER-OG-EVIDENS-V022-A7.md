# DWM v0.2.2-a7 - avhengighetsnummer og kanonisk evidens

## Leveranse og grunnlag

Denne deltaen legges oppå **v0.2.2-a6**. Endringene omfatter Noark 5-profilene, en felles avhengighetsmodell, fire Work-baserte deljobber, GUI-handlinger for eldre fullførte jobber og regresjonstester. Ingen Git-operasjoner gjennomføres.

## Stabile avhengighetsnummer

Et `Axxx`-nummer betegner en fast operasjons-ID, **ikke** posisjonen i jobblisten. `follows` refererer til nummeret for deljobber som må komme tidligere dersom begge er valgt. `required` identifiserer deljobber som må være til stede i en a7-pipeline. Tabellen ligger maskinlesbart i `app/workflow_dependencies_v022_a7.py`.

| Nummer | Operasjon | Viktigste avhengigheter |
| --- | --- | --- |
| A100 | Metadataoversikt | Ingen |
| A110 | XML/XSD | Ingen |
| A120 | Analyse av arkivstruktur | Ingen |
| A130 | DWM Noark 5 XPath | Ingen fast rekkefølge mot A100-A120 |
| A140 | Siegfried PRONOM | Ingen fast rekkefølge mot A100-A130 |
| A150 | Arkade 5 Noark 5 | Ingen fast rekkefølge mot A100-A140 |
| A160 | Arkade 5 PRONOM | Ingen fast rekkefølge mot A100-A150 |
| A170-A190 | Historiske/utvidede DWM-tester | Uavhengige i eldre profiler |
| A200 | Import av Arkade-evidens | A150 og A160 dersom valgt |
| A210 | **Bygg kanonisk Noark 5-evidens** | A130, A140, A150, A160, A200 dersom valgt; A130 kreves |
| A220 | **Koble og analyser ekstern evidens** | A210 kreves |
| A230 | **Kontroller evidensdekning** | A210 og A220 kreves |
| A240 | Resultatvisninger | A130 og A230 dersom valgt |
| A250 | Depotvalideringsrapport | A130, A200, A230 og A240 dersom valgt |
| A260 | **Forbered KS-grunnlag som UTKAST** | A230 og A250 kreves |
| A900 | DIAS/SIP-pakking | Separat fase; A260 foran dersom deljobben er med |

Det er altså fortsatt fritt å endre rekkefølge mellom de tekniske kontrollene. Knappen **Arkade-testene sist** plasserer A150 og A160 sist *blant tekniske tester*, men foran A200-A260.

## Fire nye deljobber

- **A210:** Lager `noark5_evidence/canonical-results.json` fra riktig Work-jobbs kontrollerte XPath-master. Inneholder kildebelagte referanser til eksisterende Arkade/Siegfried-evidens, uten å gjøre dem til DWM-mastertester.
- **A220:** Kobler eksplisitt de normaliserte eksterne Work-resultatene til riktig kanonisk SHA-256 og lagrer `canonical-external-analysis.json`. DWMs `pronom_statistics.json` fra Siegfried tolkes som formatstatistikk med identifiserte/uidentifiserte filer, aldri som arkivgodkjenning. Manglende resultater blir ikke fremstilt som null tester.
- **A230:** Kontrollerer jobbidentitet, hash og dekning og lagrer `evidence-audit.json` inkludert en liste over avhengighetsnummer og deres forutsetninger. Mangler det evidens for en kontroll som faktisk ble valgt, feiler deljobben.
- **A260:** Lager `qa-basis-draft.json` og `qa-basis-draft.html` i Work. Begge er tydelig utkast; dette er ikke den separat publiserte fullstendige a3 KS/depotrapportpakken, og ikke depotgodkjenning.

Tidligere versjon av kanonisk JSON og ekstern analyse lagres med SHA-256-navn under `noark5_evidence/history/` før ny publisering. Source og den tekniske Work-evidensen forblir uendret.

## Eksisterende jobber som 1525_004-006

Gamle jobber oppgraderes **ikke automatisk ved å åpnes eller lagres**. Naar en fullført Work-jobb er valgt, bruk **Legg til a7-etterbehandling...** i Kjør-menyen (Avansert) eller steg 3 (Enkel). Etter bekreftelse settes jobben til Klar, men cursor plasseres etter tidligere fullførte tekniske tester. Start vanlig arbeidsflyt for å kjøre A200-A260; XML, XPath, Siegfried og Arkade kjøres ikke om igjen.

Dette krever autoritativ Work-jobb og en tidligere fullført, eller helt ny, kontroll. Feilet eller delvis avbrutt arbeidsflyt kan ikke automatisk oppgraderes. Gamle rapporter beholdes. Jobblisten og Work oppdateres med eksisterende API etter brukerens valg.

## Sikkerhet og datakvalitet

- Ingen kryssbruk av Source/Work eller JOB-ID, og varig Work-jobb-UUID kontrolleres mot XPath-artifakter.
- Alle eksterne kilder er Work-lokale og sjekkes mot opprinnelig kildehash. Flere historiske XPath-kjøringer med uklar versjon avvises.
- Ekstern evidens blir aldri automatisk markert som bestatt Noark 5-krav. Manglende resultat betyr ukjent, ikke null.
- Eldre 10-deljobbsdefinisjoner blir ikke migrert i det skjulte.
- Både GUI-redigering, Workbench API og JobRunner fanger ugyldig rekkefølge. Selektiv deljobbkjøring krever også at avhengighetenes tidligere operasjoner ligger i den fullførte workflow-delen. A7 endrer ikke selve Siegfried-motoren eller a5-flerprosesseringen.

## Verifikasjon og begrensninger

56 målrettede tester bestod i utviklingsmiljoet. De tre ekte ZIP-ene for 1525_004, 1525_005 og 1525_006 er gjennomgaatt med a7-kildeadapteren og en isolert testbackend for kanonisk bygging; alle hadde 58 XPath-mastertester og tre kildefamilier. Full Windows-GUI/test.bat og produksjonskjøring med virkelig kanonisk/KS-motor er ikke verifisert her.

For fullstendig formell KS/depotrapportering brukes fortsatt **Avvik / KS / godkjenning**, med eksplisitt rapporteksport og manuell faglig beslutning.
