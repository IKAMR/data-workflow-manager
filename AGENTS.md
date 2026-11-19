# Repo-arbeidsregler: Data Workflow Manager (DWM)

## MÅ leses først ved Noark 5-arbeid

1. Les `docs/NOARK-SOURCE-LIBRARY.md` før du tolker eller endrer noe om
   Noark 5 (v3.1, v4.0, v5.0), metadata, krav, XML, XSD, XPath og tester.
2. **IKAMRs autoritative interne Noark 5-referansesamling er
   `IKAMR/digital-archive-workflow/docs/kilder/noark/noark5/`.** Bruk alltid
   dette repoets konkrete dokumenter og XSD-filer først. Registrer versjon,
   filsti og kildecommit ved hver analyse. Ikke forveksle intern kildefasit
   med det offisielle normative opphavet (Riksarkivet/Arkivverket/Nasjonalarkivet).
3. Originale historiske XPath-kilder for KDRS Query Standard/U1/U2 ligger i
   `IKAMR/KDRS_Query/doc/xml-queries_noark5_2026-05-26*.txt`.
   DWM-kopier ligger i `docs/reference/kdrs-query/`. KDRS Query er et
   historisk testgrunnlag, ikke en offisiell Noark-standard.
4. Eksterne offisielle kilder kan brukes til kvalitetskontroll. **Hvis de
   avviker fra vår samling, åpne en dokumentert QA-sak med repositoriets eier før
   noen kildefiler, normative antakelser eller regler endres.** Etter
   godkjent beslutning oppdateres kilderepoet først, deretter DWM.
5. Hold Noark 5 v3.1, 4.0 og 5.0 adskilt; ingen stilletiende ekvivalens.
   Skill mellom XSD-validering, verdilisteavstemming, KDRS-regresjon og
   depotfaglig vurdering. Katalogtreff betyr ikke normativ dekning.
6. Rapporter eksplisitt det som ikke er kontrollert. Ikke kall 15 registrerte
   XSD-filer eller 60 XPath-tester «komplett normativ kravdekning».
7. Respekter Source/Work-grensene, og skriv aldri om depotets originaldata.
   Brukeren håndterer Git commit og push; lever deltaer uten å committe.

## ⛔ ABSOLUTTE REGLER FOR DELTA-ZIP (SKAL ALLTID FØLGES)

**EN DELTA SKAL VÆRE FERDIG TIL Å PAKKES UT DIREKTE I REPOROTEN.**

1. **IKKE LEGG `README_A<n>.md`, `README.A<n>.md`, `README_A<n>.txt`,
   tilsvarende engangs-README eller annen forklaring inne i delta-ZIP.**
   Dette gjelder uansett versjon og skrivemåte.
2. Delta-ZIP skal ha korrekte relative stier og inneholde **kun nødvendige
   nye eller endrede filer som skal beholdes i repoet**. Ikke pakk inn en
   ekstra toppmappe, dokumentasjonsstøy, genererte filer, `__pycache__`, lokale
   testresultater, tilfeldige audit-artefakter eller midlertidige verktøy.
3. **Lever ferdige fullstendige erstatningsfiler.** Standardprosedyren er å
   pakke ut ZIP med overskriving. **Ikke krev `apply_v...py`, patcher eller
   etterfølgende Python-kommandoer for å aktivere endringene.** Unntak kan
   bare gjøres når direkte filutskifting er teknisk uforsvarlig eller klart
   mer tungvint; forklar årsaken *før* leveransen.
4. Hvis unntaket i punkt 3 brukes, skal det oppgis nøyaktig hvilke engangs-
   skript, hjelpefiler og tilhørende tester som kan slettes etter vellykket
   kjøring. Slike filer skal **aldri** ukritisk følge med til neste commit.
5. Lever eventuelle installasjonsinstruksjoner, endringsliste, teststatus,
   forbehold og oppfølgingspunkter **som egen Markdown-fil i samtalen utenfor
   delta-ZIP**. Informasjonsfilen skal ikke bli en ekstra fil i repoet.
6. En oppdatering av `AGENTS.md` eller annen faktisk repo-regel kan ligge i
   deltaen **kun når den er en tilsiktet varig repoendring**; dette er ikke en
   README for hver delta.
7. Skill mellom **produksjonskode**, **varige regresjonstester** og **engangs-
   installasjonshjelp**. Behold nødvendige produksjonsfiler og reelle tester.
   Slett ikke kode som er i bruk uten å kontrollere import/avhengigheter.
8. Deltaer må bygge på avtalt commit/branch, ha riktig versjonsnummer, bevare
   kollegaers endringer og kontrolleres med fil-/syntakstester så langt mulig.
   Ved usikker lokal kode må behovet for brukerens filer avklares; ikke
   overskriv fremmed kode på antakelser.
9. **Ingen commit, push, merge eller release utføres av AI.** Brukeren utfører
   Git-operasjoner etter kontroll med `test.bat` og praktisk verifisering.

## Obligatorisk format for foreslått Git commit-tekst

- Foreslå alltid **én kort, konkret og innholdsrik beskrivende setning på norsk**.
- **Versjonsnummeret plasseres sist**, med format `vX.Y.Z-aN` for alpha eller
  `vX.Y.Z` for ferdig release. Ingen tekst eller skilletegn etter versjonsnummeret.
- **Ingen versjonsprefiks** som `vX.Y.Z-aN:` og ingen `feat:`, `fix:` eller annen
  kategoriprefiks, med mindre brukeren uttrykkelig ber om en annen form.
- Beskriv faktiske tekniske/funksjonelle endringer. Unngå tomme innledninger som
  "Denne versjonen inneholder" eller annet fyllstoff.
- Før en commit-tekst foreslås skal AI kontrollere at den følger denne regelen.
  Brukeren utfører fortsatt selve commit og push.

Eksempel:

`Utvidet Noark-kravregister med kildebasert kravkartlegging, KDRS Standard/U1/U2-kontroll, XSD-validering og filtrerbar QA-gjennomgang v0.2.1-a8`
