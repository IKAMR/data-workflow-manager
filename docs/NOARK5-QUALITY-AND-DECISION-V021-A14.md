# DWM v0.2.1-a14 – lesbar kontrollforklaring og kildebundet DIAS/METS-kontekst

## Formål

a14 bygger **direkte på committet v0.2.1-a13**. Den endrer ikke Noark-tester,
Arkade-/KDRS-status, eksisterende depotvedtak, tidligere faglige merknader,
rapportprofilene Enkel/Medium/Full eller a20-vedleggene A–D.

Prioritet: En saksbehandler skal kunne forstå et konkret kontrollfunn **før**
hun eller han skriver en faglig vurdering. Opplysninger som allerede finnes i
`Work/metadata/depot_metadata.json`, må dessuten kunne leses i rapportene,
uten å framstå som bekreftet kanonisk identitet eller nye standardkrav.

## Funnforklaring i det eksisterende GUI-et

**Eksakt sti:** `Resultatvisninger → Faglig vurdering → Visning: Depotvurdering`
→ velg **JOB-001 – content** → trykk **KS / depot: vurder funn og lag rapporter…**.

Øverst kan operatøren fremdeles filtrere på `Nivå` og `Søk`. For valgt funn
vises nå først **«Hva er funnet, og hvorfor er det et avvik?»** med fire korte
opplysninger: faktisk observert resultat, krav/årsak, nødvendig skille mellom
verdi og kontrollutfall og dokumentert Noark-versjonsgrunnlag.

**«Vis XML-linjenumre og kildehenvisninger…»** åpner et **eget, resizerbart
vindu** med rapporterte test-ID, teknisk status, arkivdel, kildefil,
alle kjente XML-linjenumre og evidensreferanse, samt knapp for å kopiere
kildedetaljene. Dette viser **linjenumre, ikke selve XML-innholdet**.
Ingen tekniske linjenumre eller SHA-referanser er fjernet.
Kildedetaljene presses ikke lenger inn i et 118-pikselsfelt under
funnforklaringen. Vurderingsfeltet og knappene **Lagre faglig merknad**,
**Velg a11 KDRS QA…**, **Velg mål…** og
**Lag KS + depot + Full-rapport (a20)** er beholdt. Mer av vindushøyden
brukes innledningsvis på vurderingspanelet.

### Dokumentert eksempel: Arkade 5 N5.22

`1525_004` har 20 journalposter i arkivdel 4 med status `Journalført`.

- **Faktisk funn:** Arkade 5 N5.22 rapporterte `ERROR`.
- **Kravgrunnlag:** Noark 5 v5.0, vedlegg 1, M053. Journalposter som
  avleveres skal ha `Arkivert` eller `Utgår`.
- **Viktig skille:** `Journalført` er en registrert M053-standardverdi i
  Noark 5 v5.0, men oppfyller ikke statuskravet ved uttrekk/avlevering.
  Arkades ERROR er derfor et reelt avvik og **skal beholdes**.
- **Kilde for versjonsopplysning:** DIAS/METS registrert i Work oppgir v5.0.
  Et slikt metadatafelt er ikke automatisk en uavhengig bekreftelse av
  uttrekkets normative versjon.

For versjoner som **ikke** er dokumentert som v5.0, vises v5.0-regelen bare
som en identifisert referanse; programmet krever separat kildegrunnlag for den
aktuelle versjonen. For andre funn (for eksempel N5.15) finnes **ikke** et
ferdig normativt tolkningsgrunnlag i a14, og GUI-et sier dette uttrykkelig
framfor å finne på en regel.

Dette er foreløpig **lesbar kildekontekst**, ikke det framtidige biblioteket
med foreslåtte avvikstekster eller forhåndsdefinert håndtering.

## DIAS/METS i begge mottakertilpassede rapporter

a14 leser, men skriver **aldri**, følgende Work-objekter:

- `metadata/depot_metadata.json`: registrerte felt for arkivsystem,
  systemversjon, Noark-versjon, uttrekkssystem, roller, mottaker, oppgitt
  periode, avtale-/saksreferanse og beskrivelse.
- Bevarte `metadata/source_evidence/.../source/info.xml`-kopier når de er
  referert i metadataen: SHA-256 kontrolleres mot registrert importhash.
- Eksisterende `config/noark5/standards/noark5_standard_values.json`:
  M053-standardverdier for Noark 5 v3.1, v4.0 og v5.0 leses som **historisk
  referanse**, ikke som en ny validator.

