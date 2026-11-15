# Noark 5: semantisk verdiregister og XSD-/XPath-sporing (v0.2.1-a6)

**Første prinsipp:** Bruk `docs/NOARK-SOURCE-LIBRARY.md` og `AGENTS.md`.
Intern autoritativ versjonert kilde: `IKAMR/digital-archive-workflow`, commit
`82bd59f23aafdc2386e317e5492941862c2bab9a`,
`docs/kilder/noark/noark5/v{3.1,4.0,5.0}/`.
Dette er IKAMRs interne referansesamling; offisielt normativt opphav er
Riksarkivet/Arkivverket/Nasjonalarkivet. Ingen normative kilder eller originale
uttrekk endres i a6. KDRS Query Standard/U1/U2 er et historisk testgrunnlag,
ikke selv et normativt Noark-kravregister.

**Utgangspunkt:** DWM a5, commit `38bf26fabe8a585e038d97e3c5fdd41bd5ef15ab`.

## 1. Hva er implementert

- `config/noark5/standards/noark5_semantic_values_v021_a6.json`:
  64 **stabile meningsankere** (`N5.Mxxx.NNN`) knyttet til *eksakte*
  XSD-literalverdier fra de 17 enumererte M-typene i både v3.1 og v4.0.
  Lik literal for samme M-ID gjenbruker samme ID mellom versjonene;
  nye v4.0-verdier får nye, vedvarende ID-er. ID-ene er nå kildeankre,
  ikke bevis for at alle betydninger er normativt sammenholdt mot PDF/DOCX.
- `app/noark_semantic_values_v021_a6.py`: leser XSD-referanseverdier,
  kobler rå ordlyd til menings-ID når koblingen er eksplisitt, lager
  QA-forslag uten autoaksept og viser separate rå/semantiske opptellinger.
- `app/noark5_spec_xsd_trace_v021_a6.py`: teknisk kildesporing fra
  **15 lokale original-XSD-er** til annoterte metadata-ID-er, deklarerte
  typebrukspunkter, DWMs versjonerte registre og **leksikalske** XPath-treff.
  Resultatet er *ikke* en fullstendig normativ kravmatrise og ingen XPath-
  semantisk ekvivalenstest mot KDRS/Saxon.
- `gui_qt/noark5_xpath_audit_v021_a1.py`: ny fane **«Verdier og menings-ID»**
  inne i eksisterende XPath-dialog (samme vindu), filtrerbar med eksisterende
  Noark-versjonsvalg og søk. Viser **referanseregisteret**, ikke uttrekkets
  observerte verdier. Jobbspesifikke opptellinger finnes foreløpig i API/CLI.

## 2. Én mening, flere bokstavelige verdier

| Metadata | Observert råverdi | Menings-ID | Semantisk grunnlag | XSD v3.1/v4.0 |
| --- | --- | --- | --- | --- |
| M619 | `Besvart på telefon` | `N5.M619.003` | Eksakt XSD-literal | Oppført |
| M619 | `Besvart i telefon` | `N5.M619.003` | Brukerens uttrykkelige likhets-eksempel, 2026-11-15 | **Ikke oppført** |
| M619 | `Besvart i Telefon` | Ikke tildelt | Forslag til QA | Ikke oppført |
| M300 | `Elektronisk arkiv` | `N5.M300.002` | Eksakt XSD-literal | Oppført |
| M300 | `Elektronkskarkiv` | Ikke tildelt | Mulig leverandør-/skrivevariant, QA | Ikke oppført |
| M300 | `Fysisk arkiv` | Ikke tildelt | DWM-register avviker fra XSD: `Fysisk medium`, QA | Ikke oppført |

Merk: «Besvart på telefon» og «Besvart i telefon» har samme betydning i
brukerens konkrete eksempel, men **ulik XSD-gyldighet ved bokstavelig
enumeration** i v3.1/v4.0. Ingen semantisk alias løser dermed en
XSD-valideringsfeil. En modifisert XSD kan fortsatt brukes til *diagnostisk*
før/etter-evidens via a5-verktøyet; det endrer ikke originalens resultat.

`Svart på telefon` og `Svara på telefon` er bare QA-kandidater, ikke
automatisk godkjente målform-/dialekt-/stilvarianter. Begrepet er
**semantisk ekvivalens**; undergrupper er **preposisjonsvariant**,
**målformvariant**, **rettskrivingsvariant** eller **leverandørspesifikk skrivemåte**.
Forslag kan være feil selv om strengene likner.

## 3. Tre forskjellige tall og et uavhengig QA-lag

`analyze_observations()` gir:

1. `total_occurrences`: alle forekomster, inkludert ukjente verdier.
2. `distinct_raw_values`: forskjellige *eksakte* råverdier, uten trimming,
   case-folding eller omskriving.
3. `distinct_assigned_meaning_ids`: forskjellige menings-ID-er blant verdier
   med kildefestet, brukereksempelbekreftet eller QA-godkjent kobling.

Dessuten gis `qa_candidate_occurrences` og `unassigned_occurrences`.
En test med syntetiske og eksplisitt QA-godkjente koblinger viser
**15 forskjellige råverdier → 9 ID-er**; dette er ikke en telling av et
faktisk Noark-uttrekk.

Det finnes fire separate beslutningslag: (a) XSD-enumeration/facet,
(b) spesifikasjonens egne regler for standard-/egendefinerte verdier,
(c) faglig semantisk kobling, (d) diagnostisk XSD-modifikasjon.
Ingen av dem kan automatisk oppgradere de andre til «bestått».

