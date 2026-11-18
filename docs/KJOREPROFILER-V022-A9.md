# DWM v0.2.2-a9 – felles kjøreprofiler og redigerbar deljobrekkefølge

## Grunnlag og leveranse

Delta over **committet v0.2.2-a8**. a7-avhengighetsmodellen og de tre innebygde a8-profilene er beholdt. Ingen commit/push utføres av leveransen. Ingen jobb- eller Source/Work-data skal inkluderes i Git.

## Setup → Arbeidsflyt

- Ett synlig standardprofilvalg for nye Noark 5-jobber: **Standard DWM**, **Avansert DWM** og **Komplett DWM + Arkade 5**, samt lagrede brukerprofiler.
- De eldre `noark5_*`-sekvensene vises i en sammenleggbar **Eldre profiler**-oversikt, ikke som et konkurrerende standardvalg. Eksisterende lagrede arbeidsflyter og de gamle profil-ID-ene slettes ikke.
- Knappen **Rediger deljobber og rekkefølge…** åpner teknisk profilredigering. Merk av/fravelg tekniske kontroller og bruk **Flytt opp/ned**. Arkade 5 Noark (A150) og Arkade 5 PRONOM (A160) er uavhengige valg.
- **A130** (DWM Noark 5 XPath-master) må være valgt for en profil som skal ha hele evidens-/KS-kjeden. Obligatoriske etterjobber **A210, A220, A230, A240, A250 og A260** legges til automatisk; **A200** bare når minst én Arkade-kontroll er valgt.
- Redigering av en innebygd profil oppretter **en egen navngitt kopi**. En egen profil kan endres uten å endre oppsettet i eksisterende `.n5jobs`.
- Alt redigeringsarbeid i Setup er **midlertidig** inntil den vanlige **Lagre**-knappen nederst i Setup bekreftes. **Avbryt** forkaster endringene.

## Nye og eksisterende jobber

Nye Qt-jobber får brukerens valgte standardprofil som nøyaktig `workflow_ids` ved opprettelse. Dette gjelder også den tidligere Avansert-dialogen. I Enkel modus brukes profilen på nye uttrekk, mens fire vanlige kontrollavkryssinger fortsatt gir enkel overstyring. Egendefinerte tilleggskontroller og rekkefølge på eksisterende jobber beholdes ved senere åpning i Enkel modus.

En profil er **en mal, ikke en binding til en eksisterende jobb**. Endring av malen kan derfor ikke endre tidligere resultatdata, arbeidsflytcursor eller historiske profiler uten eksplisitt per-jobb-handling. Per-jobb-rekkefølge kan fremdeles redigeres med den eksisterende a6-funksjonen i begge moduser. Profilvalg på en allerede startet jobb er fremdeles blokkert av a8-grensesnittet.

Gammel klient- og sekvenskode bruker fortsatt `noark5_discovery_workflow`; a9 lagrer en konservativ kompatibilitetssekvens ved siden av `noark5_default_run_profile`. Egendefinerte profiler kan ikke representeres eksakt i det gamle feltet. **Det er den nye a9-standarden som er autoritativ i Qt**.

## Avhengigheter og testtilfeller

- A100–A190: Faglige tekniske kontroller kan omordnes, så lenge eventuelle eksplisitte forutsetninger overholdes.
- A190 refererer nå til faktisk registrert `run_noark5_xpath_regression_2026` (tidligere feilaktig ID uten `_2026`).
- A200: Betinget import av Arkade-evidens ved A150 og/eller A160.
- A210–A260: Kanonisk evidens, ekstern kildeanalyse, dekningsrevisjon, resultatvisninger, depotrapport og KS-utkast. Alltid etter relevante tekniske kontroller, med obligatoriske forutsetninger.
- En egendefinert profil som omfatter bare Arkade Noark (ikke Arkade PRONOM), og omvendt, skal valideres og kunne lagres.
- En ekstra avkryssing i Enkel modus skal ikke stille om en lagret jobbs ikke-synlige supplerende kontroller eller egen rekkefølge.

## Foreslått praktisk Windows-kontroll

1. Åpne Setup → Arbeidsflyt. Bekreft at gamle forhåndsvalg ikke vises i den øverste nedtrekkslisten.
2. Velg **Standard DWM** → **Rediger deljobber og rekkefølge…**. Flytt Siegfried til første tekniske posisjon og velg bare Arkade Noark. Lagre som `IKAMR – testprofil`.
3. Avslutt Setup med **Avbryt** og kontroller at ny profil ikke ble lagret. Gjenta og velg **Lagre**; åpne Setup på nytt og kontroller at profilen er valgt standard.
4. Start **Ny kontroll** i Enkel modus og registrer et nytt, ubrukt testuttrekk. Bekreft at nye jobbens arbeidsflyt har riktig rekkefølge og A200–A260.
5. Legg til et annet testuttrekk med annen profil. Bekreft at JOB-001 beholder sin egen `workflow_ids`.
6. Åpne Avansert, kontroller rekkefølge og alle avhengighetsnumrene. Lagre og gjenåpne `.n5jobs`; kontroller samme profil og egne Work-plasseringer.
7. Endre senere standardprofil og kontroller at de eksisterende jobbene **ikke** endres.

## Senere mikrotester

A9 aktiverer ikke skjulte mikrotestbrytere. Antall tester i installert Arkade CLI må hentes fra *faktisk versjon* og støttede CLI-parametere, ikke hardkodes som 52, 54 eller 64. Framtidig mikronivå skal skille mellom å slå av en test i kontrollmotoren og å filtrere resultatvisningen.

## Verifikasjon

34 målrettede a7/a8/a9-regresjonstester bestod i et rekonstruert, isolert Python-miljø; koden er syntakskontrollert. Full `test.bat` i hele repoet og reell Windows/PySide6 GUI-test er ikke kjørt i dette miljøet. Dette er et utviklingskontrollpunkt og ikke en release.
