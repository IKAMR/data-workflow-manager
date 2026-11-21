# Data Workflow Manager v0.2.4

## Stabilisering av kjøring, flerjobbvisning og eksterne verktøy

Endringer siden **v0.2.3** (utviklingsløp v0.2.4-a1–a5):

- **Siegfried/PRONOM (a1):** Mer robust håndtering av ugyldige eller delvise Siegfried JSON-svar i store kjøringer. Gyldige batcher og tidligere fullførte data kan beholdes; feilsituasjoner håndteres med eksplisitt status og kontrollert fortsettelse i stedet for å presentere ufullstendige data som komplette. Historisk resultat-/proveniensgrunnlag skal ikke slettes ved feilretting.
- **Fortsett og Nullstill (a2):** Separate, eksplisitte jobbhandlinger for å fortsette en avbrutt/feilet kjøring eller nullstille jobbens kjørestatus etter bekreftelse. Work er autoritativt, og `.n5jobs` er en indeks; eksisterende Source, Work-resultater og tidligere kjøre-/vurderingshistorikk slettes ikke av disse handlingene.
- **Korrigert lagringsstatus (a3):** Etter vellykket lagring av Work og jobblisteindeksen ryddes uriktig «ulagret»-markering. Nedtrekkslister får lokal posisjonering i Qt-vinduet, uten å aktivere den tidligere problematiske globale hendelsesfiltreringen.
- **Kjøredetaljer (a4):** Bedre førsteplassering av plan, historikk og logg i eget vindu. Lesbare startbredder for historikktabellen; operatørens justerte kolonnebredder og indre paneldeling lagres mellom jobbskifter og omstarter. Tidligere lagret øvre deling beholdes. Visningsvalg endrer ikke jobbkilde eller resultatfiler.
- **Arkade 5 og Siegfried i Setup (a5):** Tidsbegrenset, asynkron oppstartskontroll med avgrenset søk etter eksisterende installasjoner, inkludert `PATH`, `C:\Prog`, `%ProgramFiles%`, `%ProgramFiles(x86)%`, `C:\Program Files`, `C:\Program Files (x86)`, `C:\Programfiler` og delt SIARD/Siegfried-installasjon. Status, sti, versjon og Siegfrieds PRONOM-signatur lagres brukerspesifikt under `%LOCALAPPDATA%\IKAMR\DataWorkflowManager\external-tools-v1.json` og kontrolleres på nytt når det er relevant. Ingen automatisk nedlasting eller installasjon; en eksplisitt valgt programsti overskrives ikke.
- **a5 Windows-testretting:** Sammenligning av simulerte Windows-programstier bruker Windows-stisemantikk i stedet for ren strenglikhet (`Q:/` og `Q:\` representerer samme testmappe). Q: i enhetstesten er fiktiv, ikke en faktisk bruker- eller arkivdisk.

## Kompatibilitet og sikkerhet

- Uendret: Noark 5 v3.1/4.0/5.0-regler og XPath-/XSD-testgrunnlag, Arkade 5-testdefinisjoner, 17-deljobbsprofilen, kildeevidens, tidligere rapporter, eksisterende `.n5jobs` og Work-data.
- Det er ingen endringer i Source-filer, automatisk faglig godkjenning, depotvedtak eller AIP-produksjon. **17/17 teknisk fullførte operasjoner betyr ikke at et uttrekk er faglig godkjent.** KS-rapporter forblir utkast der prosessen krever manuell vurdering.
- Arkade 5 v2.13.1 (23.09.2026) er den daterte versjonsreferansen i a5, **ikke** et løpende nettbasert «nyeste versjon»-oppslag. Arkade CLI må fortsatt installeres manuelt. Siegfried kan deles med SIARD Workflow Manager.
- SAFE MODE beholder sin forsiktige Qt-oppstart og omgår den valgfrie automatiske verktøyproben. Eksterne verktøy kjøres ikke på arkivuttrekk fra Setup.

## Ferdigstillelse fra a5 til v0.2.4

- `version.py` og `pyproject.toml` er endret til den ferdige versjonen `0.2.4`.
- a5-testens **bokstavelige alpha-versjonskrav** er byttet ut med en varig milepæltest som krever minst v0.2.4-a5 og godtar sluttversjon. Funksjonelle a1–a5-tester og tidligere testvakter skal fortsatt kjøres.
- Releasehistorikken er utvidet med nøyaktig én ny `## v0.2.4`-seksjon, uten å fjerne tidligere releaser. Egen test kontrollerer historikk, versjonsfiler og at den gamle alpha-vakten ikke gjeninnføres.
- Ingen test er hoppet over eller deaktivert for å få release-versjonen grønn. Distribusjonspakken inneholder ferdige filer, uten manuelle etterpatcher.

## Gjenstående arbeid etter denne releasen

1. **Resultatvisninger og faglig forståelse:** Bedre samlet tilgang til DWM XPath, Arkade 5, Siegfried/PRONOM, XSD og KS-funn; dokumentert kilde, faktisk teststatus, arkivdel og individfunn må ikke blandes eller dobbelttelles.
2. **Feil i tidligere prosessering:** Identifisere og rette reelle feil før videre presentasjonsarbeid, blant annet kilde-/dokumentreferanser, presis fil-/hash-evidens, store uttrekk, ekstern CLI-robusthet og avhengighetsrekkefølge der praktiske kjøringer avdekker feil.
3. **Praktisk depotkontroll:** Teste visninger på tre fullførte WebSak-uttrekk (1525_004–006) og et stort uttrekk (1502_024) uten å omklassifisere teknisk fullført til faglig godkjent.
4. **Utvidet Wiki:** Videreføre visuell skjerm-for-skjerm-veiledning og teste publikumslesbarhet i den separate GitHub Wiki-en.

## Releasekontroll før commit, tag og publisering

Utgangspunkt: committet `v0.2.4-a5` på `a270-280`, SHA `a6fc257809aa149b77c115392475b4488e3babfe` (inkludert den korrigerte Windows-stitesten).

1. Pakk ut release-deltaen direkte over **samme** a5-revisjon på arbeidsgrenen.
2. Kontroller `py -c "from version import VERSION; print(VERSION)"` → `0.2.4` og kjør `py tools/release_gate.py`.
3. Kjør full `test.bat` på Windows; forvent **null feil**. Resultatet skal lagres under `docs/test-results/v0.2.4.md`. Dersom en eneste test feiler, må den undersøkes før release – ikke ignorer den eller reduser testomfanget.
4. Åpne ekte Qt/Windows GUI. Verifiser eksisterende jobbliste, Kjøredetaljer, Fortsett/Nullstill, Setup-oppstartskontroll, bevarte resultater, og at nye verktøystier ikke overstyrer brukerens eksplisitte valg.
5. Etter grønn fulltest og operatørgodkjenning håndterer utvikleren selv commit, push og GitHub-release/tag `v0.2.4`.

**Begrensning ved pakking:** Full `test.bat` for hele Windows-repositoriet kan ikke gjennomføres uten tilgang til den komplette lokale koden og Windows-miljøet. Release-gaten og målrettede tester er ment som tillegg, ikke erstatning. Det må derfor ikke rapporteres at hele testpakken er grønn før Windows-kjøringen er dokumentert.
