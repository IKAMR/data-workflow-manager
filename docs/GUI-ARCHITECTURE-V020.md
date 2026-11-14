# DWM 0.2 – overordnet GUI og produksjonslinje

## Autoritative faglige trinn

**Arkivskaper/-eier:** Innkjøp → Idriftsetting → Produksjon → Avslutning → Uttrekk → Pakking → Innlevering.

**Depot:** Mottak → Antiviruskarantene → overordnet innholdskontroll (liste/filer, sjekksummer, uttrekkstype SIARD/Noark 5, første vurdering) → Validering → Godkjenning/avvisning → Bevaring → Innsyn.

Disse prosessene skal forstås med OAIS, DIAS, KDRS Prosesser og Rutiner og etablert Arkade 5-praksis som referansegrunnlag. Prosess-steg og GUI-bokser er **ikke** identiske. Faglig kontroll, kvalitetssikring, arkiveiers innholdsbekreftelse, depotbeslutning og bevaring forblir forskjellige hendelser. Godkjenningsrapporten skal bevare uttrekkets identitet, tilstand, avvik og begrunnelse for beslutning slik at dette kan gjenfinnes i ettertid.

## Overordnet GUI

Åtte avtalte bokser: **Ingest**, **Antiviruskontroll**, **Til arbeidsområde**, **Kontroll**, **Rapportering**, **Bevaring**, **Mot intern CRM**, **Innsyn**. «Kontroll» brukes for funksjonsområdet, «Validering» for den snevrere aktiviteten.

Det skal skilles mellom *arbeidsprofil* (synlige funksjonsområder) og *oppstartsmodus for Kontroll* (Enkel/Avansert). Arbeidsprofilene er **Kontroll** (standard for nye brukere, kun kontrollboksen), **Depot – produksjonslinje** (alle åtte) og **Egendefinert**. Profilvalg skal kunne endres i Setup og raskt fra Startside. Skjulte bokser deaktiverer ikke underliggende funksjonalitet.

Oppstartsmodus er et gjensidig utelukkende radiovalg: **Sist brukte modus**, **Alltid Enkel modus** (standard), **Alltid Avansert modus**. Fast oppstartsmodus bestemmer bare neste oppstart: brukeren kan alltid bytte manuelt. Eksisterende **Avansert modus**-knapp i Enkel og **Enkel start** i Avansert beholdes, sammen med en lett tilgjengelig **Startside**.

## v0.2.0-a1 – faktisk implementert

- Den eksisterende PySide6-hovedvisningen og samme jobber, resultater, DIAS-metadata og Work gjenbrukes.
- Ny avrundet startside viser boksene for valgt arbeidsprofil. Ved standardprofil åpnes Kontroll direkte i Enkel modus, uten onboarding-dialog. Startside åpnes fra den **faste, felles topplinjen** i både Enkel og Avansert modus. Startside er ikke en knapp nederst i den rullbare kontrollflaten.
- Oppstartsprofil og -modus kan lagres i eksisterende Setup under «Oppstart og profil»; arbeidsprofil kan også byttes fra Startside. Topplinjen viser aktiv arbeidsprofil og Kontroll-modus og har direkte tilgang til Setup.
- Den eksisterende Avansert modus-knappen er flyttet til topplinjen og skifter navn til Enkel modus ved bytte. Begge visningene deler samme knapp og samme jobbdata. Startside aktiverer Kontroll-boksen. **De øvrige boksene er kun navigasjonsutkast i a1** og oppgir dette eksplisitt ved klikk. Ingen funksjonalitet, pakking, antiviruskontroll eller CRM-integrasjon påstås opprettet.
- Eksisterende DIAS AIP-pakkemodul, `info.xml`-verdier, original SIP og depotets bevaringspraksis endres ikke. Ingen ny pakkemodell innføres.
- Ingen eksisterende jobb eller data slettes eller flyttes av GUI-profilvalg.

## v0.2.0-a2 – startsidens faktiske arbeidsområder

