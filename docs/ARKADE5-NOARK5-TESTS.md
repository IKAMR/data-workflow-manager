# Arkade 5 – Noark 5-tester i v2.13.0

Dette dokumentet beskriver **hva Arkade 5 faktisk tester** for Noark 5, basert på kildekoden i `IKAMR/arkade5`. Dokumentasjonen er laget som et kildekodeverifisert referansegrunnlag for Data Workflow Manager (DWM) og andre prosjekter som skal tolke eller importere Arkade-resultater.

## Kilde og versjonsfeste

- Arkade-versjon: **2.13.0**
- Kilderepository: `IKAMR/arkade5`
- Verifisert commit: `40a32ee0ae84ddf44d1f3c35f1860567ca262733`
- Commit-en er merge av `release/v2.13.0` med meldingen `Finish release`.
- Autoritativ testregistrering: `Noark5TestFactory.cs`.
- Struktur-/innholdsinndeling: `Noark5TestProvider.cs`.
- Norske visningsnavn: `ArkadeTestDisplayNames.nb-NO.resx`.

Katalogen er også tilgjengelig maskinlesbart i `config/noark5/external/arkade5_test_catalog.json`. Testnummer fra KDRS Query eller DWM skal ikke automatisk tolkes som Arkade-testnummer eller semantisk ekvivalens.

## Testmodell

Arkade registrerer 54 Noark 5-tester i `Noark5TestFactory`. Fire tester behandles som strukturtester i `Noark5TestProvider`: N5.01, N5.02, N5.03 og N5.28. De øvrige kjøres som innholdstester.

| Type | Antall |
|---|---:|
| StructureControl | 3 |
| StructureAnalysis | 1 |
| ContentControl | 8 |
| ContentAnalysis | 42 |

Ikke registrert i factory innen N5.01–N5.64: `N5.31`, `N5.49`, `N5.50`, `N5.52–N5.58`.

## Komplett testoversikt

| ID | Navn | Type | Hovedkilder |
|---|---|---|---|
| N5.01 | Kontroll av eksistens for XML-filene | StructureControl | arkivuttrekk.xml/ADDML, uttrekkets dokumenterte XML-enheter |
| N5.02 | Validering av sjekksummer | StructureControl | arkivuttrekk.xml/ADDML, dokumenterte XML-filer, dokumenterte XSD-filer |
| N5.03 | Validering av XML i henhold til skjema | StructureControl | alle ArchiveXmlUnit-enheter, tilknyttede XSD-skjemaer |
| N5.04 | Antall arkiv | ContentAnalysis | arkivstruktur.xml |
| N5.05 | Antall arkivdeler | ContentAnalysis | arkivstruktur.xml |
| N5.06 | Status på arkivdeler | ContentAnalysis | arkivstruktur.xml |
| N5.07 | Antall klassifikasjonssystem | ContentAnalysis | arkivstruktur.xml |
| N5.08 | Antall klasser | ContentAnalysis | arkivstruktur.xml |
| N5.09 | Antall klasser i det primære klassifikasjonssystemet uten underklasser, mapper eller registreringer | ContentAnalysis | arkivstruktur.xml |
| N5.10 | Antall mapper | ContentAnalysis | arkivstruktur.xml, arkivuttrekk.xml/ADDML |
| N5.11 | Antall mapper for hvert år | ContentAnalysis | arkivstruktur.xml |
| N5.12 | Klasser med både underklasse(r) og mappe(r) | ContentAnalysis | arkivstruktur.xml |
| N5.13 | Antall mapper for hver klasse | ContentAnalysis | arkivstruktur.xml |
| N5.14 | Antall mapper uten registreringer eller undermapper | ContentAnalysis | arkivstruktur.xml |
| N5.15 | Antall av ulike saksmappestatuser | ContentAnalysis | arkivstruktur.xml |
| N5.16 | Antall registreringer | ContentAnalysis | arkivstruktur.xml, arkivuttrekk.xml/ADDML |
| N5.17 | Antall av ulike journalposttyper | ContentAnalysis | arkivstruktur.xml |
| N5.18 | Antall registreringer for hvert år | ContentAnalysis | arkivstruktur.xml |
| N5.19 | Klasser med både underklasse(r) og registrering(er) | ContentAnalysis | arkivstruktur.xml |
| N5.20 | Antall registreringer for hver klasse (ikke medregnet registreringer under mappe) | ContentAnalysis | arkivstruktur.xml |
| N5.21 | Antall registreringer uten dokumentbeskrivelse | ContentAnalysis | arkivstruktur.xml |
| N5.22 | Antall av ulike journalstatuser | ContentAnalysis | arkivstruktur.xml |
| N5.23 | Antall dokumentbeskrivelser | ContentAnalysis | arkivstruktur.xml |
| N5.24 | Antall dokumentbeskrivelser uten dokumentobjekt | ContentAnalysis | arkivstruktur.xml |
| N5.25 | Antall av ulike dokumentstatuser | ContentAnalysis | arkivstruktur.xml |
| N5.26 | Antall dokumentobjekter | ContentAnalysis | arkivstruktur.xml |
| N5.27 | Opprettelsesdatoer for første og siste registrering | ContentAnalysis | arkivstruktur.xml |
| N5.28 | Validering av antall dokumentfiler | StructureAnalysis | arkivuttrekk.xml/ADDML, dokumentmappe |
| N5.29 | Antall av ulike dokumentformater | ContentAnalysis | arkivstruktur.xml |
| N5.30 | Dokumentfilers sjekksummer | ContentControl | arkivstruktur.xml, dokumentfiler |
| N5.32 | Refererte dokumenters eksistens | ContentControl | arkivstruktur.xml, dokumentfiler |
| N5.33 | Dokumentfiler som mangler referanse | ContentAnalysis | arkivstruktur.xml, dokumentfiler |
| N5.34 | Dokumentfiler med referanse fra mer enn ett dokumentobjekt | ContentAnalysis | arkivstruktur.xml |
| N5.35 | Antall saksparter | ContentAnalysis | arkivstruktur.xml |
| N5.36 | Antall merknader | ContentAnalysis | arkivstruktur.xml |
| N5.37 | Antall kryssreferanser | ContentAnalysis | arkivstruktur.xml |
| N5.38 | Antall presedenser | ContentAnalysis | arkivstruktur.xml |
| N5.39 | Antall korrespondanseparter | ContentAnalysis | arkivstruktur.xml |
| N5.40 | Antall avskrivninger | ContentAnalysis | arkivstruktur.xml |
| N5.41 | Antall dokumentflyter | ContentAnalysis | arkivstruktur.xml |
| N5.42 | Antall skjerminger | ContentAnalysis | arkivstruktur.xml, arkivuttrekk.xml/ADDML |
| N5.43 | Antall graderinger | ContentAnalysis | arkivstruktur.xml |
| N5.44 | Antall kassasjonsvedtak | ContentAnalysis | arkivstruktur.xml, arkivuttrekk.xml/ADDML |
| N5.45 | Antall utførte kassasjoner | ContentAnalysis | arkivstruktur.xml, arkivuttrekk.xml/ADDML |
| N5.46 | Antall konverterte dokumenter | ContentAnalysis | arkivstruktur.xml |
| N5.47 | Systemidentifikasjoner | ContentControl | arkivstruktur.xml |
| N5.48 | Arkivdelreferanser | ContentControl | arkivstruktur.xml |
| N5.51 | Klassereferanser | ContentControl | arkivstruktur.xml |
| N5.59 | Antall journalposter | ContentControl | arkivstruktur.xml, offentligJournal.xml, loependeJournal.xml |
| N5.60 | Start- og sluttdatoer | ContentAnalysis | arkivstruktur.xml, offentligJournal.xml, loependeJournal.xml |
| N5.61 | Antall loggførte endringer | ContentAnalysis | endringslogg.xml |
| N5.62 | Endringslogg-referanser til arkivstrukturen | ContentControl | arkivstruktur.xml, endringslogg.xml |
| N5.63 | Elementer som mangler innhold | ContentControl | arkivstruktur.xml |
| N5.64 | Antall tomme dokumentfiler | ContentAnalysis | arkivstruktur.xml, dokumentfiler |

