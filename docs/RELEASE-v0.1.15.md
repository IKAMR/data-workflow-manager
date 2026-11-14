# Data Workflow Manager v0.1.15

## Kanoniske resultater og dokumentasjon av kontroll

- Kanonisk resultatindeks for Noark 5-kontroller med kilde- og jobbidentitet.
- Integrasjon av eksterne analysedata fra Arkade 5 (Noark og PRONOM), med kildeavtrykk og tydelig skille fra DWM-kontroller.
- Kontrollgrunnlag og dekningsmatrise som skiller registrert evidens fra faglig verifisering.
- Kvalitetssikringsrapport med arkivdeler, innholdsoversikt, proveniens, formatstatistikk og uavklarte funn.
- Ferdigstillings- og beslutningsutkast med avvik, kontrollstatus og referanser til KS-rapport. Dette er ikke automatisk depotgodkjenning.
- Evidenskandidat i Work med SHA-256-manifest og integritetskontroll. Kandidaten er ikke AIP.
- Skrivebeskyttet koblingskontroll til eksisterende DIAS AIP-pakkemodul og `info.xml`-/METS-håndtering; ingen ny pakkemotor.
- Faglige utviklingsføringer for produksjonslinjen, KDRS/OAIS, arkiveiers involvering og eksisterende depotpraksis er dokumentert i prosjektets planer.

## Avgrensninger

Evidenskandidat er ikke ferdig DIAS AIP. Original SIP, arkivversjoner, beslutninger og tilleggsdokumentasjon inngår etter depotets faktiske valg og eksisterende DIAS-prosess. Kontrollresultater innebærer ikke automatisk aksept. Neste GUI-arkitektur og oppstartsprofiler planlegges for v0.1.16.

## Test og publisering

Kjør `test.bat` i Windows før commit og publisering. Opprett deretter tag `v0.1.15` fra godkjent release-commit. Dette dokumentet er releaseutkast frem til test er bekreftet.
