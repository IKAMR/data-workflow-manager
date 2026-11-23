# DWM v0.2.1-a16.1 – metadata, kildehenvisninger og ryddig METS-visning

**Delta over v0.2.1-a16**, uten ny distribusjonsversjon, metadata-migrering eller
endring i Source. a16.1 erstatter beskrivelsen av metadata-GUI-et i a16-dokumentet;
alle a16-sikkerhets- og Work-prinsipper gjelder fortsatt.

## Arbeidsflate og visninger

Eksakt sti: **Resultatvisninger → Faglig vurdering → Visning: Depotvurdering →
Sjekkliste / METS… → Metadata og kilder → Komplett DIAS/METS: sammenlign og rediger metadata…**.

**Vis** har nå fem adskilte valg:

1. **Metadata – 47 Arkade-felt** (standard): Kun de 47 feltkategoriene fra
   `0000-metadata-arkade.xlsx`, uten dobbeltvisning av XML-attributter.
2. **Depotopplysninger – 4 felt**: Egne DWM-katalogdata. Disse er **ikke**
   metadatafelter i METS eller fra Arkade-regnearket.
3. **Utvidede METS-opplysninger**: `OBJID`, `TYPE`, `PROFILE`, opprettelsesdato,
   andre/ekstra aktører, ukjente/gjentatte referanser og **én oversiktsrad per
   fil** i `fileSec` (ID, sti, størrelse, MIME-type og sjekksum). Opplysninger
   som allerede har plass blant de 47 feltene vises ikke på nytt her.
4. **Teknisk XML – alle forekomster**: Fullt kildeinventar med ordinal XML-sti,
   alle tekstverdier, attributter og strukturelementer. Dette er teknisk innsyn,
   ikke den ordinære redigeringslisten. Det kan søkes i hele inventaret.
5. **Bare ulike / endrede**: Avvikende gjeldende Work-verdier og relevante
   endringer fra den grupperte utvidede visningen, ikke alle duplikate rå XML-rader.

## To kildereferanser per Arkade-felt

47-feltlisten har kolonnene **Ytre info.xml** og **Indre DIAS METS**.
Begge er synlige for hvert felt, også når én kilde **ikke er importert**.

- Hver kolonne viser forventet plassering og kildestatus: **Påvist**,
  **Ikke påvist**, **Kilde ikke importert** eller **Ikke kartlagt**.
- Velg et felt for å se full, forventet plassering, **faktisk ordinal
  XML-forekomst**, kildefil, SHA-256 og den opprinnelige verdien for hver
  av de to kildene. Samme informasjon er tilgjengelig i tabellcellens tooltip.
- To kilder kan ha uavhengige og ulike verdier. Da markeres de to kildereferansene,
  og antallet kildeforskjeller oppgis. Det er **ikke** automatisk et avvik eller
  en teknisk testfeil. Gjeldende Work-verdi sammenlignes fortsatt med den
  konkret valgte historiske kilden.
- Kildene verifiseres byte-for-byte mot registrert SHA-256. En annen fil med
  samme navn er aldri tilstrekkelig. Kildevalg binder historisk verdi til
  nøyaktig valgt XML; den andre kildetypen presenteres med egen identitet.

Referanser til de 47 feltene bygger på Arkade 5s metadata-katalog og
`docs/integrations/dias/DIAS-METADATA-MAPPING.md`. `mets:agent/@ROLE/@OTHERROLE/@TYPE`
identifiserer organisasjon, person og programvare. Kontakt- og versjonsnotater
bruker **Arkade 5s `notescontent:`-konvensjon**, ikke en oppdiktet METS-datatype.
Faktiske stier har forekomstindekser (`[1]`, `[2]`, ...), slik at gjentatte
aktører kan spores uten sammenblanding. De menneskelesbare, forventede
`notescontent:`-referansene er feltplasseringer, ikke utgitte XPath-spørringer.

**Bevisst uavklart:** DWM-feltet `extraction_date` har ikke vedtatt kildefelt
på ytre `info.xml`. Arkade 5 kan legge `VERSDATE` på indre filgruppen
`ArchiveExtraction`, men vi påstår **ikke** automatisk at denne datoen er
faglig identisk med DWM-uttferdiget «Uttrekksdato». Dette vises som
**Ikke kartlagt** med forklaring. `PROJECTNAME` forventes normalt i indre
DIAS METS; ytre Arkade-eksport skriver vanligvis ikke dette feltet.

## Kildeintegritet, redigering og bakoverkompatibilitet

- **47 eksisterende Work-felt** redigeres på samme sted som før med begrunnelse,
  bruker og historikk. Denne visningen lager ikke en konkurrerende 47-feltmodell.
- Rå tekstfelt uten kanonisk mapping kan fortsatt registreres som
  kildebundne Work-arbeidsverdier; originalfilen endres aldri.
- Teknisk identitet (`OBJID`, profil, pakketype, skjema), filstier,
  `CHECKSUM`, `CHECKSUMTYPE`, `SIZE` og andre `fileSec`-opplysninger er
  skrivebeskyttet i det tekniske inventaret. De skal ikke kunne forveksles med
  en faktisk korrigert pakkestruktur. Eventuelle tidligere a16-arbeidshendelser
  bevares, men forveksles ikke med verifiserte, nye sjekksummer.
- `metadata/depot_metadata.json`, original `source_evidence`, eksisterende
  append-only hendelser, sjekkliste, N5.22/Arkade og a20-rapportmotor er ikke
  migrert eller endret av a16.1.
- a16-grensene på 32 MiB per XML-kilde / 180 000 XML-noder gjelder videre;
  overskridelser skal rapporteres, ikke behandles som komplett import.

## Windows-test i GUI

1. Pakk **`v0.2.1-a16.1.zip` over installert a16**. Kjør `test.bat`.
2. Åpne `1525_004` i metadataarbeidsflaten som angitt ovenfor.
3. Standard **Vis: Metadata – 47 Arkade-felt** skal nå bare vise 47 felt,
   med **to separate kildereferansekolonner**. Velg `Arkivskaper`,
   `Systemversjon`, `METS LABEL` og `Startdato`; se faktisk kildebanesti.
4. Hvis indre `dias-mets.xml` ennå ikke er importert, skal dens kolonne vise
   **Kilde ikke importert**, mens forventet plassering fremgår. Den må ikke
   vises som «Ikke påvist» i en kilde DWM ikke har lest.
5. Velg **Utvidede METS-opplysninger**: Kontroller få, tydelig grupperte
   metadata, herunder `OBJID` og filobjekter, uten `agent/@ROLE`, `@TYPE`,
   `notescontent` og hovedfeltenes navn i gjentatte rader.
6. Velg **Teknisk XML – alle forekomster**: 124 registrerte XML-forekomster
   i det benyttede `1525_004`-grunnlaget er fortsatt tilgjengelige.
7. Importer om mulig en bevart **indre** `dias-mets.xml`, og kontroller at
   begge kolonnene viser hver sin faktiske forekomst og SHA-256. Gi ulik
   `LABEL` i et testgrunnlag for å kontrollere tydelig kildedifferanse.
8. Gjør en testendring på et lite, ordinært Work-felt, med begrunnelse, og
   bekreft at bare gjeldende verdi blir uthevet. Tilbakestill etter testen.

Kjør full `test.bat` før commit. Ingen påstand om full Windows-GUI-verifikasjon
før manuell gjennomgang er godkjent.