- Arbeidsområdene vises i fast produksjonsrekkefølge, filtrert av samme arbeidsprofil som a1. Tilgjengelighet på boksene beskriver **integrasjon i GUI**, ikke kontrollstatus, antivirusstatus, faglig godkjenning eller bevaring av arkivuttrekk.
- **Kontroll:** tilbake til aktiv Enkel/Avansert modus og samme jobb.
- **Til arbeidsområde:** åpner eksisterende Work-steg i Enkel modus uten å opprette mapper automatisk.
- **Rapportering:** velger mellom eksisterende resultatvisninger og rapport-/samlerapport-dialog.
- **Ingest:** krever bekreftelse før separat oppstart av eksisterende, eldre GUI. Ingen mottaksjobb startes automatisk.
- **Bevaring:** to eksplisitte alternativer: eksisterende DIAS-koblings-/evidenskontroll i Qt, eller separat eksisterende GUI for DIAS AIP-pakking. Evidenskandidat og ferdig AIP forblir ulike begreper.
- **Antiviruskontroll**, **Mot intern CRM** og **Innsyn:** ikke integrert, inaktive bokser. Ingen fiktiv skann, CRM-overføring eller innsynspublisering.
- Aktiv jobb-ID vises kun som informasjonskontekst. Bytte av arbeidsprofil flytter ikke jobb, Source, Work, AIP eller resultater.

## v0.2.0-a2 – korrigering etter Windows-test

- Startsiden vises som en **integrert sentralvisning i samme QMainWindow** som Kontroll. Det åpnes ikke lenger et separat Startside-popupvindu. Bytte mellom Startside og Kontroll endrer ikke aktiv jobb eller runner.
- Arbeidsprofilene **Kontroll**, **Depot – produksjonslinje** og **Egendefinert** lagres gjennom en egen validert utvidelse av eksisterende Setup-API. Nøklene `ui_work_profile`, `ui_startup_mode` og `ui_visible_sections` kan lagres uten feilen «Ukjente Setup-innstillinger»; ordinære Setup-nøkler beholder de eksisterende kontrollene.
- Profilbytte på Startsiden oppdaterer kortlisten umiddelbart. Depotprofilen viser åtte kort i avtalt rekkefølge. Kontrollprofilen viser ett kort. Ikke integrerte områder utfører ingen jobb.
- Den faste topplinjen blir stående, og Avansert-modus sine paneler skjules bare midlertidig mens Startsiden vises. Tidligere paneltilstand gjenopprettes før lagring av vindusoppsett ved avslutning.
- Eksisterende kontroll-, rapport-, Work- og DIAS-rutiner er beholdt. Full GUI-test på Windows må gjennomføres før commit.

## Videre trinn

1. Lag integrerte Qt-arbeidsflater for mottak/Ingest og videre antivirus/karantenekontroll; behold sikkerhets- og bevaringskontrakter.
2. Felles jobb-/mottakskontekst og trinnvis gjenopptakelse på tvers av GUI-modus.
3. Videreutvikle rapportering, beslutningsspor og kobling mot bevaring uten å konstruere nye OAIS-/DIAS-pakketyper.

Historisk mottaksfunksjonskontrakt: `docs/plans/N5-WF-MAN-19-A19-INGEST.md`, særlig `docs/plans/N5-WF-MAN-19-A19-FIX5-FLATT-MOTTAK.md` (flat E-mottaksmappe, separat uttrekksmappe). DIAS: `docs/DIAS-METADATA-MAPPING.md`, `docs/SHARED-ROADMAP.md` og `docs/NOARK5-CONTROL-TO-PRESERVATION-ROADMAP.md`.

## v0.2.0-a2 – oppstartsside og arbeidsområdenes modenhet

- Under **Setup → Oppstart og profil** finnes to uavhengige oppstartsvalg:
  **Oppstartsmodus for Kontroll** (Sist brukte, Alltid Enkel, Alltid Avansert)
  og **Oppstartsside** (Følg arbeidsprofil, Sist brukte side, Alltid Startside,
  Alltid Kontroll). «Følg arbeidsprofil» viderefører eksisterende standard:
  Kontrollprofil åpner Kontroll; Depot/Egendefinert åpner Startside.
- «Sist brukte side» lagres separat i `QSettings` som
  `qt/v020_last_page`. Å lukke DWM fra Startsiden må ikke overskrive valget
  med Kontroll når skjulte Avansert-paneler gjenopprettes før vindustilstanden
  lagres. Fast oppstartsside og fast Enkel/Avansert er uavhengige valg.
- **Modenhet 0/1/2 for arbeidsområder** følger DWM sin eksisterende
  `app.operation_metadata`-skala fra SIARD-prinsippet:
  0 = Alpha, 1 = Beta, 2 = Stabil. Setup-filteret viser minimum 0 (alle),
  minimum 1 (Beta+Stabil) eller minimum 2 (kun stabile). Standard **0**
  bevarer a2-visningen med åtte bokser. Feilkonfigurert lagret terskel
  normaliseres restriktivt til 2.
- Klassifisering av **GUI-integrasjonen** ved a2: Ingest=0, Antivirus=0,
  Til arbeidsområde=2, Kontroll=2, Rapportering=1, Bevaring=1,
  Mot intern CRM=0, Innsyn=0. Dette er **ikke** modenhetsvurdering av
  de underliggende kontrolloperasjonene, og er ikke depotets godkjenningsstatus.
