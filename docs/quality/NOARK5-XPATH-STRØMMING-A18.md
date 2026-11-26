# v0.2.7-a18 – F06 og riktig kjørelogg

## A190 / F06 / N5.40

Kjøringen på `1502_024` med a17 ga 59 OK og ett teknisk `UnsupportedStreamMetric` i F06.

A18 beregner disse XPath-uttrykkene ved lukking av `avskrivning`, med kun
minnebegrensede XML-stakkrammer:

- `count(//registrering[@type="journalpost"]/avskrivning[string-length(avskrivningsmaate)>0]/avskrivningsmaate)`
- `count(//registrering[@type="journalpost"]/avskrivning[string-length(referanseAvskrivesAvJournalpost)>0]/referanseAvskrivesAvJournalpost)`

Kontrollen av `string-length()` bruker utrimmet strenglengde, slik at mellomrom
ikke behandles som tomt. Det kreves direkte `registrering`-forelder med
`@type="journalpost"`, og direkte avskrivningsfelt. Støtte for ukjente XPath-uttrykk
blir **ikke** gjettet eller gitt OK-status.

F06-resultatet sammenlignes i tester med standard `lxml` XPath, inkludert tomt
felt, mellomrom, referanse og en registrering av annen type. C01/C02 og de
øvrige strømmende kontrollene endres ikke.

## Kjøredetaljer → Logg

Under aktiv kjøring skal Logg åpne nyeste arbeidsflytlogg, ikke den valgte
historiske deljobbloggen. Ved oppdatering av historikken flyttes utvalget til
nyeste rad bare når den tidligere valgte raden var forrige nyeste. Brukerens
bevisste valg av eldre rader beholdes når kjøringen ikke pågår.

## Verifikasjon

Kjør hele `test.bat` og behold testresultatet i `docs/test-results/` ved commit.
Praktisk 1502_024-verifikasjon: fortsett JOB-001 fra A190 (8/17), behold fullførte
A100–A180, kontroller 60/60 tester og resultatlikhet før etterarbeid.
