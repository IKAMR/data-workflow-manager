# v0.2.2-a1.4 – Ny kontroll i Enkel modus

**Rettelsesdelta over v0.2.2-a1.3**, som legges over a1.2 og committet a1.1. Programversjonen er fortsatt `0.2.2-a1`. Ingen spesial-BAT, installasjonsendringer, Git-operasjoner eller endringer i Source/Work.

## Hva ble rettet?

Tidligere «Ny kontroll»-knapp ble skjult i a1.2 og håndteringen ble feilaktig endret til «Legg til jobb». Dermed måtte brukeren åpne Avansert modus og forstå begrepet jobbliste for å komme tilbake til et helt tomt utgangspunkt.

Enkel modus har nå **to tydelige handlinger**:

| Knapp | Betydning |
| --- | --- |
| **Ny kontroll** | Lukker gjeldende arbeidsflate og starter med helt tom Source/Work og ingen valgte uttrekk. Tidligere lagrede filer og resultater beholdes. |
| **Legg til uttrekk** | Oppretter et nytt utkast i samme kontroll uten å fjerne de andre uttrekkene. De registrerte uttrekkene vises også i Avansert modus. |

Enkel modus viser nå «Uttrekk i denne kontrollen», «Velg uttrekk», «Lagre» og «Lagre som…». Programmet bruker fortsatt én og samme `.n5jobs`-modell som Avansert modus; navnene er bare forenklet for brukeren.

## Sikkerhet ved «Ny kontroll»

1. Ved eksisterende uttrekk vises en bekreftelse. Et ufullstendig utkast kan bare forkastes etter eksplisitt bekreftelse.
2. Finnes en lagret `.n5jobs`, forsøker DWM å lagre ferdige endringer før den åpne arbeidsflaten nullstilles. Ved lagringsfeil beholdes den åpne kontrollen.
3. Finnes flere jobber, men ingen lagret fil, spør DWM om **Lagre / Forkast / Avbryt**. Hvis filvelgeren avbrytes, beholdes hele gjeldende kontroll.
4. Når nytt tomt kontrolloppsett åpnes, nullstilles bare DWMs aktive jobbmodell og feltene i GUI; ingen eksisterende `.n5jobs`, Source, Work, rapporter eller kontrollresultater slettes.
5. Ny kontroll er sperret så lenge en kjøring pågår.
6. Ingen kontrollkjøring startes automatisk av «Ny kontroll» eller «Legg til uttrekk».

## Brukertest

1. Pakk ut `v0.2.2-a1.4.zip` over **a1.3**, og kjør `test.bat`.
2. Åpne en allerede kjørt jobb (f.eks. 1525_004) i Enkel modus. Kontroller at **Ny kontroll** vises øverst, foran «Avansert modus».
3. Klikk **Ny kontroll** og bekreft. Source og Work skal være tomme, og visningen skal gå til Source-trinnet. Kontroller at den gamle `.n5jobs` fremdeles kan åpnes.
4. Velg Source og Work for et annet uttrekk. Kontroller at dette blir første uttrekk i den nye kontrollen uten kjøring. Klikk **Lagre** for å gi kontrollen eget filnavn.
5. Klikk **Legg til uttrekk** to ganger og velg to andre Source/Work-par. Kontroller at tre uttrekk står i nedtrekket og kan velges enkeltvis, og at de også vises samlet i Avansert modus.
6. Klikk **Ny kontroll** igjen, og kontroller at den lagrede kontrollen med tre uttrekk bevares og kan gjenåpnes.
7. Test også **Ny kontroll** når gjeldende kontroll med flere uttrekk ikke er lagret. Avbryt i «Lagre før ny kontroll?»; den eksisterende åpne kontrollen skal ikke forsvinne.

**Målrettede tester i isolert miljø:** 31 bestått. Testene inkluderer sikker nullstilling, automatisk lagring av eksisterende kontroll, avbrutt filvalg, lagringsfeil, ufullstendig utkast, gammelt Work-oppsett og tre uttrekk i felles API. Full `test.bat` og visuell Windows/PySide6-test er ikke utført her.

## Teknisk avgrensning

Dette er en retting av navigasjon/arbeidsflate og tilhørende regresjonstester. Verken den delte DWM-kjøremotoren, jobblisteformatet, kontrollresultatene eller depotrapportene er endret. En fullstendig vurdering av batchkjøring er separat fra denne testen.
