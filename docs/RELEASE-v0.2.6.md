# Data Workflow Manager v0.2.6

## Stabilisering av evidensdekning, Qt-arbeidsflate og releasekontroller

Endringer siden **v0.2.5** (utviklingsløp v0.2.6-a1–a3):

- **Dokumentasjonsstruktur og vedvarende QA (a1):** Teknisk dokumentasjon er omorganisert med `docs/README.md` som inngang, tematisk inndeling og bevart historikk. `tools/docs_layout.py` og `tests/test_docs_layout.py` hindrer nye løse alpha-notater i `docs/` og kontrollerer at dokumenter beholdes på riktig sted. Eksisterende historiske kilder og ankre er bevart når de kreves av tester og kode.
- **Klarere releaseovergang (a1):** `tools/release_gate.py` kontrollerer samsvar mellom app- og distribusjonsversjon, aktuell testkode og releasehistorikk. `tools/release_prepare.py` gir en kontrollert utviklerprosedyre for alpha-til-sluttversjon, med separate tester for å hindre hardkodede alpha-låser. En ferdig delta-ZIP inneholder allerede komplette versjons- og dokumentasjonsfiler; ingen manuelle patcher er nødvendige.
- **Filformatvurdering i Setup (a2):** Forbedret oppstartskobling og Qt-layout for filformatvurdering, med mer lesbare, tekstbrytende forklaringer og tydelig inndeling mellom vurderingsgrunnlag, evidens og Siegfried/PRONOM. Valgte formatkilder videreføres, uten å endre hvilken kontrollmotor som er autoritativ eller automatisk endre lagrede brukerinnstillinger.
- **A210 og Arkade PRONOM-evidens (a3):** Retter tilfeller der A160 har koblet PRONOM-statistikk til en annen Arkade-import enn den siste Noark-rapporten som A210 velger. A210 kan finne og verifisere statistikk fra en annen import tilhørende **samme jobb og Work**, etter kontroll av originalfil, bevart CSV, manifest og SHA-256. Det er ikke tilstrekkelig at Arkade CLI rapporterer teknisk suksess.
- **A230 Evidensdekning og fortsettelse (a3):** Når bare `arkade_pronom` mangler, kan A230 kontrollere om en entydig, verifisert tidligere PRONOM-kilde kan gjenkobles. Da oppdateres avledede A210/A220-indekser, med bevaring av tidligere versjoner under Work-historikk, uten omkjøring av tidligere deljobber eller endringer i Source. Manglende, uverifiserbar, tvetydig eller feiltilknyttet evidens gir fortsatt feil med tydeligere årsak i `evidence-audit.json`.
- **Regresjonstester:** Nye tester dekker A230-gjenkobling, feiltilfeller og tilbakeføring ved feil, Qt-oppsett, dokumentasjonsstruktur samt alpha-/releaseovergang. Endringene fra v0.2.5 for A170/A180, sikker modusveksling og sekvensiell flerjobbfortsettelse beholdes.

## Kompatibilitet og faglige avgrensninger

- Eksisterende `.n5jobs`-jobblister, Source, Work, A100–A260-kjøreprofiler, Arkade 5, Siegfried/PRONOM, DWM-/KDRS-evidens, rapportutkast og tidligere arbeidsflythistorikk videreføres.
- Den automatiske gjenkoblingen er begrenset til entydig verifiserbare Arkade PRONOM-kilder for **samme jobb**. Manglende evidens erstattes aldri med tomme eller oppdiktede data. Originale arkivuttrekk og importerte kildefiler skal ikke endres av evidenskontrollen.
- Ingen nye normative Noark 5-regler eller påstand om full dekning av Noark 5 v3.1, 4.0 og 5.0 er innført. Teknisk gjennomført eller koblet evidens er **ikke** depotfaglig godkjenning. KS-/depotrapporter forblir utkast fram til manuell vurdering.
- Testene for A230 omfatter syntetiske, isolerte Work-strukturer. Kjøring på flere virkelige uttrekk, inkludert store eller historisk sammensatte Arkade-importer, må fremdeles kontrolleres praktisk. Et tidligere A230-avvik skal ikke omklassifiseres til godkjent uten verifiserte kilder.

## Releasekontroll før commit, tag og publisering

Utgangspunkt: committet `v0.2.6-a3` på `main`, SHA `0c3ffeff8dbba70f1e08b77c29d984438e3bf5d1`. Den committede a3-fulltesten rapporterer **4 771 tester, 4 737 bestått, 0 feil og 34 hoppet over** etter dokumentasjonsrettingen. Dette er *ikke* et fulltestresultat for sluttversjonen.

1. Pakk release-deltaen direkte over denne revisjonen. Sjekk at `version.py` og `pyproject.toml` er `0.2.6`, uten `-a3` eller `a3`.
2. Kjør `py tools/release_gate.py`, `py tools/release_prepare.py --check` og `py tools/docs_layout.py --check`; alle må bestå.
3. Kjør **hele** `test.bat` på Windows med den endelige `0.2.6`-versjonen. Kontroller `docs/test-results/v0.2.6.md` og null feil. Ingen tester skal kobles ut for å gjøre releasen grønn.
4. Start GUI med `start.bat`, kontroller eksisterende jobblister, Filformatvurdering og A230 ved fortsettelse fra lagret kontrollpunkt. Ikke nullstill Work eller slett historikk for å teste rettingen.
5. Først etter grønne kontroller håndterer utvikleren selv commit, push, tag og GitHub-release.

## Videre utvikling

Fortsett praktisk volumtesting av A170/A230 og sammenstilling av resultatkilder, samt kontroll av fil-/hash-evidens, opptelling per arkivdel og koblingen mellom teknisk status og faglig KS. Forbedre brukerveiledningen i GitHub Wiki parallelt med depotets praktiske tester.
