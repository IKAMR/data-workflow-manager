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
