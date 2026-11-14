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

## Videre trinn

1. Koble øvrige bokser til **eksisterende** funksjoner, særlig Mottak/Ingest og DIAS AIP; kartlegg implementert dekning før navigasjon aktiveres.
2. Felles jobb-/mottakskontekst og trinnvis gjenopptakelse på tvers av GUI-modus.
3. Videreutvikle rapportering, beslutningsspor og kobling mot bevaring uten å konstruere nye OAIS-/DIAS-pakketyper.

Historisk mottaksfunksjonskontrakt: `docs/plans/N5-WF-MAN-19-A19-INGEST.md`, særlig `docs/plans/N5-WF-MAN-19-A19-FIX5-FLATT-MOTTAK.md` (flat E-mottaksmappe, separat uttrekksmappe). DIAS: `docs/DIAS-METADATA-MAPPING.md`, `docs/SHARED-ROADMAP.md` og `docs/NOARK5-CONTROL-TO-PRESERVATION-ROADMAP.md`.