## Detaljert kontrollbeskrivelse

### N5.01 – Kontroll av eksistens for XML-filene

**Type:** `StructureControl`  
**Kilder:** `arkivuttrekk.xml/ADDML`, `uttrekkets dokumenterte XML-enheter`  
**Scope:** `whole_extraction`  
**Implementasjon:** `src/Arkivverket.Arkade.Core/Testing/Noark5/Structure/N5_01_ValidateStructureFileExists.cs`

Går gjennom XML-enheter som uttrekket dokumenterer og kontrollerer at hver dokumentert XML-fil og tilhørende hovedfil faktisk finnes i uttrekkets innhold.

Særregler / viktige detaljer:
- Manglende dokumentert XML-fil gir Error.

### N5.02 – Validering av sjekksummer

**Type:** `StructureControl`  
**Kilder:** `arkivuttrekk.xml/ADDML`, `dokumenterte XML-filer`, `dokumenterte XSD-filer`  
**Scope:** `whole_extraction`  
**Implementasjon:** `src/Arkivverket.Arkade.Core/Testing/Noark5/Structure/N5_02_ValidateAddmlDataobjectsChecksums.cs`

Leser fil- og schema-properties fra ADDML, krever checksum-property og checksum-algoritme, beregner sjekksum for faktisk fil og sammenligner med dokumentert verdi.

Relevante felt/elementer: `file/name`, `file/checksum/value`, `file/checksum/algorithm`.

Særregler / viktige detaljer:
- Implementasjonen aksepterer SHA-256/SHA256.
- Manglende checksum, algoritme, fil eller mismatch gir Error.
- Samme schemafil valideres ikke flere ganger.

### N5.03 – Validering av XML i henhold til skjema

**Type:** `StructureControl`  
**Kilder:** `alle ArchiveXmlUnit-enheter`, `tilknyttede XSD-skjemaer`  
**Scope:** `whole_extraction`  
**Implementasjon:** `src/Arkivverket.Arkade.Core/Testing/Noark5/Structure/N5_03_ValidateXmlWithSchema.cs`

Validerer hver XML-enhet i uttrekket mot skjemaene Arkade har knyttet til enheten. Valideringsfeil rapporteres med fil og XML-linjer.

Særregler / viktige detaljer:
- Bruk av Arkades innebygde fallback-skjema rapporteres som Error i dagens kode.
- arkivuttrekk.xml rapporteres med dette navnet selv om intern ADDML-filrepresentasjon brukes.

### N5.04 – Antall arkiv

**Type:** `ContentAnalysis`  
**Kilder:** `arkivstruktur.xml`  
**Scope:** `whole_extraction`  
**Implementasjon:** `src/Arkivverket.Arkade.Core/Testing/Noark5/N5_04_NumberOfArchives.cs`

Teller arkiv-elementer i arkivstrukturen og rapporterer samlet antall, med analyse av arkivnivå/hierarki.

Relevante felt/elementer: `arkiv`.

### N5.05 – Antall arkivdeler

