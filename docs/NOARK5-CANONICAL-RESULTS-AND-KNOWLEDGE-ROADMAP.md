# Noark 5: felles resultatdata, rapporter, statistikk og erfaringsbase

**Status:** styrende utviklingsplan fra v0.1.14-a6 (ikke påstand om ferdig funksjonalitet).
**Domene:** DWM Noark 5-profil. Generell DWM-arkitektur kan utvikles senere.
**Kilder:** [Digital Archive Workflow / Noark](https://github.com/IKAMR/digital-archive-workflow/tree/main/docs/kilder/noark) for spesifikasjoner, DTD og XSD; [IKAMR/arkade5](https://github.com/IKAMR/arkade5) for sammenligning med Arkade 5. Disse er kildemateriale, ikke DWM-kontrollfunn.

## 1. Ett kanonisk datagrunnlag per uttrekk

Alle Noark 5-tester og eksterne importerte kontroller skal levere *strukturerte, kildesporbare observasjoner* til en samlet, versjonert resultatmodell for ett uttrekk. En rapport er en avledet visning, ikke primærlageret. Originale råresultater beholdes side om side; rapporter og egne faglige vurderinger må ikke endre testbevisene. Spesielt skal Arkade 5, KDRS Query og DWM ikke blandes til én anonym «test OK»-status.

Behov: (1) alle depotrapporter, også bevaring/godkjenning, (2) sammenligning av flere uttrekk, (3) aggregerbar statistikk etter totalsum, Noark-versjon, leverandør/systemtype, arkivskaper, arkiveier, arkivdel, år, resultatkategori m.m.

### 1.1 Foreslåtte entiteter (senere implementasjon)

- `extraction`: stabil ID, innleverings-ID, original kilde, mottak, versjonsbelegg, system/leverandør/versjon når dokumentert, arkiveier, arkivskapere, avleverer, arkivdeler og periode; ukjent er ikke lik tom streng og må ikke gjettes.
- `source`: filrelativ identitet, kontrollsum, filtype, prosess- og kildereferanse (arkivstruktur.xml, vedlegg, XSD m.m.).
- `run`: DWM-/verktøyversjon, profil, testkatalogversjon, tidspunkt, innstillinger, input-identitet, kjørestatus, arbeidsområde.
- `test_definition`: stabil test-ID, felt/metadata-ID, versjonert regelgrunnlag, kildeverktøy; separate regler og observasjoner.
- `observation`: test- og kjøre-ID, måleverdi, verdi-/tellingstype, alvorlighets- eller statusklasse, kildereferanser, evidens-ID; aggregeringer skal ikke forveksles med unike hendelser.
- `evidence`: XML-fil + XPath + linje + system-ID når faktisk kjent, dokumentreferanse, filhash, rå rapportreferanse; en samling av lokatorer, ikke en gjetning.
- `assessment`: faglig beslutning, merknad, tiltak, hvem/når, historikk og regel-/erfaringsreferanse. Oppdatering er ny hendelse, ikke overskriving av opprinnelig test.
- `dimension`: arkivskaper, eier, leverandør, systemtype, kommune, arkivdel, periode og klassifikasjoner med kilde/proveniens; benyttes ved aggregat og sammenligning.

### 1.2 Modellprinsipper

1. **Kanoniske observasjoner** lagres én gang per måling med stabile ID-er og entydig kilde- og kjøreproveniens. Ingen falsk tredobbelttelling ved historiske Noark-versjonssammenligninger.
2. **Rådata + normalisert resultat** bevares i Work, med gjensidig referanse og dokumentert transformasjon; Source er skrivebeskyttet.
3. **Kryssuttrekksstatistikk** hentes fra et *eksplisitt valgt* lokalt register/indeks over importerte ekstraktsammendrag. Ingen automatisk innlasting eller deling av depotinnhold.
4. **Rapporter** (kontrolloversikt, vedlegg, periodevurdering, depotvurdering, godkjenning/bevaring) bygges som avledede visninger fra samme kanoniske datagrunnlag, med eksplisitt rapportutgave og tidspunkt. En godkjenningsrapport må også vise manuelle beslutninger og uavklarte forhold.
5. **Statistikk** skal håndtere både teller, nevner, manglende data, ukjent system/arkivskaper/eier, overlappende perioder, flere arkivdeler og samme uttrekk kjørt flere ganger. Unngå dobbelttelling av kjøringer/versjoner.
6. **Sammenligning** må definere identitet og sammenligningsnøkler (arkivskaper, tidsperiode, kildeuttrekk, arkivdel, kontroll). Ulik test-/regelversjon skal ikke presenteres som reell kvalitetsutvikling uten normalisering.
7. **Personvern/sikkerhet:** kun aggregater/kataloginfo som standard for tverruttrekksindeks; ingen dokumentbinærer, personopplysninger eller kilde-XML kopieres til et felles register. Publisering er alltid eksplisitt og senere.
8. **Utvidbarhet:** versjonerte JSON Schema-kontrakter, migrering, kompatibilitet og regresjonstester; fremtidig SQLite kan fungere som lokal søkeindeks, ikke eneste kopi av evidens.

## 2. Kildetolkning og versjonsrekkefølge

- Uttrekkets Noark-versjon undersøkes fra lokale XSD-er (`xs:schema/@version`, faktisk struktur, endringshistorikk) og SHA-256; gamle opplysninger i `arkivuttrekk.xml` er sekundære og konflikter vises.
- Korrekt betegnelsen **Noark 5 versjon 5.0**; 5.5/5.5.0 brukes i enkelte sammenhenger om vedlikehold/omtale og skal ikke opprettes som separat standardversjon.
- **Gjeldende versjon først, deretter bakover:** 5.0 → 4.0 → 3.1 for v5.0-uttrekk; ingen «fremtidig» versjon i historisk sammenligning.
- Skill XSD-minimum/enum fra standardens normative tekst, DWM sitt forenklede verdiregister og semantisk fagvurdering.
- M300 `dokumentmedium` i v5.0-XSD: `minLength=1`, ingen XSD-enumeration. `Elektroniskarkiv` er derfor ikke et enumerasjonsbrudd i denne feltregelen; syntaktisk gyldighet er ikke ensbetydende med fullstendig depotfaglig godkjenning.
- Versjon 3.1 og 4.0 har M300-enumeration som bl.a. inneholder **«Fysisk medium»**, mens et eksisterende DWM-verdiregister oppgir **«Fysisk arkiv»**. Inntil dette er avklart må XSD-referanse og DWM-register tydelig holdes atskilt.

## 3. Lokal XSD-evidens og erfaringer

- a6: brukerinitiert, lokal `Work/noark5_evidence/xsd_variants.json`, filidentitet SHA-256, stabil UUIDv5 per innhold, observasjons-UUID, først/sist-observert, antall lagringer, kildesti, XSD-versjon, referanse og identifikasjonsstatus. Opplysninger er **ikke** et automatisk vitnemål om at en XSD er normativt identisk med originalen. Ingen nettverkskontakt eller sentral publisering.
- Videre: lokalt erfaringsregister med feltregel, kjent verdi-/skrivemåtevariant, dokumenterte versjonsforskjeller, manuell vurdering, godkjent lokal policy, forslag til kontrollmerknad og revisjonshistorikk.
- Et felles GitHub-register er en mulig fremtidig distribusjon. Først stabiliseres lokalt format, anonymisering, proveniens, datalisens/rettigheter, kvalitetskontroll og manuell publiseringsflyt.

## 4. Utviklingstrinn

| Trinn | Innhold | Status |
| --- | --- | --- |
| v0.1.14-a3/a4 | XML-kildetreff og metadatareferanser | Implementert, Windows-test hos bruker |
| v0.1.14-a5/fix1 | XSD-versjon, hash, konflikter og vedlikeholdsmerknad | Implementert, Windows-test hos bruker |
| **v0.1.14-a6** | XSD-feltregler nå → historisk bakover; lokal XSD-evidens i Work; arkitekturplan | Implementeres i dette deltaet |
| **v0.1.14-a7** | Første lokal M300-erfaringssak, eksplisitte Work-vurderingshendelser, valgfri lokal gjenbruksmerknad | Implementert som avgrenset første steg; bredere regler planlagt |
| a8 | Kontrollørens vurderingsarbeidsflate, stikkprøver, kobling til XML og dokumenter | Planlagt |
| a9 | Oversikt, filtrering, sammenslått kontrollnavigasjon, forklaringer og kompakt GUI | Planlagt |
| Senere | Kanonisk datasett, rapportadaptere, kryssuttrekksindeks, statistikk, delt erfaringsregister | Planlagt, utvikles trinnvis |

**Praktisk rekkefølge:** Før større endringer i rapporter og statistikk skal vi etablere en versjonert kontrakt for kanoniske observasjoner og kartlegge eksisterende DWM/Arkade/KDRS-felter mot den. Ingen destruktiv migrering av eldre Work-data uten særskilt plan.

## 5. Implementert i a7: lokal erfaringsvurdering

Se [NOARK5-LOCAL-EXPERIENCE.md](NOARK5-LOCAL-EXPERIENCE.md). Lokale vurderinger er append-only hendelser i jobbens Work og skal senere være input til en separat `assessment`-entitet. Samme testresultat endres ikke, og dette er ennå ikke den kanoniske resultatsamlingen.

## 6. Distribuert lokal erfaringsbase og framtidig samordning

DWM benyttes først av flere brukere på enkeltstående Windows-klienter ved samme depot.
Erfaringer må kunne samordnes uten å kreve serverdrift, permanent nettverkstilkobling
eller å kopiere konkrete arkivuttrekk til GitHub.

**Logiske nivåer (uavhengig av fysisk plassering):**

1. **Felles offentlig kunnskapsbase (GitHub, senere):** generelle, kvalitetssikrede
   Noark-/XSD-erfaringer, regelreferanser og publiserbare anonymiserte tilfeller.
2. **Depot:** depotets godkjente policy, felles erfaringssamling og versjonsregler.
   En egen depot-kilde, eventuelt et privat GitHub-repo, kan velges senere; dette
   skal ikke låses til et underområde i det offentlige repoet.
3. **Bruker:** personlige utkast, preferanser og faglige forslag, identifisert med
   stabil bruker-ID og uavhengig av hvilken PC som brukes.
4. **Klient:** teknisk cache, lokale innstillinger, frakoblet arbeidskø og
   synkroniseringsstatus; PC-identitet skal ikke erstatte brukeridentitet.
5. **Depotserver (valgfritt senere):** samme datakontrakter og policy som på
   klientene; serveren kan bli depotets autoritative lagrings- og synkroniseringspunkt.
6. **Flerdepot-tjeneste (eventuelt KDRS senere):** felles kunnskapsgrunnlag og
   depotisolerte områder, med eksplisitt eierskap, rettigheter og delingsvalg.

**Samordningsmodell:**

- Delbar erfaring har stabil ID, skjema-/regelversjon, opphav, forfatter/aktør,
  tidsstempel og revisjon. Lokal overstyring er et eget objekt og endrer aldri
  den felles posten. Faglige beslutninger om et uttrekk ligger i jobbens Work.
- For nå: lokal lagring og **eksplisitt eksport/import** som et senere trinn,
  med kontroll av duplikater, versjoner og konflikter; ikke filsynkronisering
  ved å kopiere hele `%LOCALAPPDATA%` mellom brukere.
- Ved sammenslåing skal samtidige endringer beholde begge versjoner eller
  gi en eksplisitt konflikt; ikke 'siste fil vinner'. Beslutninger er
  hendelser som ikke overskrives. Lokale policy-override prioriteres for lokal
  *anbefaling*, men kan aldri endre normative standardkrav eller test-evidens.
- Klientsynkronisering, depot-GitHub, depotserver og KDRS er **ikke implementert**.
  Første milepæl er stabil lokal datakontrakt, eksport/import og identiteter;
  sentral topologi bestemmes senere.

**GUI-regel:** Noark-metadata-ID (f.eks. `M300`) vises som en kort separat
kolonne i standardverdikontroller. Test-ID (f.eks. `kdrs.c02`) beholdes som
uavhengig identifikator. Begge er nødvendige for kildesporbarhet.
