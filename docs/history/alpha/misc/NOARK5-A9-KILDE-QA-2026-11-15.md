# Noark 5 kravkilder: a9.1-observasjoner og a9.2-oppfølging

Dato: 2026-11-15. Status: **KILDE-QA ÅPEN**. Dette dokumentet er en
observasjonslogg, ikke en godkjenning av normativ kravdekning eller DWM-testdekning.
Ingen originalkilder, XSD-filer eller KDRS XPath-kilder er endret.

## Grunnlag

- Kilderepo: `IKAMR/digital-archive-workflow` commit
  `8d28e312e1e38af8cb93bfe05cecef11e09af34f`.
- DWM a9.1 lokalkjøring: 15 av 15 DOCX lesbare; v3.1: 963
  kravkandidater fra XLSX; v4.0: 974 og v5.0: 400 fra DOCX.
- a9.1-kilde-QA: 3 FEIL, 155 WARNING (138 tekstavvik, 9 krav bare
  i DOCX-avsnitt, 8 XLSX-krav uten selvstendig Word-tabelltreff).
- Kontroll mot a8 PDF-tekstuttrekk er **ikke** en fullstendig kontroll
  av PDF/DOCX-ordlyd.

## Tre konflikter som skal gjennom faglig kilde-QA

### Noark 5 v3.1: 6.3.25 (XLSX)

- `Noark5_v3.1_tabelloversikt_krav.xlsx`, `sheet2.xml:row211`:
  tekst om dynamiske skjema; samsvarer med **6.3.25** i
  `Noark5_v3.1_standarden.pdf`, PDF-side **147**.
- Samme XLSX, `sheet2.xml:row223`: tekst om import av deler av
  arkivstrukturen; i original-PDF-en er denne teksten nummerert
  **6.3.35**, PDF-side **149**, ikke 6.3.25.
- Foreløpig konklusjon: avvik i XLSX-nummereringen. Original
  PDF har her sterkere evidens. Korrigering av autoritativ XLSX
  krever beslutning hos kildeeier; DWM endrer ingen kildenummer.

### Noark 5 v3.1: 12.2.28 (XLSX)

- `sheet8.xml:row35`: tekst om oppgavedifferensiering er
  **12.2.28** i PDF-side **239**.
- `sheet8.xml:row58`: tekst om avgrensning av brukerens tilgang til
  saksområder/sakstyper er **12.2.38** i PDF-side **241**,
  ikke 12.2.28.
- Foreløpig konklusjon: avvik i XLSX-nummereringen. Ingen
  automatisk korrigering gjennomført.

### Noark 5 v5.0: 2.8.3 (DOCX)

- `Noark 5 v 5.docx`:
  `word/document.xml:tbl19:row4:cell1:p1` inneholder et krav om
  skjerming av registreringstittel (type O).
- `word/document.xml:tbl20:row2:cell1:p1` inneholder et krav om
  nøkkelord for klasser, mapper og registreringer (type V).
- Historisk a8 PDF-tekstuttrekk identifiserer også **2.8.3**
  to ganger i `Noark 5 v 5.pdf`, PDF-side **37**, linje 22 og 44.
- **Åpen:** Bekreft begge numrene visuelt i PDF-originalen. De
  kan representere en kildefeil eller et tabell-/listeproblem;
  a8-PDF-tekst alene avgjør ikke dette normativt.

## Teknisk rettelse i a9.2

- Innholdsfortegnelseoppføringer som `15\tOrdforklaringer\t266`
  og `7\tOrdforklaringer\t113` skal **ikke** brukes som
  `source_heading_context` for krav i v4.0/v5.0.
- Bare gjenkjennelige overskrifter kan gi kapittelkontekst;
  ellers tom streng, uten fabrikkert PDF-sidehenvisning.
- Hvert duplikatavvik i QA-CSV viser begge Word-/XLSX-ankre og
  tekstutdrag, slik at manuell kildekontroll kan gjøres konkret.
- Uavklart Word-nummerering (413 i hoveddokument v4.0,
  129 i hoveddokument v5.0) inkluderer også listeformater som
  ikke er desimalnumre. Dette er **ikke** et tall for tapte krav.
- `qa_counts` er antall kandidatstatuser. `qa_issue_counts` er
  antall separate QA-saker; de to tallene skal ikke blandes.

## Godkjenning og avgrensning

- Kildeavvik er ikke feil i et Noark 5-arkivuttrekk.
- DOCX er lesbar og filidentiteten er kontrollert; ordlydlikhet med
  original-PDF er fortsatt **ikke** faglig attestert.
- Alle registrerte krav er kandidater for normativ gjennomgang.
  Det gis ingen automatisk status «godkjent» eller «implementert i DWM».
- Full `test.bat` må kjøres hos repoets eier på Windows for commit.
