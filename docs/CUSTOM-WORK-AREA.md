# DWM custom_work – avgrenset arbeidsmateriale i Work

DWM bruker jobbens godkjente **Work** som rot for alt appstyrt arbeidsmateriale.
Dette er et tillegg til det mottatte arkivuttrekket, ikke en endring av Source.
En depotstruktur kan for eksempel ha `content/` for originalt SIP-innhold og
`repository_operations/dwm2/a03/` som jobbens Work. DWM må **ikke** kreve
akkurat disse mappenavnene på andre depot.

```text
<godkjent jobb-Work>/
  job.json
  noark5_evidence/
  noark5_reports/
  custom_work/
    xml_extracts/
      XML-<uuid>/
        extract.xml
        manifest.json
    document_samples/       (framtidig, ikke opprettet nå)
    format_investigations/   (framtidig, ikke opprettet nå)
    conversions/            (framtidig, ikke opprettet nå)
```

## Gjeldende funksjon: XML-eksport

Brukeren kan eksportere et valgt metadatafelt eller den komplette, undersøkte
kontekstseksjonen. Eksporten oppretter en unik mappe med selvstendig XML-fil
og manifest under `custom_work/xml_extracts/`. DWM endrer aldri originalen,
og eksporten foregår ikke hvis Work ikke kan verifiseres. En avkortet seksjon
kan ikke merkes som fullstendig eksport. Eksportfilens SHA-256 er identitet
for arbeidskopien, ikke for hele Source-filen. De serialiserte fragmentene er
selvstendige XML-elementer, ikke byte-for-byte kopier av kildens filområder.

## Senere dokumentarbeid

Arbeidskopier av valgte dokumenter, alternative formater og konverteringer skal
få egne arbeidsoppgave-ID-er og manifester med kildehenvisning og checksums.
Slikt materiale kan være sensitivt og forblir i Work inntil en eksplisitt
arkivfaglig beslutning er tatt. Dette er ikke implementert i a8.1.

## Pakking

Det normale er å supplere uttrekket med kontroll, vurderinger og arbeidskopier.
Endring eller ny pakking av TAR, utpakket TAR eller DIAS-pakke gjøres bare
som særskilt, brukerinitiert og dokumentert arbeidsflyt. Det er ikke en side-
effekt av XML-eksport eller annen ordinær resultatvisning.
