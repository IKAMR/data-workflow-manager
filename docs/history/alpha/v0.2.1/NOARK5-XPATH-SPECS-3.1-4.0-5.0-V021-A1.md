# Noark 5 v3.1, 4.0 og 5.0 - XPath, KDRS Query og kildekartlegging

## Formål og etterprøvbar status, v0.2.1-a1

Arbeidspakken kartlegger eksisterende KDRS Query Standard/U1/U2 mot DWM sitt
`lxml`-baserte kataloggrunnlag, viser deklarerte XPath-uttrykk og originale
KDRS/Saxon-uttrykk side om side, og gir en lesbar GUI for **faktisk lagret**
Work-status. Det er et første, sporbarhetssikret trinn, **ikke** en ferdig
normativ kravmapping eller attestasjon av full KDRS-semantisk ekvivalens.

Kildeversjoner for gjennomgangen:

- DWM: `IKAMR/data-workflow-manager` commit
  `b7eee003933158bbcc4c02669bcdfecfbc5e311e` (v0.2.0).
- Historiske KDRS-definisjoner i DWM:
  `docs/reference/kdrs-query/xml-queries_noark5_2026-05-26.txt`,
  `..._U1.txt` og `..._U2.txt` (opprinnelige jobber og uttrykk).
- Noark-spesifikasjoner og skjemaer: `IKAMR/digital-archive-workflow`
  commit `82bd59f23aafdc2386e317e5492941862c2bab9a`,
  `docs/kilder/noark/noark5/v{3.1,4.0,5.0}/`.
- DWM-definisjoner: `config/noark5/tests/xpath_catalog_2026_05_26.json`.

## Hva er verifisert i eksisterende materiale?

| Tema | Faktisk dokumentert | Hva det IKKE beviser |
| --- | --- | --- |
| KDRS Standard | 59 originale `job_id` registrert i masterfilen | Ikke kontroll av hver enkelt original XPath mot dagens DWM-resultat |
| U1/U2 | U01 og U02 finnes i egne kildetekster og også i Standard | At alle U1/U2-sammensetninger er maskinelt verifisert |
| DWM-katalog | 60 definisjoner: 59 originale KDRS-ID-er + `DWM-AU01` | Ikke 60 uavhengige normative krav eller 60 obligatoriske tester |
| Normal produksjonsprofil | 58 aktive; U01/U02 bevart som regresjonsreferanse | U01/U02 kjøres ikke automatisk i normalprofil |
| U1/U2-datamapping | 43 `covered`, 3 `deferred` i eldre dekningskontrakt | Ikke full normative kravdekning |
| Katalogens Noark-versjoner | 57 av 60 har `master_query_subtype_needs_qa` | Ikke selvstendig XSD-verifisert versjonsgyldighet |
| Standardverdisjekker | 16 koblinger mellom katalogtest og versjonsdelt verdiregister | Manglende/annen verdi er ikke automatisk feil |
| Normative kravregistreringer | 3.1: 0, 4.0: 0, 5.0: 2 | Det store omfanget av Noark-krav er ennå ikke modellert |

Det foreligger ikke uavhengig sammenlikning av alle opprinnelige KDRS
XPath 2.0/3.0-uttrykk med alle DWM `lxml`/Python-implementasjoner. I denne
versjonen bevares originaluttrykkene som kilde, mens de deklarerte DWM-uttrykkene
og en separat, valgfri **syntaks-kompilering** kan kontrolleres. KDRS bruker
Saxon-funksjoner som ikke alltid har direkte XPath 1.0-ekvivalent. En gyldig
`etree.XPath`-kompilering er derfor IKKE ekvivalensbevis.

## XSD-samling, endringspunkter og begrensninger

Det er registrert fem XSD-filer per versjon (totalt 15):
`arkivstruktur`, `endringslogg`, `loependeJournal`, `metadatakatalog`,
`offentligJournal`. De tre versjonene kan ikke antas utbyttbare.

Et innledende syntaktisk navneuttrekk fra XSD-ene i kilderepoet gir:

