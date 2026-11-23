# v0.2.2-a1.7 – Flerjobb først etter at første uttrekk er klargjort

**Delta over v0.2.2-a1.6.** Programversjonen forblir `0.2.2-a1`. DWM bruker fortsatt én felles `.n5jobs`-modell for Enkel og Avansert modus. Ingen endringer i kjøring, jobblisteformat, DIAS-metadata, Source/Work-stier eller eksisterende resultatfiler.

## Brukergrensesnitt

- **0 registrerte uttrekk:** Ingen ekstra flerjobb-/lagringsboks vises. Brukeren starter direkte med «1. Velg uttrekk».
- **1 registrert uttrekk:** På **1. Velg uttrekk** og **2. Arbeidsmappe** vises bare det aktuelle steget, også etter at DWM automatisk har registrert jobben. Når brukeren åpner **3. Kontroller / kjør** eller **Oversikt**, vises «Uttrekk klart for kontroll» med «Legg til nytt uttrekk» og «Lagre».
- **2 eller flere registrerte uttrekk:** Den felles «Bytt uttrekk»-velgeren vises på alle steg slik at brukeren kan velge hvilket uttrekk som redigeres. «Legg til nytt uttrekk» beholdes, og alle registrerte uttrekk kan fortsatt kjøres fra Avansert modus.
- **Ufullstendig nytt utkast ved siden av eksisterende jobb(er):** Velgeren beholdes tilgjengelig, slik at man kan gå tilbake til et tidligere uttrekk uten å miste jobbene.
- **Status:** Egen linje viser antall registrerte uttrekk og den aktive jobbens kontrollstatus, f.eks. «Registrert, ikke kjørt» eller «Kontroll fullført». En separat linje viser **lagring til fil**: «Ikke lagret til fil», «Lagret i ...» eller «Lagring feilet». Brukeren kan dermed se at uttrekket eksisterer i DWM selv om en `.n5jobs` ennå ikke er lagret.
- **Ingen endret registrering:** Første uttrekk registreres fortsatt automatisk når Source, Work og kontrollvalg er gyldige. Dette starter ingen kontrollkjøring. En allerede valgt `.n5jobs` oppdateres av eksisterende API. Første lagring til en ny fil velges av brukeren.
- **Ingen kontroller valgt:** «Legg til nytt uttrekk» deaktiveres inntil minst én kontroll er valgt. Aktuell jobb og lagringsstatus er fortsatt tilgjengelig.

## Installasjon

1. Bruk eksisterende v0.2.2-a1.6 (med a1.2–a1.5 allerede installert).
2. Pakk ut `v0.2.2-a1.7.zip` over repoet med overskriving av filene i deltaen.
3. Kjør `test.bat` og start DWM på nytt.
4. Ingen Git commit/push er utført av leveransen.

## Praktisk kontroll på Windows

1. Klikk «Ny kontroll». Velg Source og eventuelt `info.xml`, og gå til «2. Arbeidsmappe». Velg/godkjenn Work. **Det skal ikke komme noen flerjobbboks øverst i steg 1 eller 2**, selv om jobben allerede er registrert.
2. Klikk «Neste» til «3. Kontroller / kjør». Nå skal du se «Uttrekk klart for kontroll», jobbstatus **«Registrert, ikke kjørt»** og separat melding **«Ikke lagret til fil»**. Klikk «Lagre» og velg filplassering, uten å kjøre kontrollene.
3. Klikk «Legg til nytt uttrekk». Velg en annen Source og en egen Work-mappe. Etter registrering skal «Bytt uttrekk» vise JOB-001 og JOB-002. Velg hver og se at stiene er riktige.
4. Legg til et tredje uttrekk. Gå til Avansert modus, kontroller at tre jobber er tilgjengelige i samme jobbliste. Gjenåpne `.n5jobs` og kontroller igjen.
5. Gå tilbake til Enkel modus. På steg 1 og 2 skal «Bytt uttrekk» fortsatt vises når det finnes minst to registrerte jobber.
6. Åpne en tidligere fullført jobb. Statusen skal vise «Kontroll fullført», ikke «Registrert, ikke kjørt». Stopp-/kjøretilstanden skal fortsatt styre hvilke knapper som er aktive.
7. Test at «Ny kontroll» ikke sletter eller skriver over eksisterende Work, Source eller lagrede jobblister.

## Verifisering

- **57 målrettede tester bestått** i isolert Python-miljø etter sammenslåing av deltaene a1.2–a1.7. Det omfatter 12 nye tester for kontekststyrt flerjobbvisning, status, lagringstekst, første og påfølgende jobber, aktivt utkast, kjøring og navigasjon.
- Python-syntaks kontrollert for alle leverte `.py`-filer.
- **Full `test.bat` og ekte PySide6/Windows-visuell kontroll er ikke utført her.** Disse må gjennomføres før commit.

## Utenfor denne endringen

Utskifting av feil valgt `info.xml` med korrekt isolering av gamle/nyere metadata og automatisk vindushøyde per steg er separate oppfølgingspunkter. Denne deltaen endrer ikke noen av disse mekanismene.