**Type:** `ContentAnalysis`  
**Kilder:** `arkivstruktur.xml`  
**Scope:** `whole_extraction`, `archive`  
**Implementasjon:** `src/Arkivverket.Arkade.Core/Testing/Noark5/N5_05_NumberOfArchiveParts.cs`

Teller arkivdel-elementer og knytter resultatet til overordnet arkiv der dette er tilgjengelig.

Relevante felt/elementer: `arkiv/systemID`, `arkivdel`.

### N5.06 – Status på arkivdeler

**Type:** `ContentAnalysis`  
**Kilder:** `arkivstruktur.xml`  
**Scope:** `whole_extraction`, `archive_part`  
**Implementasjon:** `src/Arkivverket.Arkade.Core/Testing/Noark5/N5_06_StatusOfArchiveParts.cs`

Grupperer og teller arkivdeler etter arkivdelstatus, med arkivdelens systemID og tittel som resultatkontekst.

Relevante felt/elementer: `arkivdel/systemID`, `arkivdel/tittel`, `arkivdel/arkivdelstatus`.

### N5.07 – Antall klassifikasjonssystem

**Type:** `ContentAnalysis`  
**Kilder:** `arkivstruktur.xml`  
**Scope:** `whole_extraction`, `archive_part`  
**Implementasjon:** `src/Arkivverket.Arkade.Core/Testing/Noark5/N5_07_NumberOfClassificationSystems.cs`

Teller klassifikasjonssystemer under arkivdel og rapporterer per arkivdel når relevant.

Relevante felt/elementer: `arkivdel/systemID`, `arkivdel/tittel`, `klassifikasjonssystem`.

### N5.08 – Antall klasser

**Type:** `ContentAnalysis`  
**Kilder:** `arkivstruktur.xml`  
**Scope:** `whole_extraction`, `archive_part`, `classification_system`  
**Implementasjon:** `src/Arkivverket.Arkade.Core/Testing/Noark5/N5_08_NumberOfClasses.cs`

Teller klasser og organiserer resultatet etter arkivdel og klassifikasjonssystem. Leser strukturelle nivåer mens klassehierarkiet prosesseres.

Relevante felt/elementer: `arkivdel/systemID`, `arkivdel/tittel`, `klassifikasjonssystem/systemID`, `klasse`.

### N5.09 – Antall klasser i det primære klassifikasjonssystemet uten underklasser, mapper eller registreringer

**Type:** `ContentAnalysis`  
**Kilder:** `arkivstruktur.xml`  
**Scope:** `whole_extraction`, `archive_part`, `classification_system`  
**Implementasjon:** `src/Arkivverket.Arkade.Core/Testing/Noark5/N5_09_NumberOfClassesInMainClassificationSystemWithoutSubClassesFoldersOrRegistrations.cs`

Finner tomme klasser i klassifikasjonssystem som Arkade identifiserer som primært gjennom faktisk bruk. En klasse er tellbar når den ikke har underklasse, mappe eller registrering.

Relevante felt/elementer: `klassifikasjonssystem/systemID`, `klasse`, `mappe`, `registrering`.

Særregler / viktige detaljer:
- Avgrensningen til primært klassifikasjonssystem er vesentlig ved sammenligning med andre tellere.

### N5.10 – Antall mapper

**Type:** `ContentAnalysis`  
**Kilder:** `arkivstruktur.xml`, `arkivuttrekk.xml/ADDML`  
**Scope:** `whole_extraction`, `archive_part`  
**Implementasjon:** `src/Arkivverket.Arkade.Core/Testing/Noark5/N5_10_NumberOfFolders.cs`

Teller mapper, inkludert mappetyper, og sammenholder faktisk antall med dokumentert mappeantall når dette finnes i uttrekksdokumentasjonen.

Relevante felt/elementer: `mappe`, `mappe/@type`, `arkivdel/systemID`, `arkivdel/tittel`.

Særregler / viktige detaljer:
- Analyse kan produsere Error når dokumentert og faktisk antall ikke samsvarer.

### N5.11 – Antall mapper for hvert år

**Type:** `ContentAnalysis`  
**Kilder:** `arkivstruktur.xml`  
**Scope:** `whole_extraction`, `archive_part`  
**Implementasjon:** `src/Arkivverket.Arkade.Core/Testing/Noark5/N5_11_NumberOfFoldersPerYear.cs`

Grupperer mapper etter år fra opprettetDato. Ugyldige XML-datoer håndteres eksplisitt av datoparsingen.

Relevante felt/elementer: `mappe/opprettetDato`, `arkivdel/systemID`, `arkivdel/tittel`.

### N5.12 – Klasser med både underklasse(r) og mappe(r)

**Type:** `ContentAnalysis`  
**Kilder:** `arkivstruktur.xml`  
**Scope:** `whole_extraction`, `archive_part`  
**Implementasjon:** `src/Arkivverket.Arkade.Core/Testing/Noark5/N5_12_ControlNoSuperclassesHasFolders.cs`

Finner klasser som samtidig inneholder underklasse og mappe, og rapporterer identiteten til berørte klasser.

Relevante felt/elementer: `klasse/systemID`, `klasse/klasse`, `klasse/mappe`, `arkivdel/systemID`, `arkivdel/tittel`.

### N5.13 – Antall mapper for hver klasse

**Type:** `ContentAnalysis`  
**Kilder:** `arkivstruktur.xml`  
**Scope:** `whole_extraction`, `archive_part`, `class`  
**Implementasjon:** `src/Arkivverket.Arkade.Core/Testing/Noark5/N5_13_NumberOfFoldersPerClass.cs`

Teller mapper som ligger direkte under hver klasse og rapporterer per klasse med klasseidentitet.