## 4. Fremtidige egendefinerte betydninger

Nye menings-ID-er legges **append-only** til det sentrale registeret, som
`N5.M619.008`, `N5.M619.009` osv. En ny lokal kategori må registreres som
`qa_approved_custom_concept` med `qa.decision_id`, `qa.approved_by`,
`qa.approved_at` og `qa.reason` før den godtas som en *intern meningskategori*.
Det gir aldri i seg selv rett til egendefinert XSD-/spesifikasjonsverdi.

En aliasgodkjenning kan oppgis via en **eksplisitt lokal beslutningsfil i Work**:

```json
{
  "format_version": 1,
  "decisions": [
    {
      "metadata_id": "M619",
      "raw_value": "Besvart per telefon",
      "concept_id": "N5.M619.003",
      "decision": "approve_semantic_link",
      "decision_id": "QA-EKSEMPEL-IKKE-GODKJENT",
      "approved_by": "ERSTATT_MED_FAKTISK_GODKJENNER",
      "approved_at": "2026-11-15",
      "reason": "ERSTATT_MED_DOKUMENTERT_FAGLIG_BEGRUNNELSE"
    }
  ]
}
```

**JSON-eksempelet er bare struktur:** ikke en gjennomført QA-beslutning.
Programmet nekter beslutninger uten sporbarhet eller som peker på menings-ID
for feil M-felt. En ny QA-beslutning må aldri overskrive historisk evidens;
oppbevar beslutningsfilene med jobb-/saksidentifikator i Work.

## 5. Hvilke XSD-verdier er undersøkt

De 17 enumererte M-typene i **begge** v3.1 og v4.0:
`M050`, `M051`, `M052`, `M053`, `M054`, `M056`, `M082`, `M087`,
`M089`, `M217`, `M300`, `M450`, `M503`, `M506`, `M508`, `M619`, `M700`.

v4.0 har to flere oppførte `M087`-verdier (`Intern kopimottaker`,
`Medavsender`) og to flere `M619`-verdier (`Besvart med notat`,
`Saken ble avsluttet`) sammenlignet med v3.1.
Disse XSD-typedefinisjonene i v5.0 har **ingen enumeration**. Dette betyr
ikke at v5.0-dokumentasjonen mangler standardverdier eller at alle egne
verdier er normativt tillatt. `M300` og `M619` i v5.0 har teknisk `minLength=1`.

Den historiske DWM-tabellen `noark5_standard_values.json` endres **ikke**
uten QA. M300-avviket (`Fysisk arkiv` i DWM mot `Fysisk medium` i XSD)
står fortsatt som åpent kontrollpunkt.

## 6. Kjøring med lokale kilder

Verdiopptelling fra *allerede aggregert* jobbresultat (ingen XML leses):

```bat
py -m app.noark_semantic_values_v021_a6 --metadata M619 --noark-version 4.0 --counts-json "C:\temp\m619-raverdier.json"
```

Eksempel på innhold i `m619-raverdier.json`:

```json
{"Besvart på telefon": 13, "Besvart i telefon": 2, "Besvart med brev": 5}
```

Med QA-beslutninger: legg til `--decisions-json "C:\temp\m619-beslutninger.json"`.
CLI skriver JSON til stdout, uten å endre inndata eller opprette rapportfiler.

XSD-basert deknings-/sporingsrapport fra våre **originale lokale
referansekilder**:

```bat
py -m app.noark5_spec_xsd_trace_v021_a6 --source-root "C:\git\IKAMR\digital-archive-workflow" --dwm-root "C:\git\IKAMR\data-workflow-manager" --output "C:\temp\noark5-xsd-trace-a6.json"
```

Dette verktøyet kontrollerer alle fem XSD-filer per versjon, deres hash,
metadata-typedefinisjoner, XSD-enumerationer mot a6-registeret, eksisterende
DWM metadata-/kravregistre samt leksikalske XPath-kandidater. Rapporten
skrives **utenfor** begge repoer og nekter overskriving.

`source_checkout_commit` skal samsvare med vår versjonerte kildesamling.
Hvis lokalt repo er på en annen revisjon, flagges dette for QA; ingen
versjonssynkronisering skjer automatisk. Originale PDF/DOCX/XLSX-kilder må
fortsatt leses og vurderes punktvis før **normativ kravdekning** kan oppgis.

## 7. Gjenstående før full Noark-kontroll

- **Normativ fullgjennomgang:** hovedspesifikasjoner, metadatavedlegg og
  v3.1-kravoversikten (PDF/DOCX/XLSX) per versjon, med krav-ID, ordlyd,
  lokasjon og kategorisering av uttrekksverifiserbart/funksjonelt krav.
- **KDRS-formelparitet:** 60 katalogdefinisjoner, 45 metrikkjobber og 15
  spesial-/sammensatte jobber må testes semantisk mot KDRS Standard/U1/U2.
  Leksikalsk XPath-omtale er bare kandidat.
- **Faglig QA:** M300-avviket, reglene for egendefinerte M619-verdier og
  språk-/leverandørvarianter må vurderes før normative vurderingsregler endres.
- **Operativ Work-integrasjon:** a6-fanen viser versjonert *referansekatalog*.
  Neste trinn er å koble faktiske lagrede XPath-observasjoner, linjer og
  objektkontekst til disse begrepene – ikke å lese depotdata til Git-repoet.

**Teststatus i leveransen:** Automatiserte a6-enhetstester og eksisterende
målrettede a5-tester; full Windows `test.bat` må kjøres av repoets eier.
