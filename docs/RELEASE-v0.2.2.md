# Data Workflow Manager v0.2.2

## Jobblister, avhengighetsstyrt arbeidsflyt og faglig KS

- **Jobber i Enkel og Avansert modus:** Samme lagrede `.n5jobs`-jobbliste med flere uttrekk. Jobber kan registreres uten å startes, vises i begge modus og kjøres sekvensielt etter bekreftelse. Jobbnavn og Source-kontekst håndteres tydeligere.
- **Deljobber med eksplisitte avhengigheter:** Nummererte A100–A190 for tekniske kontroller og A200–A260 for etterbehandling, Arkade-import, Noark 5-evidens, views/compositions, depotrapporter og KS-grunnlag. Etterbehandling inngår i den faktiske jobbstatusen og er ikke en valgfri manuell etterjobb. Status 100 % betyr teknisk fullført arbeidsflyt, ikke godkjent uttrekk.
- **Kjøreprofiler:** Opprett, velg og rediger kjøreprofiler og deljobrekkefølge, med skille mellom tekniske tester og etterbehandling. Bevaring av jobbliste og profilvalg mellom oppstarter.
- **Kjøre- og resultatvisning:** Kjøreløp viser faktiske deljobber og resultathistorikk. Antall resultatfiler presenteres særskilt fra tekniske loggadvarsler og faglige testfunn.
- **Windows/Qt:** Forbedret stabil oppstart, avgrenset popup-håndtering, vindusplassering ved flere skjermer, konsolldiagnostikk og autojustering av Avansert arbeidsflate. Kjente små Windows-justeringer av vindusgeometri logges uten falsk rød alarm.
- **KS-arbeidsflate:** Kildebundne funn, tekniske tester, arkivdeler, evidensfiler og filter på kilde, alvorlighet, vurderingsstatus og fritekst. Faglige kommentarer lagres som append-only Work-hendelser, bundet til jobb, funn og depotrapportens kildeversjon. Manuelle avklaringer og observert avvik holdes atskilt fra tekniske kontrollresultater.
- **KS-/godkjenningsrapport som UTKAST:** Konfigurerbart rapportinnhold, forhåndsvisning, originalt avviksregister (HTML/JSON/CSV), kildehenvisninger og SHA-256-manifest, basert på etablerte KS-/depotrapporter. Eksporten publiserer ny rapportmappe atomisk og overskriver ikke Source eller Work. Rapporten utgjør ikke formelt depotvedtak.

## Praktisk kontrollgrunnlag og begrensninger

- Tre eksisterende WebSak-jobber 1525_004, 1525_005 og 1525_006 er gjennomført med 17 av 17 deljobber hver i tidligere a9-kjøring. Teknisk sluttstatus er skilt fra faglig Noark 5-aksept; Arkade rapporterte henholdsvis 2, 0 og 5 feil.
- A12s nye test-/kildeleser ble kontrollert mot disse Work-mappene og viste 177 test-/kildeposter per uttrekk, inkludert DWM XPath, XPath-regresjoner, Arkade 5, XSD og PRONOM-rapportkilder. Ikke alle kildene er selvstendige mikrokontroller.
- Workshop 19. november 2026 skal verifisere den faktiske operatørflyten fra funn, via kommentar og arkivdelsvurdering, til rapportutkast. Formell godkjenning, attestasjon av Noark 5-etterlevelse og total Saxon/lxml-paritet er **ikke** en del av releasen.
- Source og tidligere kontrollresultater beholdes. Opprettelse av vurderingshendelser skjer kun etter eksplisitt lagring i Work. Tidligere faglige vurderinger kan ikke automatisk overstyre eksterne Arkade- eller KDRS-resultater.

## Versjon og releaseprosedyre

- Basis: committet `v0.2.2-a12`, SHA `d99da9c458b826841bc559c283ebb2efd76791cd` (18. november 2026).
- Sluttversjon: `version.py` = `0.2.2`; `pyproject.toml` = `0.2.2`. Oppdatert eksisterende a9-versjonstest, samt egen sluttversjonstest.
- Pakk ut deltaen direkte over committet a12. Ingen ekstra installasjonsskript eller etterarbeid er nødvendig.
- Før utgivelse: Kjør full `test.bat` på Windows, kontroller GUI-start med flere skjermer og test det lagrede Work-grunnlaget for 1525_006. Verifiser kommentarer etter omstart, kildefilåpning og rapporteksport. Ingen samlet Windows-test eller formell workshop-godkjenning påstås i dette deltaet.
- Opprett først Git-tag/release `v0.2.2` etter gjennomført og godkjent testing. Deltaen utfører ingen git commit, push eller tag.