Relevante felt/elementer: `klasse/systemID`, `klasse/mappe`, `arkivdel/systemID`, `arkivdel/tittel`.

### N5.14 – Antall mapper uten registreringer eller undermapper

**Type:** `ContentAnalysis`  
**Kilder:** `arkivstruktur.xml`  
**Scope:** `whole_extraction`, `archive_part`  
**Implementasjon:** `src/Arkivverket.Arkade.Core/Testing/Noark5/N5_14_NumberOfFoldersWithoutRegistrationsOrSubfolders.cs`

Finner mapper som verken inneholder registreringer eller undermapper. Mappe med status «utgår» tas ikke med. Berørte mapper rapporteres med identitet og XML-linje.

Relevante felt/elementer: `mappe/systemID`, `mappe/mappeID`, `mappe/offentligTittel`, `mappe/saksstatus`.

Særregler / viktige detaljer:
- Status «utgår» er et eksplisitt unntak.

### N5.15 – Antall av ulike saksmappestatuser

**Type:** `ContentAnalysis`  
**Kilder:** `arkivstruktur.xml`  
**Scope:** `whole_extraction`, `archive_part`  
**Implementasjon:** `src/Arkivverket.Arkade.Core/Testing/Noark5/N5_15_NumberOfEachCaseFolderStatus.cs`

Grupperer saksmappestatus og teller forekomster per arkivdel. Kontrollen bruker Arkades mappestatusmodell og kan rapportere avvik for manglende/ugyldig status.

Relevante felt/elementer: `mappe/saksstatus`, `arkivdel/systemID`, `arkivdel/tittel`.

### N5.16 – Antall registreringer

**Type:** `ContentAnalysis`  
**Kilder:** `arkivstruktur.xml`, `arkivuttrekk.xml/ADDML`  
**Scope:** `whole_extraction`, `archive_part`  
**Implementasjon:** `src/Arkivverket.Arkade.Core/Testing/Noark5/N5_16_NumberOfRegistrations.cs`

Teller registreringer og registreringstyper og sammenholder faktisk antall med dokumentert registreringsantall når tilgjengelig.

Relevante felt/elementer: `registrering`, `registrering/@type`, `arkivdel/systemID`, `arkivdel/tittel`.

Særregler / viktige detaljer:
- Analyse kan produsere Error ved avvik mellom dokumentert og faktisk antall.

### N5.17 – Antall av ulike journalposttyper

**Type:** `ContentAnalysis`  
**Kilder:** `arkivstruktur.xml`  
**Scope:** `whole_extraction`, `archive_part`  
**Implementasjon:** `src/Arkivverket.Arkade.Core/Testing/Noark5/N5_17_NumberOfEachJournalPostType.cs`

Identifiserer journalpost-registreringer og grupperer dem etter journalposttype. Tom journalposttype rapporteres som Error med XML-lokasjon.

Relevante felt/elementer: `registrering/@type`, `registrering/systemID`, `registrering/journalposttype`.

### N5.18 – Antall registreringer for hvert år

**Type:** `ContentAnalysis`  
**Kilder:** `arkivstruktur.xml`  
**Scope:** `whole_extraction`, `archive_part`  
**Implementasjon:** `src/Arkivverket.Arkade.Core/Testing/Noark5/N5_18_NumberOfRegistrationsPerYear.cs`

Grupperer registreringer etter år fra opprettetDato og bruker eksplisitt XML-datoparsing.

Relevante felt/elementer: `registrering/opprettetDato`, `arkivdel/systemID`, `arkivdel/tittel`.

### N5.19 – Klasser med både underklasse(r) og registrering(er)

**Type:** `ContentAnalysis`  
**Kilder:** `arkivstruktur.xml`  
**Scope:** `whole_extraction`, `archive_part`  
**Implementasjon:** `src/Arkivverket.Arkade.Core/Testing/Noark5/N5_19_ControlNoSuperclassesHasRegistrations.cs`

Finner klasser som samtidig inneholder underklasse og registrering direkte under klassen.

Relevante felt/elementer: `klasse/systemID`, `klasse/klasse`, `klasse/registrering`.

### N5.20 – Antall registreringer for hver klasse (ikke medregnet registreringer under mappe)

**Type:** `ContentAnalysis`  
**Kilder:** `arkivstruktur.xml`  
**Scope:** `whole_extraction`, `archive_part`, `class`  
**Implementasjon:** `src/Arkivverket.Arkade.Core/Testing/Noark5/N5_20_NumberOfRegistrationsPerClass.cs`

Teller registreringer som ligger direkte under klasse. Registreringer under mapper medregnes ikke.

Relevante felt/elementer: `klasse/systemID`, `klasse/registrering`, `arkivdel/systemID`, `arkivdel/tittel`.

### N5.21 – Antall registreringer uten dokumentbeskrivelse

**Type:** `ContentAnalysis`  
**Kilder:** `arkivstruktur.xml`  
**Scope:** `whole_extraction`, `archive_part`  
**Implementasjon:** `src/Arkivverket.Arkade.Core/Testing/Noark5/N5_21_NumberOfRegistrationsWithoutDocumentDescription.cs`

Finner registreringer uten dokumentbeskrivelse og rapporterer berørte registreringer. Registrering/mappe med status «utgår» filtreres gjennom Arkades statusmodell.

Relevante felt/elementer: `registrering/systemID`, `registrering/registreringsID`, `dokumentbeskrivelse`, `mappe/status`, `registrering/status`.

Særregler / viktige detaljer:
- «utgår»-unntaket er viktig ved sammenligning med en rå XPath-telling.

### N5.22 – Antall av ulike journalstatuser

