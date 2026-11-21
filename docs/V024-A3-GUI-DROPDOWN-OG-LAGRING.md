# DWM v0.2.4-a3 – Qt-nedtrekkslister og lagringsmarkering

**Delta over v0.2.4-a2.** Ingen endring i eksisterende arbeidsflyt, Siegfried, Noark 5-tester, Arkade 5, Source/Work-struktur, database eller resultatformat.

## 1. Nedtrekkslister i Enkel modus, Setup og dialoger

V0.2.0 hadde allerede `gui_qt/combobox_popup_v020_a2.py` med global QApplication-eventfilter og korrekt geometriberegning. Filteret var imidlertid deaktivert som standard fra v0.2.2-a1.14 etter intermittent native Windows Qt-ustabilitet. **A3 aktiverer ikke det gamle globale filteret.**

Ny `gui_qt/combobox_anchor_v024_a3.py`:

- Binder seg bare til popup-vinduet for den **QComboBox som faktisk får fokus**, inkludert nedtrekksfelt i dialoger som åpnes etter oppstart.
- Bruker samme dokumenterte `dropdown_origin`-beregning og korrigerer forskjøvet Show/Move/Resize.
- Observerer ikke alle Qt-hendelser på QApplication; ingen global eventFilter eller endring i øvrige popups.
- Oppretter ikke private QComboBox-popupvinduer for alle felt under oppstart; registrering skjer ved faktisk fokus.
- Lar `DWM_SAFE_MODE=1` deaktivere ny korreksjon for feilsøking av native Qt-feil.

**Testkrav på Windows:** Åpne Bytt uttrekk, Setup/Arbeidsprofil, kjøreprofil og KS-filter. Flytt/rull side, gjenta med flere skjermskaleringer om tilgjengelig. Listen skal forbli ved feltet etter 50 ms og ved ny åpning. Ingen blank oppstart eller native krasj.

## 2. `*` i tittellinjen

Work-first-prosessen skriver autoritativ jobbdata før `.n5jobs`-indeksen, men beholdt historisk `_dirty=True` også etter suksessfulle autoskrivinger. A3 får `_persist_updated_job` til å tømme markeringen først **etter** at `super()` har skrevet Work og den tilhørende `.n5jobs`-indeksen uten rapportert skrivefeil.

- Ved lagringsfeil i Work: unntaket beholdes, ingen kvittering om lagring.
- Ved mislykket `.n5jobs`-indeks: lagringsadvarsel beholdes og `*` fjernes ikke.
- Ingen ekstra diskanalyse eller lagring på Qt-hovedtråden.
- Samme forhold gjelder alle jobber i felles jobbliste.

## 3. Test og installasjon

1. Pakk ut delta i roten til **v0.2.4-a2** på en separat testkopi.
2. Kjør:

   ```powershell
   py -m unittest tests.test_v024_a3_dropdowns_autosave -v
   .\test.bat
   ```

3. Start DWM flere ganger med normal `start.bat`, og test samme nedtrekksliste før og etter scrolling; test også Setup og en nystartet dialog.
4. Åpne en testjobbliste med 3 jobber, kontroller at eksisterende historikk er bevart og at `*` følger faktisk lagringsstatus.
5. Kontroller at `Fortsett jobb`, `Nullstill jobb` og fullført resultatvisning fungerer som i a2.
6. Ved oppstartsproblem: kjør `start-safe.bat` og hent relevante native krasjlogger; ikke test patch direkte i en prosess som kjører 2 TB-uttrekk.

**Lokalt testet uten PySide6:** 11 nye a3 tester og 29 eksisterende a2-tester, totalt 40/40. Full Windows `test.bat` og reell grafisk validering er ikke kjørt her. Ingen Git commit/push.
