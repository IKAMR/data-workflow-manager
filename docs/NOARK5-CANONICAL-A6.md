# v0.1.15-a6: Kontrolldekning og justerbar resultatvisning

## Endring

- `Rapport -> Kanoniske resultatdata` har nå en **vertikal, trekkbar skillelinje** mellom kandidatlisten og rapportfeltet (`QSplitter`). Det nederste feltet får automatisk mer plass etter «Finn ekstern evidens» og «Kontrolldekning». Brukerens fordeling lagres i Qt `QSettings` ved lukking.
- Ny knapp **Kontrolldekning** lager en **lesebasert** oversikt fra `noark5_evidence/canonical-results.json` med SHA-256 og kontroll av om `canonical-context.json` fortsatt peker til den gjeldende kanoniske filen.
- Første kontrollkategorier: XML/XSD, DWM Noark 5 XPath, Arkade 5 Noark, Siegfried PRONOM, Arkade 5 PRONOM og DWM depotrapport. Kategorien viser `registered` eller `not_documented` og separat oppgitt råstatus.

## Avgrensning som er avgjørende for depotarbeid

`registered` betyr **kun at en observasjon/kjøring er registrert i den valgte kanoniske indeksen**. Verken `status=ok`, antall kjøringer eller «funn av manifest» innebærer en ferdig kontroll, et oppfylt krav eller depotaksept. Matrisen er derfor merket `profile_not_selected`, `compliance=not_assessed`, `coverage_complete=null` og `mandatory_tests_verified=false` inntil en godkjent Noark- og leveranseprofil og faktisk resultattolking finnes.

Eksterne Arkade 5-JSON-, XML- og CSV-filer krever undersøkelse av faktisk skjema før man kan trekke ut og rapportere **individuelle testresultater**. De er fortsatt kandidat-/evidensfiler i a6. Arkade-kjøring registrert i råledger er ikke lik lest Arkade-testrapport. `Siegfried` formatidentifikasjon er heller ikke valideringsgodkjenning.

## Neste arbeid

1. Undersøk virkelige `external_evidence/arkade5/.../normalized/arkade5_results.json`, `source/arkade-testrapport_*.json` og `external_evidence/siegfried/.../pronom_statistics.json` i et **eksempeldatasett**, dokumenter skjema/versjoner og lag validerte parsere med egne kilde-ID-er og evidenshash.
2. Definer godkjent/versjonert obligatorisk og betinget **kontrollprofil**, per Noark 5-versjon, leveranseprofil, eksterne verktøy og avbrutte eller ikke-relevante tester. Knytt profil til plan før kjøring.
3. Koble kontrollstatus og avvik til XML-forekomster, dokumentreferanser, regel-ID og faglige vurderinger uten å forveksle testreferanse og faglig verifikasjon.
4. Bruk dekningsmatrisen i kvalitetssikringsrapport for arkivskaper, depotets ferdigstillingsrapport og kuratert bevaringsevidens/AIP.

Se også `docs/NOARK5-CONTROL-TO-PRESERVATION-ROADMAP.md` og `docs/DWM-BACKLOG-CONSOLIDATED.md` fra a4.