**Type:** `ContentAnalysis`  
**Kilder:** `arkivstruktur.xml`  
**Scope:** `whole_extraction`, `archive_part`  
**Implementasjon:** `src/Arkivverket.Arkade.Core/Testing/Noark5/N5_22_NumberOfEachJournalStatus.cs`

Grupperer journalposter etter journalstatus og rapporterer manglende/tom status etter Arkades kontrollregler.

Relevante felt/elementer: `registrering/journalstatus`, `arkivdel/systemID`, `arkivdel/tittel`.

### N5.23 – Antall dokumentbeskrivelser

**Type:** `ContentAnalysis`  
**Kilder:** `arkivstruktur.xml`  
**Scope:** `whole_extraction`, `archive_part`  
**Implementasjon:** `src/Arkivverket.Arkade.Core/Testing/Noark5/N5_23_NumberOfDocumentDescriptions.cs`

Teller dokumentbeskrivelser totalt og per arkivdel.

Relevante felt/elementer: `dokumentbeskrivelse`, `arkivdel/systemID`, `arkivdel/tittel`.

### N5.24 – Antall dokumentbeskrivelser uten dokumentobjekt

**Type:** `ContentAnalysis`  
**Kilder:** `arkivstruktur.xml`  
**Scope:** `whole_extraction`, `archive_part`  
**Implementasjon:** `src/Arkivverket.Arkade.Core/Testing/Noark5/N5_24_NumberOfDocumentDescriptionsWithoutDocumentObject.cs`

Finner dokumentbeskrivelser uten dokumentobjekt, men anvender Arkades faglige unntak for «utgår» og fysiske dokumentmedier. Fysiske dokumentbeskrivelser uten objekt rapporteres separat.

Relevante felt/elementer: `dokumentbeskrivelse/systemID`, `dokumentbeskrivelse/dokumentnummer`, `dokumentbeskrivelse/dokumentmedium`, `dokumentobjekt`, `mappe/status`, `registrering/status`.

Særregler / viktige detaljer:
- Dokumentmedium «fysisk medium» og «fysisk arkiv» behandles separat og teller ikke som ordinært manglende dokumentobjekt.
- Mappe/registrering med status «utgår» filtreres ut.

### N5.25 – Antall av ulike dokumentstatuser

**Type:** `ContentAnalysis`  
**Kilder:** `arkivstruktur.xml`  
**Scope:** `whole_extraction`, `archive_part`  
**Implementasjon:** `src/Arkivverket.Arkade.Core/Testing/Noark5/N5_25_NumberOfEachDocumentStatus.cs`

Grupperer dokumentbeskrivelser etter dokumentstatus og rapporterer manglende/tomme verdier etter Arkades regler.

Relevante felt/elementer: `dokumentbeskrivelse/dokumentstatus`, `arkivdel/systemID`, `arkivdel/tittel`.

### N5.26 – Antall dokumentobjekter

**Type:** `ContentAnalysis`  
**Kilder:** `arkivstruktur.xml`  
**Scope:** `whole_extraction`, `archive_part`  
**Implementasjon:** `src/Arkivverket.Arkade.Core/Testing/Noark5/N5_26_NumberOfDocumentObjects.cs`

Teller dokumentobjekter totalt og per arkivdel.

Relevante felt/elementer: `dokumentobjekt`, `arkivdel/systemID`, `arkivdel/tittel`.

### N5.27 – Opprettelsesdatoer for første og siste registrering

**Type:** `ContentAnalysis`  
**Kilder:** `arkivstruktur.xml`  
**Scope:** `whole_extraction`, `archive_part`  
**Implementasjon:** `src/Arkivverket.Arkade.Core/Testing/Noark5/N5_27_FirstAndLastRegistrationCreationDates.cs`

Leser registrering/opprettetDato, validerer datoformat, teller ugyldige datoer og rapporterer første og siste gyldige opprettelsesdato per arkivdel.

Relevante felt/elementer: `registrering/opprettetDato`, `arkivdel/systemID`, `arkivdel/tittel`.

Særregler / viktige detaljer:
- Ugyldige datoer gir Error med XML-linjer.
- Datakilden er registrering/opprettetDato, ikke dokumentbeskrivelse/opprettetDato.

### N5.28 – Validering av antall dokumentfiler

**Type:** `StructureAnalysis`  
**Kilder:** `arkivuttrekk.xml/ADDML`, `dokumentmappe`  
**Scope:** `whole_extraction`  
**Implementasjon:** `src/Arkivverket.Arkade.Core/Testing/Noark5/Structure/N5_28_ValidateNumberOfDocumentfiles.cs`

Teller faktiske dokumentfiler, leser dokumentert antallDokumentfiler fra ADDML og sammenligner verdiene.

Relevante felt/elementer: `antallDokumentfiler`.

Særregler / viktige detaljer:
- Manglende dokumentmappe, null faktiske filer, manglende dokumentasjon eller mismatch kan gi Error.

### N5.29 – Antall av ulike dokumentformater

**Type:** `ContentAnalysis`  
**Kilder:** `arkivstruktur.xml`  
**Scope:** `whole_extraction`, `archive_part`, `document_format`  
**Implementasjon:** `src/Arkivverket.Arkade.Core/Testing/Noark5/N5_29_NumberOfEachDocumentFormat.cs`

Grupperer dokumentobjekter etter format og sammenligner deklarert format med filendelsen i referanseDokumentfil. Mismatch rapporteres som Error.

Relevante felt/elementer: `dokumentobjekt/format`, `dokumentobjekt/referanseDokumentfil`.

Særregler / viktige detaljer:
- Sammenligningen bruker filendelsen i referansen; dette er ikke full innholdsvalidering av filformat.

