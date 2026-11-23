# v0.2.2-a1.9 – Krymping fra Kontroller/kjør til Arbeidsmappe

**Rettelsesdelta over v0.2.2-a1.8.** Applikasjonens versjonsstreng er fortsatt `0.2.2-a1`; ingen ny release eller commit.

## Feil observert i Windows

Automatisk høyde fungerte i flere overganger, men når brukeren gikk fra **3. Kontroller / kjør** tilbake til **2. Arbeidsmappe**, beholdt hovedvinduet stor høyde selv om arbeidsmappesteget var kort. Skjermbildet viste mye tomt areal under Work-panelet. Brukeren hadde ikke endret vindusstørrelsen manuelt.

## Endring

- Høydeberegningen måler nå den **synlige** Basic-layouten fra aktive layout-elementer i stedet for å bruke størrelsesforslaget til hele `QScrollArea`-innholdet. Dette skiller Work-stegets naturlige høyde fra restmål etter det lange Kjør-steget.
- Skjulte steg og utvidende tomrom (`addStretch`) teller ikke med; interne marger, mellomrom og tekstbryting teller med.
- Beregningen bruker den eksplisitte minimale vindushøyden, ikke en mulig midlertidig for høy `minimumSizeHint()` etter visning av et langt steg.
- En ekstra **enkeltstående** tilpasning etter 45 ms lar Qt fullføre synlighets-/layoutendringen før siste høydesjekk. Det opprettes ikke en tilbakevendende timer.
- Eksisterende regler består: bevar vindusbredde og skjerm, respekter maksimering/fullskjerm/minimering og manuell vindusstørrelse, og tilby «Tilpass vindu» for å slå automatikk på igjen.
- Det er ingen endring i `.n5jobs`, jobbregistrering, Source/Work, `info.xml`, kontrollkjøring, framdrift eller rapporter.

## Installasjon

1. Behold alle tidligere deltaer opp til og med `v0.2.2-a1.8`.
2. Pakk ut `v0.2.2-a1.9.zip` over **reporoten**, med overskriving av de eksisterende filene.
3. Kjør `test.bat` og start DWM på nytt.

## Praktisk akseptansetest

1. Start ny kontroll i Enkel modus, velg Source og Work.
2. Gå til **3. Kontroller / kjør**; vinduet skal utvides hvis skjermen har plass.
3. Klikk **← Forrige** til **2. Arbeidsmappe**; vinduet skal nå **krympe** til Work-innholdet, ikke bli stående i høyden fra Kjør-steget.
4. Gjenta 2 → 3 → 2 og test deretter 1 → 2 → 3 → Oversikt → 3 → 2.
5. Dra i vinduskanten manuelt, bytt steg, og bekreft at størrelsen beholdes frem til «Tilpass vindu» aktiveres igjen.
6. Gjenta med maksimert vindu og eventuelt ekstra skjerm. Ingen automatisk krymping ved maksimering.
7. Kontroller at tidligere valgte Source/Work og registrerte jobber er uendret.

## Verifisering

- 75 av 75 målrettede tester bestått i sammensatt kode fra deltaene a1.2–a1.9, med koden fra committet baseline for Settings inkludert i det isolerte testmiljøet.
- Fem nye regresjonstester dekker synlige/skjulte paneler, tekstbryting, faktisk krymping etter oppskalering med utdaterte Qt-hint, manuell-størrelse-vakt og ett ekstra layout-pass.
- Python-syntaks kontrollert. ZIP innhold og anvendelse over a1.8 kontrollert.
- **Full Windows `test.bat` og virkelig PySide6-grafikk er ikke testet i dette miljøet**, og må godkjennes på Windows før commit.

**Ikke del av denne deltaen:** separat identifisert feil ved utskifting av feilaktig `info.xml` og påfølgende feltfletting.