| XSD-fil | v3.1 | v4.0 | v5.0 |
| --- | ---: | ---: | ---: |
| `arkivstruktur.xsd` (deklarerte / unike elementnavn) | 271 / 166 | 271 / 166 | 282 / 167 |
| `loependeJournal.xsd` (deklarerte / unike elementnavn) | 41 / 35 | 41 / 35 | 51 / 44 |
| `offentligJournal.xsd` (deklarerte / unike elementnavn) | 36 / 35 | 36 / 35 | 44 / 40 |

Mellom 4.0 og 5.0 endres bl.a. `sakspart` til `part` og `gradering`
til `grad` i relevante XSD-er; flere journalmetadata kommer til.
DWM-katalogen har allerede særskilte `sakspart`/`part`-beregninger (`F01`,
`L02`) og `gradering`/`grad`-beregninger (`F09`). Dette er relevant dekning,
men hver semantisk regel, forekomst og anvendelighet må vurderes mot riktig
XSD og standardversjon.

Det nye lokale XSD-verktøyet teller *deklarasjoner*, rapporterer manglende
skjemaer og kildehash (SHA-256), og viser navn som forekommer i deklarerte
XPath-strenger. Et navn som nevnes i en XPath, er IKKE dokumentert validering
av forekomstkrav, datatype, rekkefølge, unike ID-er, kryssreferanser eller
normative krav. Python-specialhandlers og annen eksisterende XML/XSD-validering
inngaar heller ikke i denne leksikalske målingens teller.

De offisielle spesifikasjonsdokumentene for 3.1, 4.0 og 5.0 er registrert i
kildesamlingen. Hele normative kravtabeller, metadatavarianter og
funksjonskrav er foreløpig **ikke** gjennomgått og kryssreferert kravnivå
for kravnivå i DWM-registeret. Kilderepoet dokumenterer selv ufullstendig
opphav/proveniens og publiseringsstatus for Noark 5-filer. Denne versjonen
utgir derfor ikke en godkjent normativ dekningsprosent.

## DWM implementasjon og nye arbeidsflater

- `app/noark5_xpath_audit_v021_a1.py`: skrivebeskyttet oversikt over alle
  60 katalogtestene, ID-dekning fra alle tre originale kilder, tilhørighet,
  originale KDRS-uttrykk, deklarerte lxml-XPath-er, Work-indeks/resultat og
  valgfri lokal XSD-inventarliste. Ingen Source-skanning.
- `gui_qt/noark5_xpath_audit_v021_a1.py`: i **Resultatvisninger ->
  Oversikt -> Vis alle XPath-kontroller...**. Filtrer på valgt jobb,
  oppgitt versjon, Status, KDRS Standard/U1/U2 eller DWM, og søk på XPath,
  metadatakode, navn, ID, XML-fil og kontrollpunkt. Velg en rad for
  referanseuttrykk og lagret evidens. Rå JSON beholdes.
- `gui_qt/main_v020_a6.py`: bruker eksisterende resultatvindu og installerer
  visningen etter a6-gruppenavigasjon. Ingen nye kontroll-/godkjenningsmotorer.
- Originale KDRS-uttrykk leses fra kildetekstene og *kjøres ikke* i Qt-dialogen.
  DWM bruker allerede lxml/Python for egne beregninger. De samme originaluttrykkene kan
  derfor inspiseres, også de store U01 og U02.

### Hva FEIL, WARNING, NOTE osv. betyr

| Filter | Eksakt kontrakt |
| --- | --- |
| `FEIL` | Lagret testkjøring rapporterte `status=error` |
| `WARNING` | Dokumentert avstemmingsavvik eller ekstraverdi mot uttrykkelig valgt versjons verdireferanse: manuell vurdering, ikke normativ feil |
| `NOTE` | Referanse mangler eller valgt versjon har ingen observerte verdier i eksisterende resultat |
| `MANGLER` | Testen rapporterte `source_missing`; en valgfri journalfil kan mangle |
| `UKJENT` | Feilaktig, uleselig eller utilgjengelig resultat / ukjent status |
| `UTFORT` (UTFØRT) | Testen kjørte teknisk med `status=ok`; det betyr IKKE at uttrekket er korrekt eller godkjent |
| `IKKE_KJORT` | Ingen registrert kjørt test i valgt Work; ikke automatisk et avvik |
| `REGRESJON` | U01/U02 finnes, men er normalt utenfor produksjonsprofilen |