### N5.30 – Dokumentfilers sjekksummer

**Type:** `ContentControl`  
**Kilder:** `arkivstruktur.xml`, `dokumentfiler`  
**Scope:** `whole_extraction`, `archive_part`, `document_object`  
**Implementasjon:** `src/Arkivverket.Arkade.Core/Testing/Noark5/N5_30_DocumentFilesChecksumControl.cs`

For hvert dokumentobjekt leses filreferanse, sjekksum og sjekksumAlgoritme; Arkade beregner sjekksum for den faktiske dokumentfilen og sammenligner med deklarert verdi.

Relevante felt/elementer: `dokumentobjekt/referanseDokumentfil`, `dokumentobjekt/sjekksum`, `dokumentobjekt/sjekksumAlgoritme`, `dokumentbeskrivelse/systemID`.

### N5.32 – Refererte dokumenters eksistens

**Type:** `ContentControl`  
**Kilder:** `arkivstruktur.xml`, `dokumentfiler`  
**Scope:** `whole_extraction`, `archive_part`  
**Implementasjon:** `src/Arkivverket.Arkade.Core/Testing/Noark5/N5_32_ControlDocumentFilesExists.cs`

Kontrollerer at hver referanseDokumentfil peker på en dokumentfil som faktisk finnes i uttrekket.

Relevante felt/elementer: `referanseDokumentfil`, `arkivdel/systemID`, `arkivdel/tittel`.

### N5.33 – Dokumentfiler som mangler referanse

**Type:** `ContentAnalysis`  
**Kilder:** `arkivstruktur.xml`, `dokumentfiler`  
**Scope:** `whole_extraction`  
**Implementasjon:** `src/Arkivverket.Arkade.Core/Testing/Noark5/N5_33_DocumentfilesReferenceControl.cs`

Sammenligner faktiske dokumentfiler med referanseDokumentfil-verdiene i dokumentobjekter og identifiserer filer som ikke er referert.

Relevante felt/elementer: `dokumentobjekt/referanseDokumentfil`.

### N5.34 – Dokumentfiler med referanse fra mer enn ett dokumentobjekt

**Type:** `ContentAnalysis`  
**Kilder:** `arkivstruktur.xml`  
**Scope:** `whole_extraction`, `archive_part`  
**Implementasjon:** `src/Arkivverket.Arkade.Core/Testing/Noark5/N5_34_NumberOfMultiReferencedDocumentFiles.cs`

Grupperer referanseDokumentfil og identifiserer dokumentfiler som er referert fra flere dokumentobjekter.

Relevante felt/elementer: `dokumentobjekt/referanseDokumentfil`, `arkivdel/systemID`, `arkivdel/tittel`.

### N5.35 – Antall saksparter

**Type:** `ContentAnalysis`  
**Kilder:** `arkivstruktur.xml`  
**Scope:** `whole_extraction`, `archive_part`  
**Implementasjon:** `src/Arkivverket.Arkade.Core/Testing/Noark5/N5_35_NumberOfCaseParts.cs`

Teller saksparter/parter. Implementasjonen håndterer både eldre sakspart-element og Noark 5.0 part-element og fordeler tilknytning etter relevant forelder.

Relevante felt/elementer: `sakspart`, `part`, `arkivdel/systemID`, `arkivdel/tittel`.

Særregler / viktige detaljer:
- Arkade har separat visningsnavn «Antall parter» for v5.0.

### N5.36 – Antall merknader

**Type:** `ContentAnalysis`  
**Kilder:** `arkivstruktur.xml`  
**Scope:** `whole_extraction`, `archive_part`  
**Implementasjon:** `src/Arkivverket.Arkade.Core/Testing/Noark5/N5_36_NumberOfComments.cs`

Teller merknader og grupperer dem etter hvilken Noark-entitet de er knyttet til.

Relevante felt/elementer: `merknad`, `arkivdel/systemID`, `arkivdel/tittel`.

### N5.37 – Antall kryssreferanser

**Type:** `ContentAnalysis`  
**Kilder:** `arkivstruktur.xml`  
**Scope:** `whole_extraction`, `archive_part`  
**Implementasjon:** `src/Arkivverket.Arkade.Core/Testing/Noark5/N5_37_NumberOfCrossReferences.cs`

Teller kryssreferanser etter referansetype, blant annet referanseTilKlasse, referanseTilMappe og referanseTilRegistrering.

Relevante felt/elementer: `referanseTilKlasse`, `referanseTilMappe`, `referanseTilRegistrering`.

### N5.38 – Antall presedenser

**Type:** `ContentAnalysis`  
**Kilder:** `arkivstruktur.xml`  
**Scope:** `whole_extraction`, `archive_part`  
**Implementasjon:** `src/Arkivverket.Arkade.Core/Testing/Noark5/N5_38_NumberOfPrecedents.cs`

Teller presedens under mappe og journalpost-registrering ved hjelp av Arkades typeidentifikasjon.

Relevante felt/elementer: `mappe/presedens`, `registrering/presedens`, `registrering/@type`, `mappe/@type`.

### N5.39 – Antall korrespondanseparter

**Type:** `ContentAnalysis`  
**Kilder:** `arkivstruktur.xml`  
**Scope:** `whole_extraction`, `archive_part`  
**Implementasjon:** `src/Arkivverket.Arkade.Core/Testing/Noark5/N5_39_NumberOfCorrespondenceParts.cs`

Teller korrespondanseparter og grupperer etter type/tilknytning i strukturen.

Relevante felt/elementer: `korrespondansepart`, `arkivdel/systemID`, `arkivdel/tittel`.

### N5.40 – Antall avskrivninger

