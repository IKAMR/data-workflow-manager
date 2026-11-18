# DWM v0.2.2-a8 – kjøreprofiler

**Delta over committet a7**, inkludert den grønne a7.1-regresjonsrettelsen. Pakken er ikke en fullstendig DWM-installasjon. Ingen Git-operasjoner er utført.

## Tre nye kjøreprofiler

* **Standard DWM** (ny standard): metadata, XML/XSD, arkivstruktur, DWM XPath 2026, Siegfried PRONOM og A210–A260. Ingen Arkade.
* **Avansert DWM**: Standard + DWM Core, U1 og XPath-regresjon. Ingen Arkade. Supplerende kontrollfamilier kan overlappe ordinær XPath og er ikke automatisk flere normative Noark-krav.
* **Komplett DWM + Arkade 5**: Avansert DWM + Arkade 5 Noark (A150) og Arkade 5 PRONOM (A160) som **to separate** kontroller.

Både Enkel og Avansert modus får **Kjøreprofiler…**. Dialogen viser konkret deljobbrekkefølge med A-nummer og separate Arkade-avkryssinger. Valget gjelder aktiv jobb før første kjøring. Ingen eksisterende, allerede kjørte jobber får arbeidsflyten automatisk endret. Brukeren kan lagre profiler under egendefinerte navn og velge standard for nye jobber. Eksisterende historiske workflow-profiler og -ID-er blir stående; a8 tilfører et brukerrettet lag over dem.

**Viktig:** Standardvalg i a8 lagres som `noark5_default_run_profile` i DWM-innstillinger; egendefinerte profiler som `noark5_custom_run_profiles`. Nye kontroller i Enkel modus arver profil når deres synlige kontrollvalg samsvarer med standardprofilen. Allerede eksplisitt valgte avkryssinger beholdes. Endres deljobbvalgene individuelt i Enkel modus, blir dette et tilpasset oppsett. Ved ny jobb må en individuell ikke-standardprofil velges for den jobben; brukerstandard gjelder som standard.

Nye profiler opprettes ved å lagre en variant av en av de tre profilene med valgfrie Arkade-deljobber. Fri redigering av samtlige tekniske deljobber er **ikke** implementert i a8. For nå brukes den eksisterende avanserte arbeidsflytredigeringen til andre endringer. Profilen lagrer nøyaktige deljobb-ID-er, mens det er jobben som eier faktisk kjøreoppsett.

### Evidens og avhengigheter

* A150/A160 er uavhengige valg; A200 inkluderes kun dersom minst én Arkade-test er valgt.
* A210–A230 og A260 inngår i alle tre nye profiler. A240–A250 kommer før A260. Bevar kildeproveniens og ikke slå sammen Arkade- og DWM-testtall til falskt sammensatte bestått-tall.
* Skjermvalgene er ikke en per-test bryter og endrer ikke `sf`-motor, Arkade CLI eller den generelle JobRunner.

### Fremtidig mikrotest-nivå – ikke aktivert i a8

Planlegg et versjonert testregister med `tool`, `tool_version`, `test_id`, `rule_version`, `enabled`, `reason`, og `source_profile`, samt faktisk kapabilitetssjekk før man forsøker å deaktivere enkeltkontroller. **Arkades antall tester skal registreres dynamisk fra installert versjon og faktisk testrapport**, aldri låses til eldre observasjoner som 52, 54 eller 64. Det er ikke bekreftet at Arkade CLI støtter individuell kjøring av samtlige test-ID-er; om ikke må DWM vise filtrering av evaluering/rapportering som nettopp det, ikke som deaktivert utførelse. Beslutninger om mikrokontroller skal logges som egen evidens og påvirke dekningsrapporten.

## Testing

Målrettede rene Python-tester: **8 bestått**. Full Windows `test.bat`, faktisk GUI-kjøring og Arkade/Siegfried-test på reelle uttrekk gjenstår hos brukeren. For de allerede fullførte 1525_004–006, bruk **nye kontroller eller eksplisitt a7-etterbehandling** i stedet for å endre den fullførte kjøringshistorikken uten sporbar beslutning.

Praktisk prøve: åpne ny Enkel-kontroll → velg kjøreprofil → registrer Source/Work → kontroller faktisk deljobbliste i Avansert → prøv kun Arkade Noark og kun Arkade PRONOM som to egne tilfeller → bekreft at A200 er betinget og A210–A260 alltid er med → lagre/gjenåpne `.n5jobs` → start først når den viste listen stemmer.
