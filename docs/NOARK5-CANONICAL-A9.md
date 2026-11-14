# Kanoniske resultatdata – dynamisk GUI-layout (v0.1.15-a9)

## Formål
Dialogen tilpasser høydefordelingen mellom kildetabell og resultatområde til **vist innhold**, i stedet for faste prosentandeler. Antall kilder og antall tekstlinjer, inkludert estimert linjebryting, styrer plassfordelingen. Begge feltene er fortsatt rullbare når innholdet ikke får plass.

## Oppførsel
- Ved ny visning (kilder, ekstern evidens, kontrolldekning, kontrollplan, kontrollutfall/KS, kontekstindeks) beregnes høydene på nytt.
- Ved endret vindusstørrelse beregnes høydene på nytt når brukeren ikke har overstyrt midtdeleren manuelt.
- En manuelt flyttet midtdeler beholdes mens den samme visningen er aktiv. Ny visning gir dynamisk fordeling igjen.
- Handlingsknapper brytes automatisk over flere rader etter tilgjengelig vindusbredde og knappenes faktiske størrelsesbehov; ingen avkortede knappenavn er tilsiktet.
- Ingen endringer i kanoniske data, validering, Source, Work, kjøring eller evidenslagring.

## Begrensninger og verifikasjon
Linjehøyde og tekstbryting beregnes fra Qt-skriftmetrikker; faktisk tegning kan variere med tema, DPI og skjerm. Praktisk Windows-test med smalt vindu, fullskjerm, mange kandidater og KS-grunnlag er derfor nødvendig.

## Regressjon
`tests/test_v0115_a9_dynamic_layout.py` kontrollerer forholdsmessig høydefordeling, minimumshøyder, bryting av handlingsknapper og tilpasning til tekstlengde. Full `test.bat` kjøres i Windows før commit.
