# DWM ↔ Arkade 5 Noark 5-mapping – v0.1.5-a2

Denne mappingen kobler DWM sine eksisterende Noark 5-analyser mot de **54 kildekodeverifiserte Arkade 5-testene** dokumentert i a1. Den avgjør ikke likhet ut fra testnummer alene.

## Regler

- `arkade:N5.xx` og historiske `kdrs:N5.xx` er separate navnerom.
- Samme nummer betyr ikke automatisk samme kontroll.
- `equivalent` brukes bare når den koblede kontrollsemantikken kan behandles som den samme.
- `partial` betyr reelt overlapp, men med forskjell i scope, kilde, unntak eller kontrollogikk.
- `complementary` betyr at DWM og Arkade bør beholdes side om side.
- `arkade_only` er hull DWM i første omgang lar Arkade dekke.
- Runtime-importmappingen `noark5_workflow/external_evidence/arkade5_mapping.json` erstattes ikke av denne kunnskapsmappingen.

## Oppsummering

- Arkade-tester kartlagt: **54**
- `equivalent`: **1**
- `partial`: **21**
- `complementary`: **19**
- `arkade_only`: **13**
- eksplisitte DWM/KDRS-only oppføringer: **14**

## Arkade → DWM

| Arkade | Relasjon | DWM-test(er) | Begrunnelse |
|---|---|---|---|
| N5.01 | `arkade_only` | – | DWM har ingen tilsvarende kontroll av at alle dokumenterte XML-enheter faktisk finnes. |
| N5.02 | `arkade_only` | – | DWM har ingen tilsvarende ADDML-basert sjekksumkontroll av XML/XSD. |
| N5.03 | `partial` | – | DWM har XML-skjema-validering, men dagens operasjon og Arkades ArchiveXmlUnit/fallback-semantikk er ikke identiske. |
| N5.04 | `partial` | `kdrs.c01` | Begge teller arkiv; Arkade analyserer også arkivnivå/hierarki. |
| N5.05 | `partial` | `kdrs.c02` | Begge teller arkivdeler; Arkade knytter resultat til overordnet arkiv. |
| N5.06 | `complementary` | `kdrs.c02`, `kdrs.c03` | DWM har arkivdelstatus og bredere lokal rapportering; Arkade gir egen statusanalyse. |
| N5.07 | `complementary` | `kdrs.c05`, `kdrs.c05_01_r3` | Samme hovedtema; DWM har både total og per-arkivdel analyse. |
| N5.08 | `partial` | `kdrs.c06` | Begge teller klasser, men Arkade organiserer etter arkivdel/klassifikasjonssystem og nivå. |
| N5.09 | `partial` | `kdrs.c07` | Arkade avgrenser eksplisitt til primært klassifikasjonssystem. |
| N5.10 | `partial` | `kdrs.c08` | Begge teller mapper; Arkade sammenholder også med dokumentert antall i ADDML. |
| N5.11 | `complementary` | `kdrs.c09`, `kdrs.c09_r4` | DWM dekker årstelling og har egen per-arkivdel variant. |
| N5.12 | `complementary` | `kdrs.c10`, `kdrs.c10_r5` | Samme strukturelle konflikt; DWM har også per-arkivdel variant. |
| N5.13 | `partial` | `kdrs.c11` | Begge rapporterer mapper per klasse; detalj-/kontekstformat er ikke dokumentert som identisk. |
| N5.14 | `partial` | `kdrs.c12` | Arkade har eksplisitt unntak for status «utgår» og rikere identitets-/linjekontekst. |
| N5.15 | `complementary` | `kdrs.c13`, `kdrs.c13_01` | DWM dekker status/type og per arkivdel; Arkade har egen statusmodell og avvikslogikk. |
| N5.16 | `partial` | `kdrs.c14` | Begge teller registreringer; Arkade sammenholder også med dokumentert antall i ADDML. |
| N5.17 | `partial` | `kdrs.c15`, `kdrs.c15_01` | Begge analyserer journalposttype; DWM har tillegg om hoveddokument og per arkivdel. |
| N5.18 | `complementary` | `kdrs.c16`, `kdrs.c16_r6`, `kdrs.c16_01_r7` | Arkade bruker opprettetDato; DWM har både opprettetDato- og journaldato-varianter. |
| N5.19 | `equivalent` | `kdrs.c17` | Samme dokumenterte strukturavvik: klasse med både underklasse og direkte registrering. |
| N5.20 | `complementary` | `kdrs.c18` | Samme direkte registreringer per klasse; DWM rapporterer også per arkivdel. |
| N5.21 | `partial` | `kdrs.c19` | Arkade har statusbasert «utgår»-unntak som må bevares ved sammenligning. |
| N5.22 | `partial` | `kdrs.c20` | Samme hovedtema, men Arkades kontrollregler for manglende/tom journalstatus er ikke identiske med rå DWM-telling. |
| N5.23 | `complementary` | `kdrs.c21` | Begge teller dokumentbeskrivelser; DWM bruker tellingen videre i egne visninger. |
| N5.24 | `partial` | `kdrs.c22` | Arkade har eksplisitte unntak for «utgår» og fysisk medium/fysisk arkiv. |
| N5.25 | `partial` | `kdrs.c23` | Begge grupperer dokumentstatus; detaljert kontrollsemantikk er ikke dokumentert som identisk. |
| N5.26 | `complementary` | `kdrs.c24` | Begge teller dokumentobjekter; DWM har i tillegg generisk variantformatrapportering. |
| N5.27 | `partial` | `kdrs.c25` | Arkade bruker første/siste registrerings opprettelsesdato; DWM legacy-testen har annen datakilde/semantikk. |
| N5.28 | `arkade_only` | – | Arkade sammenholder faktisk antall dokumentfiler med dokumentert antall; DWM mangler tilsvarende kontroll. |
| N5.29 | `partial` | – | DWM har dokumentformatdata i øvrig analyse/rapportering, men ingen dokumentert semantisk ekvivalent Arkade N5.29-test. |
| N5.30 | `arkade_only` | – | Arkade beregner og validerer sjekksum for faktiske dokumentfiler. |
| N5.32 | `arkade_only` | – | Arkade kontrollerer at refererte dokumentfiler faktisk finnes. |
| N5.33 | `arkade_only` | – | Arkade finner faktiske dokumentfiler som mangler referanse. |
| N5.34 | `arkade_only` | – | Arkade finner dokumentfiler referert fra mer enn ett dokumentobjekt. |
| N5.35 | `complementary` | `kdrs.f01` | Begge analyserer sakspart/part; DWM grupperer også per type. |
| N5.36 | `complementary` | `kdrs.f02` | Begge analyserer merknader; DWM grupperer per type/tilknytning. |
| N5.37 | `complementary` | `kdrs.f03` | Begge analyserer kryssreferanser; DWM grupperer per type/tilknytning. |
| N5.38 | `complementary` | `kdrs.f04` | Begge analyserer presedenser; DWM grupperer per type/tilknytning. |
| N5.39 | `complementary` | `kdrs.f05` | Begge analyserer korrespondanseparter; DWM beholder egne fordelinger. |
| N5.40 | `complementary` | `kdrs.f06` | Begge analyserer avskrivninger; DWM har generisk/metodeorientert rapportering. |
| N5.41 | `complementary` | `kdrs.f07` | Begge teller dokumentflyter; DWM har generisk lokal rapportering. |
| N5.42 | `partial` | `kdrs.f08` | Begge analyserer skjerming; Arkade sammenholder også forventet/dokumentert forekomst. |
| N5.43 | `complementary` | `kdrs.f09` | Begge analyserer graderinger; DWM beholder egen fordeling. |
| N5.44 | `partial` | `kdrs.f10` | Begge analyserer kassasjonsvedtak; Arkade sammenholder forventet/dokumentert forekomst. |
| N5.45 | `partial` | `kdrs.f11` | Begge analyserer utførte kassasjoner; Arkade sammenholder forventet/dokumentert forekomst. |
| N5.46 | `complementary` | `kdrs.f12` | Begge analyserer konverterte dokumenter; DWM beholder egen fordeling. |
| N5.47 | `arkade_only` | – | Arkade kontrollerer unikhet for systemID og rapporterer duplikater med XML-linjer. |
| N5.48 | `arkade_only` | – | Arkade validerer referanseArkivdel mot eksisterende arkivdeler. |
| N5.51 | `arkade_only` | – | Arkade validerer referanseSekundaerKlassifikasjon mot eksisterende klasser. |
| N5.59 | `partial` | `kdrs.i01`, `kdrs.h01`, `kdrs.h05` | Arkade sammenligner journalpostantall på tvers av arkivstruktur, løpende journal og offentlig journal; DWM har separate kilder/tellinger. |
| N5.60 | `partial` | `kdrs.i02`, `kdrs.h03`, `kdrs.h07` | Begge arbeider på tvers av journalfilene, men Arkades periodeskille og dato-logikk må bevares som egen semantikk. |
| N5.61 | `complementary` | `kdrs.j01` | Begge teller endringer; DWM har også dato-/årsfordeling. |
| N5.62 | `arkade_only` | – | Arkade validerer systemID-referanser fra endringslogg mot arkivstrukturen. |
| N5.63 | `arkade_only` | – | Arkade finner elementer som finnes, men har tomt/whitespace-innhold, med kontekst. |
| N5.64 | `arkade_only` | – | Arkade kontrollerer faktisk filstørrelse på refererte dokumentfiler; XML-metadata er ikke ekvivalent. |

## Historiske nummer som ikke må forveksles med Arkade

KDRS-katalogen har historiske testpunktnumre som ligger i samme visuelle nummerserie som Arkade. Disse er **ikke** Arkade-test-ID-er. Særlig gjelder dette KDRS N5.52–N5.58, N5.65, N5.101 og N5.102. Arkade v2.13.0 registrerer ikke N5.52–N5.58.

## Konsekvens for videre import

a2 er kun mapping-/kunnskapslaget. Arkade skal fortsatt være ekstern evidens. a3 kan bruke denne mappingen når importen normaliseres, men må beholde original Arkade-test-ID, status, meldinger, feil/advarsler, fil/XML-linje, systemID/arkivdel og referanse til rå rapport der dette finnes.
