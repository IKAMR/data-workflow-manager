# DWM v0.2.2-a3.2 – Resultatvisninger: trygg lukking

**Delta over v0.2.2-a3.1.** Intern `VERSION` og eksisterende testregime endres ikke.

## Feil

Ved bruk/lukking av Resultatvisninger sammen med «Avvik, kvalitetssikring og godkjenning» kunne konsollen vise:

```
Traceback (most recent call last):
  File "gui_qt/result_side_layout_v020_a6.py", line 98, in _apply
    title = viewer.tabs.tabText(viewer.tabs.currentIndex())
RuntimeError: libshiboken: Internal C++ object (PySide6.QtWidgets.QTabWidget) already deleted.
```

Rotårsak: `QTimer.singleShot(0, self._apply)` la en Python-callback i hendelseskøen. Resultatvisninger kunne bli lukket og Qt-fanene slettet før callbacken kjørte.

## Rettelse

- Utsatt layouttilpasning bruker én samlende `QTimer` som eies av Resultatvisninger-vinduet, slik at Qt avbryter timeren ved destruksjon.
- Vinduets `destroyed`-signal sperrer nye oppdateringer og frigjør referansen til vinduet.
- Tilbakekall sjekker Shiboken/Qt-objektenes gyldighet før det leser faner, trevisning, skillelinje og detaljvisning.
- Eksisterende manuelle panelstørrelser, autojustering, faner og original evidensvisning beholdes.

Ingen endringer i rapportgrunnlag, jobbstatus, brukerkommentarer, Source, Work, opplastede/normaliserte data eller oppstartsgeometri.

`QWindowsWindow::setGeometry` er en separat Qt/Windows-varselmelding om geometrikorreksjon på skjerm; dette er ikke den samme feilen og er ikke endret av rettelsen.

## Isolerte regresjonstester

`tests/test_v022_a3_2_result_side_lifecycle.py` har seks tester uten krav om grafisk miljø: sammenslåtte timerhendelser, slettet QTabWidget, destruert vindu, ordinær layout, beholdt manuelt splittervalg og slettet trevisning.

**Resultat:** seks tester bestått på Python 3.13 med simulerte Qt-objekter. Test mot faktisk PySide6/Windows er ikke utført her.

## Praktisk reproduksjonskontroll

1. Start DWM med a3.2 installert og åpne JOB-002.
2. Åpne `Rapport → Resultatvisninger…` og deretter `Avvik / KS / godkjenning…`.
3. Lukk avviksdialogen og Resultatvisninger, og gjenta åpne/lukke noen ganger.
4. Bytt gjerne mellom Arkade 5 og PRONOM før lukking, for å utløse den tidligere utsatte layoutoppdateringen.
5. Kontroller at konsollen **ikke** skriver `Internal C++ object ... QTabWidget already deleted`.

Det er forventet at Resultatvisninger og avviksdialogen er separate vinduer. Avviksdialogen skal gjelde markert jobb, ikke en annen jobb i samme `.n5jobs`-liste.