- Arbeidsprofil filtrerer først hvilke funksjoner brukeren har valgt å se;
  modenhetsfilteret filtrerer deretter visningen. Det endrer aldri en jobb,
  autorisasjon, utføring, resultat, original SIP, Work eller DIAS AIP.
- Det eksisterende **«Vis operasjoner»**-valget (`operation_visibility`) beholdes
  uavhengig av det nye **«Synlige arbeidsområder etter modenhet»**-valget
  (`ui_area_visibility`).

## v0.2.0-a3 – integrert Ingest, antivirusavgrensning og Work-navigasjon

**Baseline:** siste committede og push-ede `main`, commit
`8fec1f5b6e6217d1420d879e2b2fa2109a0e46cf` (v0.2.0-a2).
A3 er én ordinær delta-ZIP med komplette, endrede filer; ingen commit eller push.

- **Ingest** åpner nå en PySide6-side i samme hovedvindu som Startside/Kontroll.
  Ikke egen Tk-prosess. Siden bruker `app/grouped_ingest.py` via en tynn,
  Qt-uavhengig adapter, ikke en ny/parallel mottaksmotor. Den støtter både
  Mottak (flat `E-FFKK-YYYY-nnnn`) og Uttrekk (separat søskenmappe), ekstern
  depot-setup, mottaksnummerforslag, valg av eksisterende mottak, valgfri
  `info.xml`/LABEL, planforhåndsvisning og eksplisitt bekreftelse før opprettelse.
- Mottak oppretter **kun** den flate E-mappen og eksisterende backendlogger
  `ingest.events.jsonl`/`depot-log.txt` direkte i E-mappen. Uttrekk oppretter
  mappetreet ved siden av E-mappen og viderefører kanonisk og portabel
  hendelseslogg med eksisterende hendelses-ID-er. Appen laster ikke ned,
  kopierer, pakker ut, skanner eller flytter arkivdata.
- Ingest-brukerprofiler åpnes/lagres via eksisterende
  `app/ingest_saved_profiles.py`; de inneholder bare oppsettfil, mappeprofil,
  disk, gruppemappe, eierkommune og foretrukket handling. Tidligere mottaksnummer,
  LABEL, `info.xml` og uttrekks-ID lagres **ikke**.
- **Antiviruskontroll** har egen Qt-side for å velge og vise den aktuelle
  karantenemappen. **Ingen antivirusmotor er integrert i a3**. Ingen knapp
  markerer mappe som skannet, ren eller godkjent; ingen falsk hendelse loggføres.
  Motor-/signaturversjon og reelt skanneresultat må inn i et senere utviklingstrinn.
- **Til arbeidsområde** og «Gå til eksisterende Work» åpner det eksisterende
  Work-steget i Enkel kontroll. Brukeren må selv velge jobbkontekst. Ingen
  automatisk kobling mellom et nyopprettet uttrekk og en jobb, og ingen
  automatisk filoverføring/Work-endring.
- Modenhet 0/1/2 beholdes uendret for alle åtte områder. Ingest=Alpha (0)
  selv om Qt-ruten er tilgjengelig. Antivirus=Alpha (0) og avgrenset som
  **ikke skannet**; statusen beskriver GUI-integrasjon, aldri depotgodkjenning.
- Når man navigerer Avansert → Startside → Ingest/Antivirus → Startside →
  Kontroll, lagres synlige Avansert-docker bare én gang og gjenopprettes.
  Oppstartssiden «Sist brukte» behandles fortsatt som Startside eller Kontroll;
  ufullførte Ingest-skjemaer startes ikke automatisk ved neste programoppstart.

**Test:** Kjør `test.bat` og `start.bat` i Windows. Velg arbeidsprofil
«Depot – produksjonslinje» og modenhetsfilter 0 for å vise Ingest/Antivirus.
Test Mottak/Uttrekk på en **egen testdisk/-mappe**, kontroller at første nivå
kun får to logger, at uttrekk blir søskenmappe og at ingen arkivdata kopieres.
Test avvisning/duplikat mottaksnummer, gjenåpning av brukerprofil,
antivirusstatus «IKKE SKANNET», Work-navigasjon og Avansert-panelretur.

**Videre etter a3:** Verifisert antivirusmotor og skanneresultater, eksplisitt
arbeidsområde-/jobbkobling, kontroll-til-rapport-til-bevaring og tverrgående
oppgavestatus; aldri utled skannestatus bare fra at en mappe finnes.
