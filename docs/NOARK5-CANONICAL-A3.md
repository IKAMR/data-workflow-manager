# v0.1.15-a3 - Kanoniske resultatdata i Qt

Under **Rapport > Kanoniske resultatdata...** kan kontrolloren se kandidatfiler i aktiv jobbs valgte Work, velge eksplisitt hvilke som skal inngaa og opprette `noark5_evidence/canonical-results.json`.

- Ingen kilde velges automatisk, selv om oppdagelsen finner en masterindeks.
- Bare ordinare masterindekser, raaresultatlogger og resultatbank v2 kan velges.
- Tidligere kjøringer merges ikke automatisk. Kildene vises separat i dekningsrapporten.
- Operasjonen utføres i en arbeidstraad slik at vinduet ikke blokkeres av Work-I/O.
- Bekreftelse kreves for opprettelse og erstatning. Ingen endring av Source, ekstern evidens, tekniske resultater eller vurderinger.
- Manglende resultatbank betyr ikke at Arkade-/KDRS-evidens ikke finnes; bare at den ikke ble funnet som stoettet v2-bank.
- UI-integrasjonen gir en valgfri resultatindeks. Etablert Resultatvisninger og rapportmotor bruker inntil videre sine tidligere datasett. Kanonisk aggregasjon og depotgodkjenning er ikke implementert.

Praktisk kontroll: Aapne en eksisterende jobb (for eksempel 1525_004), velg Rapport > Kanoniske resultatdata..., kontroller at 58 mastertester og raaresultatloggen oppdages, huk av valgte kilder og bekreft opprettelse. Kontroller filen i Work. Test `test.bat` foer commit.
