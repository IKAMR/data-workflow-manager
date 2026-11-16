# Data Workflow Manager v0.2.1

## Noark 5 – kontroller, kildegrunnlag og faglig depotvurdering

- **Kildesporbar Noark 5-kontroll:** Dokumentert kobling mellom versjonene 3.1, 4.0 og 5.0, XSD-/XPath-kontroller og KDRS Query Standard/U1/U2. Kravkandidater, faktiske kontrollimplementasjoner og resultatbevis holdes adskilt. FEIL/WARNING/NOTE kan brukes til målrettet gjennomgang av QA-resultater.
- **KDRS Query:** Import og kildekontroll av historiske tekstresultater, med eksplisitte sammenligninger mot DWM/lxml der både feltmapping og XML-bytehash gir grunnlag. Full Saxon/lxml-paritet eller komplett normativ Noark-dekning er **ikke** attestert.
- **Funn og forklaringer:** Samlet vurderingsflate for DWM, Arkade 5 og valgte KDRS-resultater. Arkades tekniske status beholdes uendret. N5.22 viser hvorfor journalposter med `Journalført` er et avleveringsavvik etter Noark 5 v5.0, vedlegg 1, M053, selv om verdien er en gyldig kode i andre sammenhenger. Kilde-/XML-linjenumre vises i eget detaljvindu; dette er ikke en rå-XML-viser.
- **Faglige merknader:** Brukeridentifiserte og kildebundne vurderingshendelser i Work med begrunnelse og individuelt valg om en kommentar skal inngå i KS- og/eller depotrapport. En faglig kommentar overstyrer ikke teknisk teststatus.
- **Rapporter:** Separate utkast til kvalitetssikring hos arkivskaper og depotets ferdigstilling/godkjenning. Eksisterende Full-rapport (a20-motor) med vedlegg A–D brukes videre. Eksport skjer til ny mappe, med sporbar evidens og SHA-256-manifest. DIAS/METS-fakta gjengis som kildeopplysninger, ikke automatisk verifiserte konklusjoner.
- **Depotets sjekkliste:** 49 manuelle kontrollpunkter og åtte faglige tekstfelt med lagret historikk og uavhengig rapportmottaker. METS/Work-kilder brukes som dokumentasjon; ingen kontrollpunktstatus godkjennes automatisk.
- **DIAS/METS-metadata:** De 47 kanoniske Arkade 5-feltene og fire separate depotfelt kan sammenlignes mot historisk import og oppdateres som gjeldende Work-verdier. Ytre `info.xml` og indre `dias-mets.xml` identifiseres og bevares som separate SHA-256-verifiserte kilder. Per-felt-kildehenvisning, markering av faktisk endring og egne visninger for utvidede opplysninger og tekniske XML-forekomster reduserer duplisering. Rå XML-kilder overskrives aldri.
- **Resultatnavigasjon:** Under Faglig vurdering er **Periodevurdering** og **Depotvurdering** direkte knapper med markering av aktiv visning. Eksisterende resultatfaner og andre hovedgruppers navigasjon er beholdt.

## Avgrensninger

- Teknisk PASS, ferdig sjekkliste og generert rapport innebærer **ikke** depotgodkjenning eller beslutning om sletting av kildemateriale.
- Originale Source-uttrekk, Arkade-/KDRS-evidens og tidligere rapportversjoner endres ikke av vurderinger eller metadataredigering i Work.
- Fullstendig teknisk XML-inventar gjelder innleste, verifiserbare METS-kilder innenfor dokumenterte grenser (**32 MiB / 180 000 XML-elementer per kilde**). Det er ikke en garanti for at enhver SIP/AIP eller alle metadata i en ukjent kildevariant er støttet.
- `extraction_date` er ikke endelig mappet til ytre `info.xml`; mulig indre `ArchiveExtraction/@VERSDATE` er ikke automatisk semantisk likestilt. Kildedifferanser skal vurderes faglig.
- Den felles, profilbaserte sjekklisten, generisk depotprofil med logo/layout, lineær kontrollflyt og endelig godkjenningsbrev er videre arbeid, ikke del av v0.2.1.

## Releasegrunnlag og kontroll

- Utviklingsgrunnlag: committet `v0.2.1-a16`, GitHub `main` commit `c8aedccb331213fcf5faaceadff7ad7ce4f8d8c9`, inkludert GUI-deltaene a16.1 og a16.2.
- Sluttversjon: `version.py` = `0.2.1`; Python-distribusjon = `0.2.1`.
- Tidligere: 118 målrettede tester fra a12 til a16.2 bestått under alpha. **Disse erstatter ikke full `test.bat` med endelig versjon.**
- For reparasjon av første v0.2.1-ZIP: Pakk `v0.2.1.1.zip` over installert v0.2.1, og kjør **`fix-v0.2.1.bat`** én gang. Denne engangsrettingen oppdaterer fem historiske alpha-versjonsvakter, kontrollerer releasehistorikk og kjører `test.bat`. De opprinnelige funksjonstestene beholdes. **Framtidige releaser skal leveres komplett uten slike skript**, se `docs/RELEASE-VERSION-TEST-RULE.md`. Kjør `test.bat`, kontroller `docs/test-results/v0.2.1.md` og test GUI med reelle Work-data (`1525_004`): begge faglige navigasjonsknapper, metadata/kildekolonner, sjekkliste, faglige funn og rapporteksport.
- Opprett GitHub release/tag `v0.2.1` først fra godkjent, committet release-kode. Ingen Git-handlinger utføres av deltaen.

## Videre arbeid

Se `docs/TODO-ROADMAP.md`. Prioriterte neste trinn: **depotprofil/Test Depot**, én profilbasert sjekkliste, enkel lineær arbeidsflyt ved siden av avansert modus, og profilbasert godkjenningsbrev med eksplisitt beslutning. Konkrete XML-forekomster fra tekniske funn og bredere METS-støtte står fortsatt åpne.
