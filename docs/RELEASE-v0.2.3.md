# Data Workflow Manager v0.2.3

## Noark 5: fullstendige funn, Veiledet KS og kildebundet XML-inspeksjon

Endringer siden **v0.2.2**:

- **Veiledet KS:** Lineær gjennomgang av individuelle funn med kilde-/testvalg, Noark-metadata, observerte XML-verdier, dokumenterte avleveringsbetingelser og faglige kommentarer. Den opprinnelige tekniske statusen endres ikke av en vurdering.
- **Arkade og DWM som separate kilder:** Store normaliserte Arkade 5-rapporter leses strømvis og indekseres kildebundet i SQLite. Alle dokumenterte funn kan behandles sidevis og eksporteres i fullstendige CSV-/JSONL-register, fremfor at bare de første radene fremstilles som komplett resultat. Siegfried/PRONOM-statistikk er separat formatidentifikasjon, ikke Noark 5-beståtte tester.
- **Noark 5-avleveringskontroll:** Det dokumenterte første regelutvalget M051–M054 dekker avleveringsverdier for arkivdel, sak, journalpost og dokumentbeskrivelse. Kontroller knytter faktisk XML-verdi, arkivdel, systemID, XPath/linje og regel-/kildeversjon til individfunn. Versjonsgrunnlag, betingelser og ikke vurderte forhold er uttrykkelige; dette utgjør ikke full normativ kravdekning for Noark 5 v3.1, 4.0 og 5.0.
- **Faglig vurderingshistorikk:** Append-only Work-hendelser og egne manuelt opprettede funn håndteres uten de eldre grensene på 2 000 poster. Vurderte *unike funn* og antall historiske hendelser skilles. Originale vurderinger og kildebevis bevares.
- **Komplette rapportutkast:** Kildebundne KS- og depotrapporter med alle individuelle funn og valgte vurderinger, sidevis HTML, CSV/JSONL, kilde-/SHA-256-manifest og separate mottakervalg. Avvik og forbehold fremgår; rapportene er fortsatt **UTKAST – IKKE GODKJENT**.
- **Store Work-resultater:** Strømlesing og SHA-256-verifisering for store XPath-masterfiler og depotrapporter; avstemming videre gjennom A11/A12/A260. Størrelsesbegrensede forhåndsvisninger skilles fra komplette funnregistre.
- **Kontrolloversikt og avstemming:** DWM XPath og Arkade 5 Noark telles hver for seg. Bestått, feil, advarsel, avbrutt, ikke kjørt, ikke relevant og ukjent holdes atskilt; hovedtall sammenholdes med dokumenterte arkivdelstall uten dobbelttelling eller ukjent=0.
- **XML-evidens i Veiledet KS:** Funn med faktisk dokumentert XML-fil/linje kan inspiseres i valgt Source. Dokumenterte systemID-er, objekthierarki, faktisk XPath og observerte verdier vises uten å finne på manglende forekomster, linjer eller søskentotaler. SHA-256 for *Arkade-rapport* må ikke forveksles med verifisert SHA-256 for *Source-XML*.
- **Kilde-QA:** Read-only avstemming av DWM-katalog mot historiske KDRS Query Standard/U1/U2 og identitetskontroll av Noark 5 v3.1/4.0/5.0-XSD-er. Dette er ikke en bekreftelse på full semantisk paritet mellom Saxon/XQuery og DWM/lxml.
- **Stabilisering:** Reparerte Windows 8.3-/lange stinavn med filidentitet fremfor strenglikhet, kilde-/jobbtilknytning og eldre kapasitetsgrenser i KS-etterbehandling. Source og historiske Work-resultater beholdes uendret ved lesing og rapportering.

## Kompatibilitet og kjøring

- Eksisterende `.n5jobs`-jobblister, A100–A260-arbeidsflyt, kjøreprofiler og DIAS-funksjoner fra v0.2.2 videreføres.
- `version.py` og `pyproject.toml` er satt til den endelige versjonen `0.2.3`. Alpha-låste versjonstester for a4/a13/a15/a17/a18 er erstattet med milepælsbaserte kontroller, uten å endre funksjonstestenes formål.
- Ingen kildeuttrekk, gamle Work-resultater, versjonerte Noark-kilder eller normative regler endres av denne release-oppryddingen. Ingen ny AIP-pakkemotor er innført.

## Kjente grenser og uferdig arbeid

- Full Noark 5 v3.1/4.0/5.0-kravdekning og full, evidensbasert Saxon/lxml-paritet er **ikke** dokumentert.
- Formell arkivskaperaksept, depotgodkjenning, journalføring og integrasjon av valgt KS-evidens i den eksisterende DIAS AIP-produksjonen gjenstår. **Ingen automatisk godkjenning eller AIP** følger av teknisk OK.
- Noen eldre rapport-/JSON-adaptere har fortsatt avgrensninger; a17/a18 løser den ordinære KS-/Work-banen og utvalgt A260-etterbehandling, ikke alle historiske lesere.
- Større XML-/JSON-token, direkte kildeoppslag og lange nettverksstier har ressurs- og sikkerhetsgrenser. Manglende kildehash eller ikke-entydig linje må vises som ikke verifisert, ikke som et attestert treff.

## Releasekontroll før tag/opprettelse

1. Kjør `py tools/release_gate.py` og full `cmd.exe /c test.bat` etter utpakking i repo-roten.
2. Kontroller i Windows/PySide6 en faktisk jobb, også eldre Work, sidevis KS, bevarte kommentarer, kildelinjer, store rapporter og A260-eksport. Verifiser gjerne 1525_004–006 og 1502_024.
3. Verifiser versjon `0.2.3` og at rapportene fortsatt viser **UTKAST – IKKE GODKJENT**.
4. Først etter grønne tester og praktisk godkjenning committer/pusher utvikler og oppretter Git-tag/release `v0.2.3`.

**Base:** `a220-a260-taa`, siste committede alpha `v0.2.3-a19`, Git-SHA `bb683a98fbc27b43ee8ae77d13ad302977f33f65` (inklusive Windows-sti-test med `samefile()`). Release-deltaen endrer ikke arbeidsflytlogikk.
