# v0.2.2-a1.5 – tilbakestilling av Setup og oppstart

Rettelsesdelta over v0.2.2-a1.4. Programversjonen er fortsatt `0.2.2-a1`.

## Hva er endret?

- **Eksisterende** «Nullstill setup» beholdes, og får den tydeligere teksten **«Tilbakestill alle Setup-innstillinger…»**. Den tilbakestiller felles DWM-verdier, inkludert verktøystier og lagrede oppstartsvalg, gjennom eksisterende `app.settings_portable.reset_settings()`.
- Under **Setup → Oppstart og profil** finnes nå **«Tilbakestill oppstart…»**. Denne nullstiller bare `ui_startup_page` og `ui_startup_mode`; den bevarer blant annet arbeidsprofil, depotprofiler, Arkade/Siegfried-stier, mappestier, rapportinnstillinger, alle jobber og resultatfiler.
- Ved ny installasjon og full Setup-tilbakestilling er standard oppstart **Kontroll → Enkel modus**, uansett arbeidsprofil. Brukeren kan fortsatt velge «Alltid Startside», «Sist brukte» eller «Avansert modus» manuelt i Setup.
- Begge handlingene krever bekreftelse. Oppstartstilbakestilling er sperret under kjøring. Valg av Nei eller feil ved lagring lar brukeren beholde sin nåværende tilstand.
- Den eksisterende fullstendige Setup-tilbakestillingen nullstiller **ikke** jobb- og rapportfiler. Den kan derimot fjerne lagrede programstier, nylig brukte mapper og andre oppsettverdier. Dette er et bevisst skille fra «Tilbakestill oppstart».

## Praktisk test i Windows

1. Pakk `v0.2.2-a1.5.zip` over a1.4 og kjør `test.bat`.
2. Gå til **Setup → Oppstart og profil**. Sett **Alltid Startside** og **Alltid Avansert modus**, velg arbeidsprofil **Depot – produksjonslinje**, og lagre.
3. Åpne Setup på nytt og klikk **Tilbakestill oppstart…**. Bekreft. Start DWM på nytt: programmet skal åpne **Kontroll → Enkel modus**, med den samme depotprofilen.
4. Kontroller at en eksisterende `.n5jobs` åpnes, at Arkade/Siegfried-konfigurasjonen er beholdt, og at Source/Work- og rapportfilene ikke er endret.
5. Prøv **Tilbakestill alle Setup-innstillinger…** (først når du ønsker å tilbakestille også verktøystier/øvrige oppsettverdier). Etter omstart skal Kontroll → Enkel modus fortsatt være standard. Eksisterende filer skal ikke være slettet.
6. Prøv å velge Nei i bekreftelsesdialogen. Ingen lagrede verdier skal da endres.

## Teststatus og avgrensning

Åtte målrettede regresjonstester (uten installert PySide6) er lagt til under `tests/test_v022_a1_5_setup_reset.py`. De dekker standard oppstart, selektiv tilbakestilling med bevart depotprofil og verktøystier, avvist tilbakestilling under kjøring, feil i lagrings-API, full tilbakestilling, eksport og kildebevaring, og GUI-koblingen gjennom en simulert Qt-dialog. Full Windows `test.bat` og GUI-prøving utføres av brukeren.

Merk: «Tilbakestill alle Setup-innstillinger» er knyttet til **felles Setup** (`config.json`). Windows-vindusplasseringer og andre Qt-vinduinnstillinger kan fremdeles ha egen tilstand; «Vis → Tilbakestill vinduer» brukes for separat tilbakestilling av arbeidsflateoppsettet.
