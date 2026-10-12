# Arkade 5 v2.13.1 – teknisk analyse av SIP og AIP

**Analysegrunnlag:** `Arkade5_v2.13.1_Noark5_SIP_AIP.zip`, mottatt 12.10.2026. To Arkade-resultater med én TAR-pakke, én ytre METS-XML og ett skjermbilde per kjøring. Analyse utført uten å kjøre Arkade 5 på nytt.

> **Testforutsetning:** Metadata for `1566_019 Gerica SIARD (1999-2024)` er bevisst presentert som Noark 5, typeversjon 5.0, både for system og uttrekkssystem. Resultatet må ikke tolkes som dokumentasjon for at Gerica-opprinnelsen faktisk er et Noark 5-system, eller som en full produksjonsgodkjenning.

## 1. Hovedfunn

- Arkade 5 har laget **to separate pakkeversjoner** med ulike UUID-er: én `SIP` og én `AIP`. Hver har et ytre METS-dokument ved siden av TAR-filen, og et eget `dias-mets.xml` inni TAR.
- **Alle 15 opprinnelige filer i `content/` er byte-identiske** mellom SIP og AIP. Dette er kontrollert med SHA-256 for hver fil.
- SIP inneholder **24 filer**, AIP **26 filer**. AIP får tilleggene `descriptive_metadata/ead.xml` og `descriptive_metadata/eac-cpf.xml`; de er små grunnstrukturer, ikke utfylte arkivbeskrivelser.
- Indre `dias-mets.xml` registrerer henholdsvis **23 og 25 filobjekter**. For alle disse stemmer både oppgitt SHA-256 og `SIZE` med faktisk TAR-innhold. `dias-mets.xml` selv er ikke ført opp i sin egen filfortegnelse.
- PREMIS finnes både som `log.xml` og `administrative_metadata/dias-premis.xml`. I denne testen er de to filene identiske innad i hver pakke og inneholder ett PREMIS-objekt for TAR-filen. Ingen hendelsesliste (`event`) eller agenthistorikk er påvist i PREMIS-innholdet.
- XML-dokumentene kunne parses. **Full XSD-validering, funksjonell Noark 5-validering og kontroll av Arkade-testutfall i GUI er ikke utført i denne analysen.**

## 2. Testpakker og identiteter

| Egenskap | SIP | AIP |
|---|---|---|
| UUID / OBJID | `c27784bc-3c3d-4933-b1b3-8dfd55c388be` | `8bb4a426-8413-456d-93bc-313ea166c96d` |
| TAR-fil | `c27784bc-3c3d-4933-b1b3-8dfd55c388be.tar` | `8bb4a426-8413-456d-93bc-313ea166c96d.tar` |
| Ytre METS-fil | `c27784bc-3c3d-4933-b1b3-8dfd55c388be.xml` | `8bb4a426-8413-456d-93bc-313ea166c96d.xml` |
| Antall ordinære TAR-filer | `24` | `26` |
| METS-filreferanser | `23` | `25` |
| SHA-256 for TAR | `a3ac427e4abe301c29ba5430bbf10f7e759f21525bc4da52e3a62c283fc017d2` | `ad600d73ac9e17eba5b01aff849411032c37e63a04433afe732eca19bc96aada` |

Begge TAR-filene har størrelse **471 040 byte**, men forskjellig SHA-256 på grunn av forskjellig innhold og pakkeidentitet. Identisk TAR-størrelse innebærer ikke identisk TAR-innhold.

## 3. Pakkestruktur

Ytre leveranse fra Arkade-resultatmappen:
```text
arkade-resultater_<UUID>/
  <UUID>.tar
  <UUID>.xml       # ytre METS / submission description
```

