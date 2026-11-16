# DWM v0.2.2-a1 – depotprofil og dokumentidentitet

## Implementert

**Depotprofil** er depotorganisasjonens avsenderidentitet i egne dokumenter.
Den er atskilt fra DWM-brukerprofilen (hvem vurderte/signerte), arbeidsprofilen
(Kontroll/Depot/Egendefinert), Noark 5-kontrollprofilen og DIAS/METS-metadata.
Depotprofilen skal aldri brukes som kilde for arkivskaper, arkiveier,
Noark-versjon eller teknisk kontrollresultat.

- Innebygd **Test Depot** med fiktivt navn, adresse, e-post under `.invalid`
  og tydelig DEMO-merking. Den kan velges, men ikke endres eller slettes.
- Operatøren kan opprette en egen depotprofil fra Test Depot uten at de
  fiktive kontaktopplysningene kopieres. Flere egne profiler kan lagres,
  aktiveres, redigeres og slettes.
- Hver profil har depot-/profilnavn, organisasjonsnummer, avdeling,
  avsender, adresse, poststed, telefon, e-post, nettsted, signaturnavn,
  stilling, referanseprefiks og bunntekst. Ingen slike opplysninger er påkrevd
  bortsett fra profilnavn og organisasjonsnavn.
- Valgfri PNG/JPEG-logo (høyst 2 MiB / 4096 × 4096 piksler) blir kopiert
  til et separat innholdskontrollert lokalt asset med SHA-256. Logo kan
  fjernes uten å endre originalbildet. Når ingen logo er valgt, vises
  generisk TD-/depotikon.
- Uavhengig valg av **Small, Medium, Full** for **Sjekkliste**,
  **Kvalitetssikringsrapport**, **Depotrapport** og **Godkjenningsbrev**.
- Skrivebeskyttet header-forhåndsvisning med demoindikator, og en versjonert
  `document_header_context()` for framtidig dokumentgenerering. Konteksten
  inneholder depotidentitet, valgt dokumenttype, headerstørrelse,
  profilavtrykk og logoreferanse. HTML-forhåndsvisningen HTML-escaper
  brukerens opplysninger.

## Bruk i GUI

Åpne **Startside → Rapportering → Depotprofil / dokumentoppsett…**.
En aktiv jobb er **ikke** nødvendig. Velg den innebygde demoprofilen eller
opprett **Ny / lag kopi…**, fyll inn avsender og kontaktopplysninger,
velg eventuelt logo og headerstørrelser og kontroller forhåndsvisningen.
Klikk **Lagre og bruk depotprofil**. Før lagring påvirkes ikke aktiv profil;
ved lukking av ulagrede data spør programmet før disse forkastes.

## Lagrings- og kildeprinsipp

Profilregisteret ligger i DWMs eksisterende **per-bruker datakatalog**, via
`app.user_profile.user_data_dir()`:

- Windows med LOCALAPPDATA: `%LOCALAPPDATA%\IKAMR\Noark5WorkflowManager\depot-profiles.json`
- Logokopier: samme mappe under `depot-profile-assets/`

Profilen legges **ikke** i repository, Source, Work, mottatt `info.xml`,
`dias-mets.xml` eller sjekklistens vurderingshistorikk. Ved uleselig/ukjent
profilfil gis en eksplisitt feil, ikke en stille nullstilling. Lagrede JSON-data
skrives atomisk. Innebygd Test Depot finnes uten profilfil.

**Avgrensning i a1:** Forhåndsvisning og felles datamodell er implementert.
Allerede eksisterende HTML-rapporter, sjekkliste-eksporter og
Godkjenningsbrev **blir ikke automatisk omformatert av denne profilen**.
Integrasjon i dokumentgeneratorene skjer i a2 (sjekkliste) og a5
(godkjenningsbrev), sammen med eksplisitt frys/snapshot av profilidentitet
på genereringstidspunktet. Gamle rapporter skal aldri endres fordi en
lokal depotprofil senere oppdateres.

## Test og regresjonskontroll

**v0.2.2-a1.1 – retting av testfilene etter alpha-leveringen**

1. Pakk `v0.2.2-a1.1.zip` **direkte over** installert `v0.2.2-a1`.
   ZIP-en inneholder de fem historiske testfilene med semantisk
   versjonskontroll (`assert_release_at_least`) og en korrigert versjonstest.
   Alle øvrige funksjonelle testassert-er og testoppsett er bevart.
2. Kjør **`test.bat` direkte**. Ingen `start-...bat`, oppgraderingsskript,
   patch eller manuell tilpasning er nødvendig. Det eldre
   `start-v0.2.2-a1-test.bat` skal ikke brukes.
3. Bekreft at full test er grønn og åpne **Rapportering → Depotprofil /
   dokumentoppsett…** uten aktiv jobb.
4. Bekreft at Test Depot er tydelig merket demo og skrivebeskyttet.
5. Opprett en egen profil, legg inn adresse, avsender og signatur, sett
   Small/Medium/Full ulikt for dokumenttypene, legg til logo, lagre og
   kontroller at profilen består etter omstart.
6. Kontroller at egne profilopplysninger ikke blandes med demoprofil,
   brukeridentitet eller tidligere Work/Noark-resultater.

**Version beholder `0.2.2-a1`**. `.1` er bare reparasjonspakkens nummer.
Ingen endring i produksjonskode, arkivuttrekk eller Work-innhold.
Ingen Git-commit eller -push gjøres automatisk.

## Videre arbeid

- **a2:** Én kanonisk sjekkliste/utgave med profilbasert utskrift og Work-evidens.
- **a3:** Bedre historiske og gjeldende METS-verdier, direkte kildeinnsyn.
- **a4:** Lineær Enkel-modus gjennom kontroll, vurdering og rapport.
- **a5:** Godkjenningsbrev fra samme frosne vurderings- og profilgrunnlag,
  kun etter eksplisitt depotvedtak.
- **a6:** Praktisk kvalitetssikring med faktiske Noark 5-uttrekk.
