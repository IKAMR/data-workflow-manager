# v0.2.2-a1.11 – justerbare kolonner i Arbeidsflyt

## Bakgrunn

I Avansert modus er «Arbeidsflyt» nederst til venstre for smal til lange deljobbnavn. Den etablerte Qt-koden setter kolonne 1 til `Stretch` og kolonnene 0, 2 og 3 til `ResizeToContents`. Ingen av disse kan dras manuelt.

## Endring

- Alle fire kolonneoverskrifter i **Arbeidsflyt** får `QHeaderView.Interactive`.
- Brukeren kan dra skillelinjene eller dobbeltklikke på en grense for å tilpasse kolonnen til innholdet.
- Standardbreddene er 38 / 300 / 88 / 72 skjermpiksler. Når docken er smalere, kan tabellen rulles vannrett.
- Kolonnebreddene lagres som Qt-vinduspreferanse (`qt/a111_workflow_column_widths`), og beholdes etter omstart og jobbbytte.
- Ved hover over deljobbnavn kan hele navnet vises som tooltip sammen med den etablerte operasjonsidentifikasjonen.
- Ingen endring i kjøringsmotor, jobbliste, Source, Work, AIP, eller visning av andre tabeller.

## Installasjon

Pakk deltaen over **v0.2.2-a1.10** og kjør `test.bat`. Start DWM på nytt. I Avansert modus, dra grensene i «Arbeidsflyt»-tabellens header. Dobbeltklikk et skille for å vise hele deljobbnavnet. Lukk og start DWM på nytt for å verifisere at valget beholdes.

## Testet

- Parsing og sikker lagring av brukerens kolonnebredder, også ved ugyldige og gamle innstillinger.
- Alle header-seksjoner er interaktive, med eksplisitt dobbeltklikkstilpasning og vannrett scrolling i et isolert GUI-API-testmiljø.
- Lagring ved manuelle endringer, ikke ved første oppstart, og bevaring av valgt layout.
- Kontroll av at oppstartskoblingen installerer endringen etter opprettelse av hovedvinduet.

**Begrensning:** Miljøet som lager deltaen har ikke PySide6. Faktisk Windows/Qt-oppførsel og full `test.bat` må kontrolleres på testmaskinen.
