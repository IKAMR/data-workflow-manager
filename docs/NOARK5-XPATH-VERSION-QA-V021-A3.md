# DWM v0.2.1-a3 – Noark 5-versjoner og dokumentert XPath-dekning

## Formål

Fortsettelse av a1 (samlet KDRS XPath-visning) og a2 (kildesporing og
regresjonsgrunnlag). Versjonstilknytning skal kvalitetssikres for **Noark 5
v3.1, v4.0 og v5.0**, uten å anta at samme XPath eller den samme metadata-
beskrivelsen er normativt gyldig i alle tre versjoner.

**a3 innfører ikke nye normative krav, en ny XPath-motor, Saxon-kjøring eller
automatisk godkjenning av uttrekk.** Det er en gjennomgang av eksplisitte
kildekoblinger og dokumentert dekningsstatus. Eksisterende registrerte krav og
metadata beholdes; ingen katalogtest omskrives eller omklassifiseres automatisk.

## Datagrunnlag og bevisnivå

| Kilde i eksisterende DWM | Hva a3 kontrollerer | Hva a3 ikke kan attestere |
| --- | --- | --- |
| `config/noark5/tests/xpath_catalog_2026_05_26.json` | Deklarert versjonsliste og `version_basis` per test | At en deklarert versjonsliste er riktig etter spesifikasjonen |
| KDRS Query Standard/U1/U2 | Eksisterende sporbarhet fra a1/a2 | At Saxon/XQuery og lxml/Python er semantisk like |
| `config/noark5/standards/sources.json` | Kilderegistrering og om kilden er versjonsspesifikk | At kildefilen er lest manuelt for den aktuelle testen |
| `metadata/<versjon>.json` | Registrerte metadata-ID-er, verdi-sett og kilde-ID | Komplett metadata- og kardinalitetsdekning |
| `noark5_standard_values.json` | Navn, metadata-ID og versjon for et eksplisitt verdi-sett | At et XPath-treff faktisk tester hele metadatafeltet |
| `requirements/<versjon>.json` | Eksplisitt registrerte normkrav og kildehenvisninger | Uttrekksbasert verifikasjon av funksjonskrav |
| `noark5_xsd_signatures_v0114_a5.json` + **valgfritt lokalt** XSD-bibliotek | SHA-256 mot det registrerte manifestet for fem XSD-filer per versjon | At hashmanifestet er uavhengig bekreftet mot offisiell original, eller at et uttrekk er XSD-validert |

Registrene er **delvis utfylt**. KDRS Query `query_subtype=3.1,4.0,5.0`
er en historisk dekningserklæring, ikke en offisiell bekreftelse på at alle
katalogkontrollene er versjonskorrekte. Tomt register betyr *ikke gjennomgått*,
ikke *ingen krav*.

## Implementasjon

### Maskinlesbart kilde- og versjonsregnskap

`app/noark5_xpath_version_qa_v021_a3.py` leverer én konsistent, lesbar
versjonsoversikt for katalogtestene, med `by_version` for hver test.

- **`needs_version_qa`**: Katalogen oppgir denne versjonen, men eksplisitt
  versjonsspesifikk kildeverifikasjon mangler.
- **`source_verified_version_link`**: Testdefinisjonen inneholder en eksplisitt
  kildereferanse, lokasjon og verifikasjonsstatus for denne versjonen, og den
  registrerte kilden omfatter versjonen. Dette er **ikke** bestått validering.
- **`registry_unavailable`**: Nødvendige autoritets-/metadata-/krav-/verdi-
  registre kan ikke leses eller er strukturelt ugyldige.
- **`reference_conflict`**: Registrert verdi-sett eller kravenhet er knyttet til
  en motstridende kilde/versjon.
- **`not_declared`**: Testen oppgir ikke aktuell Noark-versjon. Dette betyr
  **ikke** automatisk at testen ikke skal gjelde for versjonen.

Et **registrert verdi-sett** er en egen referansetype,
`registered_value_set_link`. Det er bevisst **ikke** lik
`source_verified_version_link`, og heller ikke en verifisert egenskap ved
XML-uttrekket. Dette gjelder blant annet M300: at et telleruttrykk forekommer
med `dokumentmedium`, betyr ikke at alle M300-regler er validert.

Normative krav knyttes bare ved en eksplisitt `normative_requirement_refs`
med en registrert versjonsspesifikk `requirement_id`. Teknisk
`legacy.test_point` (f.eks. N5.15) blir **ikke** automatisk koblet til en
normativ krav-ID. Funksjonskrav som krever innsikt i arkivsystemets oppførsel
kan ikke godkjennes ut fra et statisk uttrekk.

### Lokal XSD-integritetskontroll

Hvis et lokalt XSD-bibliotek er tilgjengelig, sammenlignes de fem forventede
skjemaene for hver versjon mot **DWM sitt tidligere registrerte SHA-256-manifest**:

