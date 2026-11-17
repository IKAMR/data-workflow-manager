# v0.2.2-a1.8 – Automatisk vindushøyde for alle steg i Enkel modus

**Delta over v0.2.2-a1.7.** Versjonen i `version.py` er fortsatt `0.2.2-a1`.

## Feilen

I a1.7 ble naturlig høyde for «1. Velg uttrekk» og «2. Arbeidsmappe» ofte tilstrekkelig, men det fantes **ingen beregning eller vindusendring ved stegebytte**. Når brukeren gikk til «3. Kontroller / kjør», kunne den nederste delen av kontrollene ligge utenfor vinduet selv om skjermen hadde ledig høyde. Den eldre funksjonen `_a2_fit_initial_window()` håndterte bare første oppstart.

## Løsningen

- En Qt-kontroller måler faktisk høyde på det aktive Basic-innholdet etter at layout og flerjobbpanel er oppdatert.
- Ved stegebytte tilpasser den **bare vindushøyden**, ikke bredden.
- Høyden avgrenses til **tilgjengelig geometri på skjermen der vinduet står**. Om hele kontrollpanelet er høyere enn skjermen, beholdes standard rullefelt; den kan ikke vise mer enn det skjermen fysisk har plass til.
- Vinduets horisontale plassering beholdes. Vertikal plassering flyttes bare akkurat nok til at vinduet ikke kommer under eller over skjermkanten.
- Automatisk endring er deaktivert for maksimerte, fullskjerms- og minimerte vinduer.
- Når brukeren endrer vindusstørrelsen manuelt etter den første automatiske tilpasningen, beholdes den manuelle størrelsen. **«Tilpass vindu»** vises ved siden av «Ny kontroll» og slår på automatisk tilpasning igjen. Valget lagres i Qt `QSettings` under `qt/v022_basic_auto_fit` (ikke i jobblisten).
- Scrolling starter øverst ved nytt steg, men løpende fremdriftsoppdateringer skal aldri flytte brukerens rulleposisjon.
- Ingen endringer i jobbopprettelse, `.n5jobs`, kontrollkjøring, import av `info.xml`, resultatrapporter eller Source/Work.

## Installasjon

1. Bruk eksisterende lokale v0.2.2-a1.7, inklusive a1.2–a1.6.
2. Pakk ut `v0.2.2-a1.8.zip` i reporoten med overskriving.
3. Kjør `test.bat`, og start DWM på nytt.
4. Ingen Git commit/push er gjort.

## Praktisk Windows-test

1. Åpne «Ny kontroll», velg Source og Work som før.
2. Gå mellom **«1. Velg uttrekk» → «2. Arbeidsmappe» → «3. Kontroller / kjør» → «Oversikt»**. Kontroller at høyden endres med innholdet, og at vinduet forblir på samme skjerm.
3. På en skjerm med god vertikal plass skal hele «Kontroller / kjør» vises uten at brukeren manuelt må dra i vinduskanten.
4. På en skjerm som er lavere enn kontrollpanelet, skal DWM bruke skjermhøyden og vise rullefelt for resten. Dette er tilsiktet; en 800 px høy skjerm kan ikke vise 1100 px innhold samtidig.
5. Dra i vinduskanten manuelt. Bytt steg. DWM skal **ikke** overstyre høyden. Klikk den nye «Tilpass vindu»-knappen og kontroller at tilpasningen kommer tilbake.
6. Maksimer vinduet og bytt steg. DWM skal ikke endre størrelsen automatisk. Gjenta på ekstra skjerm hvis tilgjengelig.
7. Kontroller at JOB-001, JOB-002 og JOB-003 fortsatt finnes i både Enkel og Avansert modus etter lagring/gjenåpning.

## Verifisering

- 70 målrettede tester bestått i isolert Python-miljø: tidligere a1.2–a1.7-regresjon + 13 nye tester for høydeberegning, skjermgrenser, varsling om scrolling, manuell override, GUI-kobling og simulert Qt-størrelsesoppdatering.
- Python-syntaks kontrollert.
- Koden er pakket og sammenslåingen over a1.7 verifisert med tester.
- **Ekte Qt/Windows og full `test.bat` er ikke kjørt i dette miljøet**. Dette gjenstår før commit.

## Ikke inkludert

Separat registrert feil: utskifting av en feil `info.xml` med riktig fil kan fortsatt blande tomme metadatafelt fra den første importen. Den skal rettes i egen delta etter at GUI-testen er godkjent.