Inne i TAR (SIP):
```text
<UUID>/
  dias-mets.xml
  dias-mets.xsd
  log.xml
  administrative_metadata/
    addml.xsd
    arkivuttrekk.xml
    dias-premis.xml
    dias-premis.xsd
    dokumenter-filformatinfo.csv
    dokumenter-filformatinfo-statistikk.csv
  descriptive_metadata/      # tom mappe i SIP
  content/
    addml.xsd
    arkivstruktur.xml, arkivstruktur.xsd
    arkivuttrekk.xml
    business-specific-metadata.xsd
    endringslogg.xml, endringslogg.xsd
    loependeJournal.xml, loependeJournal.xsd
    metadatakatalog.xsd
    offentligJournal.xml, offentligJournal.xsd
    noark5-test-001.xq, noark5-test-002.xq
    dokumenter/474031257635.pdf
```

AIP inneholder i tillegg: `descriptive_metadata/ead.xml` (243 byte) og `descriptive_metadata/eac-cpf.xml` (239 byte). Tomme TAR-mapper, ZIP-skjermbilder og `Thumbs.db` telles ikke som ordinære TAR-filer.

## 4. Ytre METS / info.xml

I resultatene heter ytre XML **`<UUID>.xml`**, ikke `info.xml`, men innholdet er METS i navnerommet `http://www.loc.gov/METS/` og bruker `submissionDescription.xsd` i `xsi:schemaLocation`. Det er dermed den *ytre* submission-description-strukturen som omtales i arbeidsflyten som `info.xml`.

- SIP: `TYPE="SIP"`, `OBJID` lik SIP-UUID. AIP: `TYPE="AIP"`, `OBJID` lik AIP-UUID.
- `LABEL` er identisk i begge: `1566_019 Gerica SIARD (1999-2024)`. `DELIVERYSPECIFICATION` er en egen `altRecordID` med samme *registrerte verdi* i testen. Disse to feltene har selvstendige roller; lik tekst her gjør dem ikke til samme metadatafelt.
- `SUBMISSIONAGREEMENT`: `IKAMR 26/400-2; 2026-06-26` er en lagret kildeverdi, ikke en streng som skal hardkodes i DWM.
- `DELIVERYTYPE`: `6-17 Pleie-og-omsorg`; `PACKAGENUMBER`: `1.0`; `STARTDATE`: `1999-12-31`; `ENDDATE`: `2024-11-08`.
- Begge ytre dokumenter har **14 agent-elementer** fra de samme registrerte rollene/organisasjonene/personene/programvarene. Begge bruker `notescontent:` som siste note til å beskrive de inkluderte kontakt-/programvarefeltene.
- Ytre `fileSec` registrerer to filobjekter: TAR-filen og indre `dias-mets.xml` med `file:`-referanser. Sjekksum og størrelse for TAR og indre METS er kontrollert mot faktiske byte; alle samsvarer.
- Ytre `structMap` har tom `div`. Det er ikke i seg selv dokumentasjon for at selve arkivinnholdet er komplett eller kvalitetssikret.

## 5. Indre dias-mets.xml

**Viktig navneromsskille:** Indre dokument har default-navnerom `http://arkivverket.no/standarder/METS`; ytre METS bruker `http://www.loc.gov/METS/`. De har like lokalnavn, men er **ikke samme XML-navnerom**. Dette må håndteres eksplisitt ved import/validering i DWM.

Indre `metsHdr` inneholder agentene, `altRecordID`-verdiene og `metsDocumentID=dias-mets.xml`. `fileSec` deler filene i to grupper:

| Gruppe (`USE`) | SIP | AIP | Innhold |
|---|---:|---:|---|
| `FILES` | 8 | 10 | Arkade-generert administrativt materiale, XML-skjemaer, rapport-CSV, samt EAD/EAC-CPF i AIP |
| `ArchiveExtraction` | 15 | 15 | Opprinnelig uttrekksinnhold under `content/` |