Etter valg av Noark-versjon brukes bare den versjonens lagrede
`_standard_values` til ekstra WARNING/NOTE. Versjonen bestemmes ikke
automatisk av tilfeldig observerte data i denne oversikten. Bruk eksisterende
XSD-identifikasjon og egne faglige kilder for aktuell versjon.

## Hvordan kjøre og teste

1. Pakk ut delta-ZIP i DWM-reporoten, kjør `test.bat` og `start.bat`.
2. Åpne en eksisterende Noark 5-jobbliste og velg en jobb med kjent Work.
3. Gå til **Rapportering -> Resultatvisninger -> Oversikt -> Vis alle
   XPath-kontroller...**. Sjekk at 60 testdefinisjoner vises uansett om det
   finnes lagrede kontroller.
4. Filtrer `Standard`, `U1/U2`, `DWM`. Åpne C01, F01, F09, U01 og U02;
   sammenlikn original KDRS-kilde og DWM XPath/Python-beskrivelse.
5. Velg aktuell Noark 5-versjon **3.1**, **4.0** eller **5.0** eksplisitt.
   Filtrer på `FEIL`, `WARNING / Vurder`, `NOTE`, `Mangler kilde`,
   `Ikke kjørt`; kontroller at eldre lagrede jobber ikke feilklassifiseres.
6. Bruk `Åpne lagret test-JSON` hvis Work har disse filene. Ingen original
   arkivdata eller eksisterende resultater skal skrives om.
7. Valgfritt: klon `digital-archive-workflow` ved siden av DWM eller velg
   den lokalt via `Velg lokalt XSD-bibliotek` -> `Vis XSD-kartlegging`.
   Sjekk 15 XSD og at rapporten **ikke** kalles full kravdekning.

CLI for kildetall uten Qt (fra reporoten):

```bat
py -m app.noark5_xpath_audit_v021_a1 --compile-xpath
```

Med lokalt bibliotek, kildesammenlikning og maskinlesbar JSON:

```bat
py -m app.noark5_xpath_audit_v021_a1 --compile-xpath --schema-root "C:\\git\\IKAMR\\digital-archive-workflow" --output "C:\\temp\\noark5-xpath-kildekartlegging.json"
```

Begge kommandoene er skrivebeskyttede for DWM-katalog, Source og Work;
`--output` skriver bare den **eksplisitt valgte** rapportfilen.

## Neste arbeid, konkret, ved praktisk Noark 5-validering

1. Verifisere alle **originale KDRS-uttrykk mot individuelle DWM-metrikker**
   med samme testuttrekk, inkl. generiske grupper, datointervaller,
   numeriske/aggregerte funksjoner, U01/U02-rekonstruksjon og avstemming.
   Dokumentere semantiske forskjeller, tilsiktet normalisering og reelle feil.
2. Ta normative krav og metadatafelt **per versjon og side/XSD-komponent**,
   klassifiser bare de som kan valideres fra et statisk uttrekk; registrer
   sporbar Noark-kilde og kontrollerte betingelser. Fortsett utover M300,
   M082, M500, M502, uten å hardkode testuttrekkets observerte verdier som norm.
3. Knytte fysiske XML-forekomster til hvert relevant vurderingspunkt (fil,
   XPath, faktisk linje, system-ID, arkivdel, kildeversjon, regelreferanse),
   med dataminimering og uten å endre Source.
4. Koble de kanoniske funnene til filterbar Kontroll-/Rapportering-visning
   med eksplisitt semantikk for ERROR / WARNING / NOTE / OK / UKJENT og
   detaljer for hvilke tester som er kjørt eller mangler.
5. Regresjonsteste mot faktiske Noark 5-uttrekk av ulike versjoner, med
   miljøet og kildefilene dokumentert. Unngå falske nulldata eller
   feilklassifisering bare fordi en versjon ikke benytter et felt.