- `registered_hash_matches`: Den lokale filen er identisk med den registrerte
  sjekksummen, ikke med en uavhengig nyinnhentet normkilde.
- `hash_mismatch`: Den lokale filen har annen sjekksum.
- `schema_missing`, `schema_unavailable_or_too_large`, `unsafe_schema_path`,
  `registered_hash_missing`, `local_schema_not_connected`: Klar avgrensning
  i stedet for å gjette eller rapportere bestått.

Verktøyet **laster ikke ned** XSD-er, endrer ikke biblioteket og gjennomfører
ikke en ny XSD-validering av arkivmateriale.

### GUI

Eksisterende **Resultatvisninger → Oversikt → Vis alle XPath-kontroller…**
utvides i **samme vindu** med filteret **Versjons-QA**. Velg Noark-versjon,
filtrer for eksempel **Krever kildekontroll**, **Referansekonflikt** eller
**Registrert verdi-sett**, og klikk en test for å se per-versjonens kilde-
register, referansestatus og kjente forbehold. Det er ingen ny pop-up for
vanlig kildevalg, og alle tidligere FEIL/WARNING/NOTE- og KDRS-filtre beholdes.

Den tekniske kjørestatusen og den separate versjonsstatusen vises som **to
ulike akser**. Status `ok` i DWM-motoren gir ingen automatisk endring av
versjonsstatus.

## Bruk fra kommandolinje (uten XML- eller Work-kjøring)

Fra DWM-reporoten, etter at a3-deltaen er lagt over a2:

```bat
py -m app.noark5_xpath_version_qa_v021_a3 --version 5.0
```

For alle versjoner:

```bat
py -m app.noark5_xpath_version_qa_v021_a3
```

Frivillig, dersom du vil kontrollere lokale XSD-filer mot lagret manifest:

```bat
py -m app.noark5_xpath_version_qa_v021_a3 --schema-root "C:\sti\til\digital-archive-workflow"
```

For å lagre JSON utenfor Source, Work og reporoten (ingen overskriving):

```bat
py -m app.noark5_xpath_version_qa_v021_a3 --version 5.0 --output "C:\temp\noark5-version-qa-a3.json"
```

CLI kjører ingen XPath, endrer ikke Source/Work og skriver bare hvis `--output`
er eksplisitt oppgitt. Ikke oppgi en utfil inne i en arkivleveranse.

## Tester og avgrensninger

Målrettede automatiserte tester dekker blant annet:
- KDRS-versjonslisten gir aldri normativ godkjenning.
- Eksplisitt lokasjon og versjonsspesifikk kilde kreves for verifisert lenke.
- Versjonslenker arves ikke fra 3.1 til 4.0 eller 5.0.
- Registrerte metadata-/standardverdi-lenker beholdes atskilt fra M300-validering.
- Tomme kravregistre for 3.1/4.0 teller ikke som dokumentert fullstendighet.
- Manglende, feilversjonerte, dupliserte, feilformede og utilgjengelige registre.
- XSD-manifest: samsvar, avvik, manglende fil og symlink-escape.
- Opprettholdt a1/a2-GUI, filtrering og dynamisk distribusjonsversjon.

**Ikke testet i den isolerte utviklingspakken:** Full Windows `test.bat`,
praktisk Qt-visning, alle faktiske XSD-filer fra originalkildene eller
resultatet fra faktiske Noark 5 v3.1/4.0/5.0-uttrekk. Full repo-integrasjon
må også kjøres etter at deltaen er lagt over riktig baseline.

## Hva du skal teste – og hvordan (kort)

1. Pakk ut a3-ZIP-en **over a2**, i DWM-reporoten.
2. Kjør `test.bat`. Krev **0 feil**. Hoppede tester rapporteres separat.
3. Start `start.bat`; bekreft at v0.2.1-a3 vises.
4. Åpne en eksisterende Noark 5-jobb → **Resultatvisninger → Oversikt →
   Vis alle XPath-kontroller…**.
5. Velg **Noark 5 v5.0**, filter **Versjons-QA: Krever kildekontroll**;
   åpne eksempelvis **C01** og **C02**. Kontroller at det ikke står at
   testene er normativt godkjent. Prøv **Registrert verdi-sett** og se på
   M300-referansen. Gjenta eventuelt med v3.1 og v4.0.
6. **Ikke kjør** nye Noark-tester eller DIAS-pakking i denne røykprøven.

Hvis du har liten tid, kan 4–6 vente; automatisk test er primærkontroll for a3.

## Neste fase: a4

Bygg ut de **faktisk verifiserte** metadata- og kravreferansene fra de
oppgitte Noark-kildene, med mulighet for detaljvisning per metadata-ID og
konkret, dokumentert XPath-/XML-kobling. Samtidig må utvalgte DWM-metrikker
regresjonskontrolleres mot den faktiske Saxon/KDRS-fasiten; a2 og a3
hevder ikke slik ekvivalens.