Alle 23/25 `file`-elementer har `ID`, `SIZE`, `CHECKSUM`, `CHECKSUMTYPE="SHA-256"` og `FLocat` med filsti. Ingen refererte filer mangler, og ingen feil i kontrollert `SIZE` eller `CHECKSUM` ble funnet. `structMap` er en tom `div`, uten `fptr`; filene er dermed **ført i filfortegnelsen, men ikke knyttet til en detaljert logisk struktur** her.

Mellom SIP og AIP endres blant annet `TYPE`, `OBJID`, opprettelsestidspunkter, de to nye EAD/EAC-referansene og påfølgende fil-ID-numre. Metadata som `LABEL`, agentroller, arkivperiode og overføringsavtale forblir uendret i denne testen.

## 6. PREMIS og log.xml

Følgende to filer finnes i **hver** TAR: `log.xml` og `administrative_metadata/dias-premis.xml`. Deres byteinnhold er identisk *innenfor samme pakke*, men forskjellig mellom SIP og AIP fordi objektidentifikatoren byttes.

Observerte PREMIS-felt:

- Rot: `{http://arkivverket.no/standarder/PREMIS}premis`, `version="2.0"` (Arkivverkets PREMIS-navnerom i dette materialet).
- Én `object` av typen `premis:file`, `objectIdentifierType=NO/RA`, identifikator lik pakkens UUID.
- `preservationLevelValue=full`, `compositionLevel=0`, `formatName=tar`.
- Ingen `event`, ingen egen PREMIS-`agent` og ingen dokumentert transformasjons-/valideringshistorikk i disse to XML-filene.

Dette betyr at **PREMIS finnes, men ikke dokumenterer en full prosesslogg i dette konkrete resultatet**. Navnet `log.xml` kan være misvisende hvis man forventer detaljerte hendelser. Det er en observasjon fra filinnholdet, ikke en konklusjon om alle Arkade 5-kjøringer.

## 7. ADDML, dokumentformat og Noark 5-innhold

`administrative_metadata/arkivuttrekk.xml` er en byte-identisk kopi av `content/arkivuttrekk.xml` (26 057 byte). ADDML har rot i `http://www.arkivverket.no/standarder/addml`, med `name="Noark 5-arkivuttrekk"`. Eksempelet inneholder dessuten feltet `systemType` med teksten `Sakarkiv (Noark-5)` og `systemName` med teksten `Documaster - DOTS`. Slike kildeverdier må ikke forveksles med testens manuelt angitte METS-systemfelt.

Dokumentfilformatrapportene er identiske i SIP og AIP:

| Felt | Rapportert verdi |
|---|---|
| Dokument | `474031257635.pdf` |
| PRONOM Format-ID | `fmt/354` |
| Format | `Acrobat PDF/A - Portable Document Format` |
| Versjon | `1b` |
| MIME-type | `application/pdf` |
| Størrelse | 46 329 byte |
| RAF-220301 | `Gyldig` |
| Antall | `1` |

Dette viser hva Arkade 5 **rapporterte** om filformatet. Det er ikke det samme som en uavhengig fornyet PDF/A-validering i denne analysen. Ingen av de leverte filene tyder på at selve dokumentet ble endret mellom SIP og AIP.

## 8. SIP–AIP-differanse og proveniens

- **Uendrede:** alle 15 `content/`-filer, begge rapport-CSV-er, ADDML-kopien og relevante XSD-skjemaer.
- **Endrede:** `dias-mets.xml`; `log.xml`; `administrative_metadata/dias-premis.xml`; ytre METS-XML; TAR-fil og UUID-identitet.
- **Tilført i AIP:** to korte beskrivende XML-filer (`ead.xml` og `eac-cpf.xml`).
- SIP og AIP ble pakket på ulike tidspunkter, noe som forklarer endrede opprettelsestidspunkter. Det foreligger **ikke** bevis i disse PREMIS-filene for en formelt dokumentert SIP→AIP-transformasjon med hendelseslenke mellom UUID-ene. Sammenhengen mellom pakkene dokumenteres her ved analysens felles testgrunnlag og byteidentisk `content/`.

