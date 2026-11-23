# v0.2.0-a2 – Plassering av Qt-nedtrekkslister

Den tidligere stilen `QComboBox { combobox-popup: 0; }` løste ikke feilen på Windows: listen ble først tegnet ved riktig felt, før Qt flyttet den til en feil skjermposisjon (blant annet i `Setup → Oppstart og profil`).

`gui_qt/combobox_popup_v020_a2.py` følger nå **selve Qt.Popup-vinduet** som hører til en `QComboBox`, og korrigerer posisjonen ved **Show, Move og Resize**. Den beregner plassering fra det faktiske feltet i globale Qt-koordinater og den tilgjengelige geometrien på feltets skjerm. Listen legges nedenfor feltet hvis den får plass, ellers ovenfor, og begrenses til synlig skjermareal. Korreksjon etter Show og native flytting hindrer at listen blir liggende et annet sted etter det første øyeblikket.

Regelen installeres én gang på `QApplication` og dekker også nedtrekkslister i senere åpnede Setup-dialoger og på Startsiden. Ingen modell, verdi, markering, jobber, Work, DIAS eller øvrige popup-menyer endres. Endringer av fargetema krever ikke reinstallasjon.

## Windows-kontroll

1. Åpne **Setup → Oppstart og profil**. Åpne `Arbeidsprofil` øverst og `Synlige arbeidsområder etter modenhet` nederst. Listene skal forbli festet ved sitt felt, ikke hoppe ned etter et kort øyeblikk.
2. Rull i fanen og gjenta testen. Kontroller spesielt at listen kan åpnes *over* feltet når nedre skjermkant ikke gir plass.
3. Åpne nedtrekkslister under **Utseende og vinduer**, **Filformatvurdering** og på **Startsiden**.
4. Prøv i annet tema og på sekundær skjerm dersom tilgjengelig. Bekreft valg med både mus og tastatur.
5. Kjør `test.bat`.

Headless regresjonstester dekker geometri, installasjon og flyttingshendelser. Faktisk oppførsel i Windows må fortsatt verifiseres i Qt-GUI-et.
