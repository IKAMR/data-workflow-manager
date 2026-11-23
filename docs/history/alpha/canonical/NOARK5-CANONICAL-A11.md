# Kanonisk resultatmodell – v0.1.15-a11

## Dekningsmatrise og kildestatus

`canonical_matrix_v0115_a11.py` sammenstiller den eksisterende, eksplisitt valgte kontrollprofilen med DWM-resultater fra `canonical-results.json` og eksterne, kildeverifiserte data fra `canonical-external-analysis.json` i samme Work.

Hver kontrollkategori viser kravtype, intern evidensdekning, rapportert internt utfall, eksterne kildereferanser, rapporterte Arkade-teststatuser og eventuelt PRONOM-formatrader. Resultatene er **ikke en summering av arkivinnhold**. Arkade 5 Noark-testene og DWM-testene holdes adskilt. PRONOM-statistikken er formatstatistikk, ikke et antall beståtte tester.

`load_external_status` verifiserer jobbidentitet, gjeldende SHA-256 for kanonisk indeks og SHA-256 for den enkelte opprinnelige Work-kilden. Bare kildefiler som stemmer med den lagrede analysen vises som **Analysert**. Endrede eller manglende filer får egen status; gammel analyse knyttet til en endret kanonisk indeks er ikke gyldig grunnlag.

## GUI

**Kanoniske resultatdata → Dekningsmatrise (utkast)...** anvender den medfølgende `config/noark5/control-profile-dwm-draft-v1.json` ved et eksplisitt klikk. Ingen ekstra filvelger. Kildelisten oppdaterer også analysert-status etter analysen og ved ny kildeoppdagelse. Ingen endringer foretas i Source eller i eksisterende evidensfiler.

## Kjente begrensninger

- Medfølgende profil er fortsatt et *utkast* med to påkrevde kontrollkategorier, flere betingede og én valgfri. Dette er **ikke** en komplett, faglig godkjent Noark 5-kontrollplan.
- Betingede kontroller er ikke automatisk avklart; rapporterte utfall er ikke kontrollert eller godkjent av depot.
- Arkade har egne test-ID-er; disse kobles ikke automatisk 1:1 mot DWM/XPath.
- Faglig verifikasjon, arkivskapers aksept og depotgodkjenning mangler egne beslutningsprosesser.
- Skriftlig KS-rapport, godkjenningsrapport, AIP/evidenspakking og journalføringsgrunnlag gjenstår.
- Fremtidig arbeid: detaljert kontrollplan med Noark-versjon og leveranseprofil, avviksvurderinger per arkivdel, evidenslenker til konkrete XML-forekomster.

## Testgrunnlag

Seks syntetiske enhetstester dekker importkobling, feilutfall, foreldet indeks, endret kilde og manglende analyser. En lokal integrasjonskontroll med opplastet 1525_004-evidens viste 54 Arkade-tester (52 `ok`, 2 `error`) og 12 PRONOM-formatrader. **Originale depotfiler inngår ikke i repoet.** Full Windows-`test.bat` og GUI-test gjenstår.
