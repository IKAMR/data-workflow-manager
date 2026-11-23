# Data Workflow Manager v0.2.5

## A170, aktiv modusveksling og samlet fortsettelse av jobblister

Endringer siden **v0.2.4** (utviklingsløp v0.2.5-a1–a3, inkludert oppstartsrettelsen):

- **A170 / store arkivstrukturer:** Den definisjonsstyrte XPath-analysen bruker mer avgrensede arkiv- og arkivdelutvalg og opptellinger, og skal ikke skjule en XPath-motorfeil som et tomt, fullført resultat. Tidligere utviklet strømmelesing for den eldre A170-kjøreveien er integrert. De to kjøreveiene er forskjellige og skal ikke omtales som en felles fullstendig strømmemotor.
- **A120/A170/A180-integrasjon:** Den tidligere separate utviklingsgrenen med strømbasert arkivdeltilknytning og utvidede arkivdelmetadata er tatt med. Justering av deljobbmarkøren ved gjenopptakelse inngår. Originale XPath-/Noark-kilder, Work og tidligere evidens skal ikke omskrives av dette.
- **Enkel og Avansert modus:** Bytte mellom visningene under pågående jobb er en ren visningsoperasjon. Aktiv jobb, faktisk fremdrift, logg og kjørende worker forblir felles; modusbytte skal verken registrere jobben om igjen eller starte ny kjøring.
- **Fortsett og kjør resterende:** En samlet handling finnes i begge moduser. `Ferdig` hoppes over, `Feil` fortsetter fra verifisert feilet deljobb, `Venter ved kontrollpunkt` fortsetter fra checkpoint, delvis `Klar` fortsetter fra lagret markør, og ny `Klar` (0 %) starter fra deljobb 1. Handlingen krever bekreftelse og gjenbruker eksisterende sekvensiell worker og API-et for Work-først-kjøring. Ingen automatisk nullstilling eller omkjøring av fullførte kontroller.
- **Kontrollert batchavslutning:** Neste jobb starter bare når forrige jobb er teknisk `Ferdig`; feil, avbrudd og checkpoint-pause stopper sekvensen. Uavklarte eller frakoblede jobbstatuser blokkerer samlet start fremfor å bli tolket som nye jobber.
- **Qt-oppstart:** Oppstart av `python -m gui_qt`/`start.bat` kaller igjen GUI-hovedfunksjonen. En regresjonstest verifiserer modulens oppstartsvakt. Manuell Windows-oppstart er kontrollert etter rettelsen.
- **Release-stabilisering:** Applikasjon og distribusjon bruker begge `0.2.5`, uten alfasuffiks. A3-versjonstesten er erstattet av en varig milepælkontroll som godtar sluttversjonen uten å svekke kontrollene av GUI-kobling og stoppsemantikk. Release-historikken er bevart.

## Kompatibilitet og faglige avgrensninger

- Eksisterende `.n5jobs`, Source, Work, jobbløp, logghistorikk, Siegfried-kontrollpunkter, DWM-/Arkade-/KDRS-evidens og rapportutkast videreføres. Fullført teknisk kjøring betyr **ikke** at uttrekket er faglig eller formelt godkjent.
- Ingen utvidelse av full normativ dekning for Noark 5 v3.1, 4.0 eller 5.0 hevdes. De enkelte avleveringsreglene må skilles fra produksjonsverdier og generelle XPath-observasjoner. Faglige kilder skal hentes fra IKAMRs versjonerte Noark-referanser i `digital-archive-workflow`, ikke fra ustabile eksterne dokumentlenker.
- Testene for A170 på små syntetiske XML-filer dokumenterer ikke automatisk korrekt ytelse eller minnebruk for alle produksjonsnære XML-filer på flere gigabyte. Både storfilkjøring og praktisk gjenopptakelse må kontrolleres på virkelige uttrekk før slike egenskaper kan anses fullt verifisert.
- Resultatvisninger, dokumentreferanse-/filintegritet, opptelling per arkivdel og videre volumtesting er fortsatt forbedringsområder. Ingen endring av originalfiler i Source eller automatisk depotvedtak er innført.

## Kontroll før release

1. Pakk release-deltaen direkte over den committede v0.2.5-a3-koden på grenen `a281-300`; behold eventuell eksisterende Work og `docs/test-results/`.
2. Kontroller `py -c "from version import VERSION; print(VERSION)"` (forventet `0.2.5`).
3. Kjør `py tools/release_gate.py`. En ferdig release skal gi null blokkeringer og bevare hele `docs/RELEASES.md`.
4. Kjør full `test.bat` med faktisk sluttversjon, og bekreft null feil. Testoppsummeringen skal skrives under `docs/test-results/v0.2.5.md`. Enhetstester alene erstatter ikke denne Windows-kjøringen.
5. Start GUI med `start.bat`, kontroller åpning av eksisterende jobbliste og navigering i begge moduser. Verifiser deretter samlet Fortsett/Kjør resterende med en egnet testjobbliste, og kontroller at gjenopptakelse ikke skriver om tidligere Work-evidens.
6. Brukeren utfører selv Git commit, push og eventuell merge/tag/release etter godkjente tester. Det skal ikke opprettes ny tag før sluttversjonen er testet.

### Testgrunnlag og gjenstående verifisering

Siste rapporterte fulltest fra utviklingsversjonen v0.2.5-a3: **4 733 tester, 0 feil, 35 hoppet over**. GUI-start med a3-fix1 er bekreftet i praksis. Dette er ikke et fulltestresultat for den ferdige `0.2.5`-versjonen. Endelig antall og resultat må hentes fra ny kjøring av `test.bat` etter denne release-deltaen.