## 9. Kvalitetskontroller utført i denne analysen

| Kontroll | Resultat |
|---|---|
| Lesbar ZIP og to TAR-arkiv | OK |
| Alle XML-dokumenter i TAR kan parses | OK |
| Ytre METS XML kan parses | OK |
| Indre METS-refererte filer eksisterer | 23/23 og 25/25 |
| SHA-256 i indre METS | 23/23 og 25/25 samsvar |
| SIZE i indre METS | 23/23 og 25/25 samsvar |
| Ytre METS, TAR og indre METS SHA-256/SIZE | Samsvar for begge pakker |
| Identitet for `content/`-filer | 15/15 byte-identiske |
| XSD-validering mot alle gjeldende skjemaer | Ikke utført |
| Komplett Noark 5-forretningsvalidering | Ikke utført |
| Eksterne Arkade-logger og GUI-testrapporter | Ikke mottatt som maskinlesbare rapporter |

## 10. Konsekvenser for DWM / depotarbeidsflyt

1. **To metadatarepresentasjoner:** DWM må skille ytre submission description (`info.xml`/`<UUID>.xml`, METS LOC-navnerom) fra indre `dias-mets.xml` (Arkivverkets METS-navnerom). Import og eksport må ikke blande dem.
2. **Pakkeidentitet:** `OBJID` og `TYPE` er pakke- og prosessspesifikke. SIP og AIP skal ikke dele UUID bare fordi de har samme uttrekksinnhold og `LABEL`.
3. **Proveniens:** Knytt SIP og AIP eksplisitt med separate prosess-/evidenshendelser og kildereferanser i DWM; ikke utled en formell PREMIS-prosesshistorikk av denne testens minimale PREMIS.
4. **Metadatafelt:** `LABEL`, `DELIVERYSPECIFICATION` og `SUBMISSIONAGREEMENT` behandles som adskilte felter; ingen IKAMR-spesifikke strengmønstre hardkodes som generiske krav.
5. **Filer:** Bruk filfortegnelse og SHA-256 i `dias-mets.xml` til verifiserbar integritetskontroll. Kontrollér også ytre METS mot faktisk TAR og indre METS.
6. **Kontaktnoter:** `notescontent:` beskriver kun faktisk inkluderte adresser/telefon/e-post eller programvarefelt; manglende person-agent er lovlig som representasjon av ingen oppgitt kontaktperson. Ikke gjenbruk gamle personverdier fra en tidligere import.
7. **Validering:** Bevar skille mellom Arkades rapporterte formatklassifisering (`fmt/354`, `Gyldig`) og en egen etterkontroll i DWM.
8. **Testprofil:** Metadata merket Noark 5 / 5.0 i dette forsøket er en kontrollert testforutsetning og skal ikke erstatte opprinnelig Gerica/SIARD-proveniens i ordinær depotregistrering.

## 11. Avgrensninger og videre tester

- Testen dokumenterer **resultatene i én SIP-kjøring og én AIP-kjøring**, ikke nødvendigvis enhver valgmulighet i Arkade 5 v2.13.1.
- En reell overføring kan ha andre METS-, PREMIS-, EAD-, EAC-CPF- og arkivstrukturelementer enn denne lille testpakken.
- For full verifikasjon bør original `info.xml` før Arkade-import og Arkades test-/operasjonslogger deles. Da kan verdioverføring, endringer og formelle testutfall kontrolleres direkte.
- Gjennomfør separat XSD-validering mot riktige METS-/PREMIS-/ADDML-/Noark-skjemaer, og kjør DWM-import av begge pakketyper med dokumentert forventet resultat.

---
**Status:** Teknisk fil-, struktur-, metadata- og SHA-256-analyse av mottatte artefakter fullført. Ikke sertifisering eller full schemasamsvarsgodkjenning.