**Kildeklassifisering:** `METS ARCHIVIST`, `METS OWNER` og `METS CREATOR`
vises som forskjellige roller. `METS CREATOR` er ikke automatisk arkivskaper.
Felt i `current` kan ha blitt redigert etter import, og er derfor merket
**Work/METS – registrert, ikke bekreftet**. Dersom Work og kanonisk kilde
oppgir motstridende Noark-versjoner, rapporteres konflikt; ingen versjon
velges automatisk. **Noark 5 v4.0** forveksles aldri med **Noark 4**.

Begge KS- og depotutkastene har supplerende Work/METS-opplysninger nær
begynnelsen av rapporten, samt ny seksjon **11. DIAS/METS – supplerende
Work-opplysninger**, med kildeforklaring, bevarte importhash-er og
N5.22-eksemplet. Den kanoniske linjen kan fortsatt si «Ikke dokumentert»
når den kanoniske modellen mangler opplysningen – det er bevisst: Work/METS
**erstatter ikke** den.

Evidensmanifestet inneholder SHA-256 for metadatafilen og verifiserte
originalkopier. Ved feil jobbidentitet, ugyldig filstruktur, symlink i
kildesti eller SHA-256-avvik avbrytes eksporten, fremfor å bruke metadata
fra feil kilde.

## Praktisk test på Windows

1. Pakk delta-ZIP over **committet a13**.
2. Kjør `test.bat`. Alle eksisterende a12/a13-tester skal fortsatt bestå.
3. Start DWM og gå til `Resultatvisninger → Faglig vurdering → Visning: Depotvurdering`.
4. Velg uttrekk `JOB-001 – content` og åpne
   **KS / depot: vurder funn og lag rapporter…**.
5. Søk `N5.22`. Kontroller at 20 `Journalført`, avleveringskravet,
   korrekt `ERROR`, kilde for oppgitt v5.0 og skillet mellom standardverdi
   og uttrekkskrav er tydelig, før XML-linjene vises.
6. Klikk **Vis XML-linjenumre og kildehenvisninger…** og bekreft at et
   eget, lesbart detaljvindu åpner med alle rapporterte linjer, arkivdel og
   evidensfil. Bruk eventuelt **Kopier kildedetaljer** og deretter **Lukk**.
   Vurderingsfeltene skal ikke flytte seg eller bli trangere.
7. Søk `N5.15`: for dette funnet må GUI-et *ikke* finne på kravtekst.
8. Klikk **Velg mål…**, velg en ny katalog og deretter
   **Lag KS + depot + Full-rapport (a20)**.
9. Åpne **Åpne siste rapportpakke**. Se seksjon 1 og seksjon 11 i KS-/depotutkast;
   verifiser at informasjonen er tydelig kildemerket. Kontroller at Full-rapport,
   vedlegg A–D og tidligere faglige kommentarer fortsatt er tilgjengelige.

Ikke bruk samme rapportmappe to ganger; eksisterende eksport skal ikke
overskrives.

### Tester og begrensninger

- **44 målrettede tester bestått i utviklingsmiljø**: 17 fra a12, 10 fra
  a13 og 17 nye for a14. Inkluderer versjonskonflikter, Noark 4/skille,
  feil jobb, endret bevart METS-kopi, kildehash, HTML-escaping, riktig
  mottaker for faglige kommentarer, historiske M053-verdier og uendret
  teknisk ERROR.
- Realistiske lagrede `1525_004` Work-resultater er brukt til
  a14-snapshot og rapporteksport. Work-metadata oppga v5.0, WebSak og
  separate roller; SHA-256 for bevart DIAS/METS-kopi stemte.
- Full Windows `test.bat` og GUI-prøven er **ikke utført her**.
- a14 implementerer ikke sjekklistene fra `sjekkliste.docx` og
  `sjekkliste-mets.docx` som ferdig beslutnings- eller signeringsflyt. Disse
  kommer senere med brukerstyrt avklaring av omfang og krav.
- Ingen automatiske rettinger, gjenbrukbare forslagstekster, arkivskapersvar,
  depotvedtak, Noark 5 v6.0 eller DIAS AIP-handlinger er introdusert.

Referanser: `docs/TODO-ROADMAP.md`,
`docs/NOARK5-QUALITY-AND-DECISION-V021-A13.md`,
`docs/DIAS-METADATA-MAPPING.md` og
`config/noark5/standards/noark5_standard_values.json`.