**Type:** `ContentAnalysis`  
**Kilder:** `arkivstruktur.xml`  
**Scope:** `whole_extraction`, `archive_part`  
**Implementasjon:** `src/Arkivverket.Arkade.Core/Testing/Noark5/N5_40_NumberOfDepreciations.cs`

Teller avskrivninger og grupperer etter avskrivningsmåte, inkludert referanser som inngår i avskrivningen.

Relevante felt/elementer: `avskrivning/avskrivningsmaate`.

### N5.41 – Antall dokumentflyter

**Type:** `ContentAnalysis`  
**Kilder:** `arkivstruktur.xml`  
**Scope:** `whole_extraction`, `archive_part`  
**Implementasjon:** `src/Arkivverket.Arkade.Core/Testing/Noark5/N5_41_NumberOfDocumentFlows.cs`

Teller dokumentflyt-elementer og deres tilknytning, inkludert journalpostidentifikasjon der relevant.

Relevante felt/elementer: `dokumentflyt`, `registrering/@type`, `arkivdel/systemID`, `arkivdel/tittel`.

### N5.42 – Antall skjerminger

**Type:** `ContentAnalysis`  
**Kilder:** `arkivstruktur.xml`, `arkivuttrekk.xml/ADDML`  
**Scope:** `whole_extraction`, `archive_part`  
**Implementasjon:** `src/Arkivverket.Arkade.Core/Testing/Noark5/N5_42_NumberOfRestrictions.cs`

Teller skjerming per elementtype og sammenholder faktisk forekomst med uttrekksdokumentasjonens inneholderSkjermetInformasjon.

Relevante felt/elementer: `skjerming`, `inneholderSkjermetInformasjon`, `arkivdel/systemID`, `arkivdel/tittel`.

Særregler / viktige detaljer:
- Dokumentasjon=true uten funn og dokumentasjon=false med funn behandles som avvik/Error.

### N5.43 – Antall graderinger

**Type:** `ContentAnalysis`  
**Kilder:** `arkivstruktur.xml`  
**Scope:** `whole_extraction`, `archive_part`  
**Implementasjon:** `src/Arkivverket.Arkade.Core/Testing/Noark5/N5_43_NumberOfClassifications.cs`

Teller gradering-elementer med versjonstilpasset håndtering av Noark-strukturen.

Relevante felt/elementer: `gradering`, `arkivdel/systemID`, `arkivdel/tittel`.

### N5.44 – Antall kassasjonsvedtak

**Type:** `ContentAnalysis`  
**Kilder:** `arkivstruktur.xml`, `arkivuttrekk.xml/ADDML`  
**Scope:** `whole_extraction`, `archive_part`  
**Implementasjon:** `src/Arkivverket.Arkade.Core/Testing/Noark5/N5_44_NumberOfDisposalResolutions.cs`

Teller kassasjon/kassasjonsvedtak per elementtype og sammenholder forekomst med inneholderDokumenterSomSkalKasseres i uttrekksdokumentasjonen.

Relevante felt/elementer: `kassasjon`, `inneholderDokumenterSomSkalKasseres`, `arkivdel/systemID`, `arkivdel/tittel`.

Særregler / viktige detaljer:
- Dokumentert forekomst og faktisk forekomst krysskontrolleres begge veier.

### N5.45 – Antall utførte kassasjoner

**Type:** `ContentAnalysis`  
**Kilder:** `arkivstruktur.xml`, `arkivuttrekk.xml/ADDML`  
**Scope:** `whole_extraction`, `archive_part`  
**Implementasjon:** `src/Arkivverket.Arkade.Core/Testing/Noark5/N5_45_NumberOfDisposalsExecuted.cs`

Teller utfoertKassasjon (i implementasjonen eksplisitt under arkivdel og dokumentbeskrivelse) og sammenholder med omfatterDokumenterSomErKassert.

Relevante felt/elementer: `utfoertKassasjon`, `omfatterDokumenterSomErKassert`, `arkivdel/systemID`, `arkivdel/tittel`.

### N5.46 – Antall konverterte dokumenter

**Type:** `ContentAnalysis`  
**Kilder:** `arkivstruktur.xml`  
**Scope:** `whole_extraction`, `archive_part`  
**Implementasjon:** `src/Arkivverket.Arkade.Core/Testing/Noark5/N5_46_NumberOfConversions.cs`

Teller konvertering under dokumentobjekt og rapporterer konverteringsforekomster per arkivdel.

Relevante felt/elementer: `dokumentobjekt/konvertering`, `arkivdel/systemID`, `arkivdel/tittel`.

### N5.47 – Systemidentifikasjoner

**Type:** `ContentControl`  
**Kilder:** `arkivstruktur.xml`  
**Scope:** `whole_extraction`  
**Implementasjon:** `src/Arkivverket.Arkade.Core/Testing/Noark5/N5_47_SystemIdUniqueControl.cs`

Samler systemID-verdier og kontrollerer global unikhet. Duplikater rapporteres med XML-linjenumre.

Relevante felt/elementer: `systemID`.

Særregler / viktige detaljer:
- Dette er en referanse-/integritetskontroll, ikke bare en telling.

### N5.48 – Arkivdelreferanser

**Type:** `ContentControl`  
**Kilder:** `arkivstruktur.xml`  
**Scope:** `whole_extraction`, `archive_part`  
**Implementasjon:** `src/Arkivverket.Arkade.Core/Testing/Noark5/N5_48_ArchivepartReferenceControl.cs`

Samler arkivdelers systemID og kontrollerer at referanseArkivdel peker på en eksisterende arkivdel.

Relevante felt/elementer: `arkivdel/systemID`, `referanseArkivdel`, `arkivdel/tittel`.

### N5.51 – Klassereferanser

**Type:** `ContentControl`  
**Kilder:** `arkivstruktur.xml`  
**Scope:** `whole_extraction`, `archive_part`  
**Implementasjon:** `src/Arkivverket.Arkade.Core/Testing/Noark5/N5_51_ClassReferenceControl.cs`

Kontrollerer at referanseSekundaerKlassifikasjon kan kobles til systemID-er i arkivstrukturen i henhold til Arkades klassereferansemodell.

Relevante felt/elementer: `systemID`, `referanseSekundaerKlassifikasjon`, `arkivdel/tittel`.

### N5.59 – Antall journalposter

**Type:** `ContentControl`  
**Kilder:** `arkivstruktur.xml`, `offentligJournal.xml`, `loependeJournal.xml`  
**Scope:** `whole_extraction`  
**Implementasjon:** `src/Arkivverket.Arkade.Core/Testing/Noark5/N5_59_NumberOfJournalPosts.cs`

Teller journalposter i arkivstrukturen og leser journalpostantall fra offentlig og løpende journal. Offentlig og løpende journal skal samsvare; ved skarpt periodeskille sammenlignes også arkivstrukturens antall.

Relevante felt/elementer: `registrering/@type`, `offentligJournal`, `loependeJournal`.

Særregler / viktige detaljer:
- Bruker Arkades PeriodSeparationIsSharp-regel.

### N5.60 – Start- og sluttdatoer

**Type:** `ContentAnalysis`  
**Kilder:** `arkivstruktur.xml`, `offentligJournal.xml`, `loependeJournal.xml`  
**Scope:** `whole_extraction`  
**Implementasjon:** `src/Arkivverket.Arkade.Core/Testing/Noark5/N5_60_ArchiveStartAndEndDateControl.cs`

Beregner start-/sluttdato for journalposter og sammenligner datoavgrensning mellom journalfilene og arkivstrukturen etter Arkades periodeskille-regler.

Relevante felt/elementer: `registrering/journaldato`.

Særregler / viktige detaljer:
- Arkivstrukturens datofelt er registrering/journaldato.
- Bruker PeriodSeparationIsSharp og XML-datovalidering.

### N5.61 – Antall loggførte endringer

**Type:** `ContentAnalysis`  
**Kilder:** `endringslogg.xml`  
**Scope:** `whole_extraction`  
**Implementasjon:** `src/Arkivverket.Arkade.Core/Testing/Noark5/N5_61_NumberOfChangesLogged.cs`

Leser endringslogg.xml og rapporterer antall loggførte endringer.

Relevante felt/elementer: `endringslogg`.

### N5.62 – Endringslogg-referanser til arkivstrukturen

**Type:** `ContentControl`  
**Kilder:** `arkivstruktur.xml`, `endringslogg.xml`  
**Scope:** `whole_extraction`  
**Implementasjon:** `src/Arkivverket.Arkade.Core/Testing/Noark5/N5_62_ChangeLogArchiveReferenceControl.cs`

Kontrollerer systemID-referanser fra endringslogg mot systemID-er som finnes i arkivstrukturen.

Relevante felt/elementer: `systemID`.

### N5.63 – Elementer som mangler innhold

**Type:** `ContentControl`  
**Kilder:** `arkivstruktur.xml`  
**Scope:** `whole_extraction`  
**Implementasjon:** `src/Arkivverket.Arkade.Core/Testing/Noark5/N5_63_ControlElementsHasContent.cs`

Kontrollerer elementer for manglende/tomt innhold og rapporterer funn med XML-kontekst; systemID brukes som identitetskontekst der tilgjengelig.

Relevante felt/elementer: `systemID`.

Særregler / viktige detaljer:
- Kontrollen er bredere enn en test av at elementet eksisterer; den ser etter elementer uten reelt innhold.

### N5.64 – Antall tomme dokumentfiler

**Type:** `ContentAnalysis`  
**Kilder:** `arkivstruktur.xml`, `dokumentfiler`  
**Scope:** `whole_extraction`, `archive_part`  
**Implementasjon:** `src/Arkivverket.Arkade.Core/Testing/Noark5/N5_64_NumberOfEmptyDocumentFiles.cs`

Følger dokumentreferanser fra arkivstrukturen til faktiske dokumentfiler og teller refererte filer med filstørrelse 0. Bruker mappe-/registreringsstatus i rapporteringshierarkiet.

Relevante felt/elementer: `referanseDokumentfil`, `dokumentbeskrivelse/systemID`, `dokumentbeskrivelse/dokumentnummer`, `registrering/registreringsID`.

Særregler / viktige detaljer:
- Urefererte filer håndteres av N5.33 og er ikke formålet med N5.64.

## Konsekvenser for import og sammenligning

- Arkade-resultater må importeres med test-ID, resultatstatus, original melding og lokasjon/fillinje der rapporten inneholder dette.
- Arkade-resultater skal beholdes som ekstern evidens; DWM skal ikke omskrive dem til egne testresultater og miste original betydning.
- Lik test-ID i en historisk KDRS/DWM-katalog er bare en mapping-kandidat. Semantisk ekvivalens må dokumenteres eksplisitt.
- Tester som bruker filesystem, ADDML eller flere XML-filer kan ikke reduseres til en enkel XPath uten å endre kontrollens betydning.

## Videre arbeid etter a1

Neste steg er en separat, maskinlesbar DWM↔Arkade-mapping som klassifiserer hver kobling som `equivalent`, `partial`, `complementary`, `arkade_only` eller `dwm_only`, og deretter fullfører Arkade-importen slik at alle relevante resultater kan inngå i samlet depotvalidering.
