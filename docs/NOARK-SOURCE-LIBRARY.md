# Noark-kilder: Digital Archive Workflow

## Bindende kildepolicy for DWM og Noark 5-arbeid (2026-11-15)

**IKAMRs autoritative, interne referansesamling (single source of truth) for Noark 5
spesifikasjoner, vedlegg, eksempler og XML-skjemaer er repositoriet
[`IKAMR/digital-archive-workflow`](https://github.com/IKAMR/digital-archive-workflow),
under `docs/kilder/noark/noark5/`.** Den samlingen skal alltid konsulteres
**før** annen kildesøking og **før** nye Noark-krav, metadata, XSD-regler,
versjonskoblinger, XPath-kontroller eller dekningspåstander innføres i DWM.
Dette gjelder spesielt de separate, fullstendige kildearkivene for
**v3.1, v4.0 og v5.0**: hovedspesifikasjon, metadatakataloger, øvrige vedlegg,
eksempel-XML og fem XSD-filer per versjon. DWM skal ikke erstatte dem med
løsrevne nettfunn eller antakelser om at standardversjoner er like.

**Normativt opphav og vår referansesamling er ulike ting:** Originale publikasjoner
fra Riksarkivet/Arkivverket/Nasjonalarkivet er standardenes normative opphav.
`digital-archive-workflow` er den **autoritative versjonerte kildesamlingen for
vårt arbeid i IKAMR/DWM**. Kilderepoet har i dag uavklarte opphavs-/utgave-
opplysninger for enkelte Noark 5-filer; dette skal registreres, ikke forties.

### Fast arbeidsrekkefølge og avviksbehandling

1. **Intern kilde først:** Åpne eksakt dokument/XSD for valgt Noark-versjon i
   `IKAMR/digital-archive-workflow`; registrer filsti og den eksakte Git-commiten.
   Sjekk relevant kravnummer, metadata-ID, avsnitt/side og/eller XSD-komponent.
2. **Verifiser ved behov eksternt:** Sammenlign gjerne med Nasjonalarkivet,
   Arkivverket, Riksarkivet eller andre etterprøvbare kilder; noter URL,
   utgivelsesdato, versjon og eventuelle rettelsesutgaver. Et eksternt dokument
   erstatter **aldri automatisk** innholdet i vår samling.
3. **Ved ethvert avvik:** Opprett en sporbar **QA-sak for gjennomgang hos repositoriets eier** med begge
   kilder, versjon, eksakte filnavn/komponenter, forskjell, konsekvens for DWM
   og foreslått løsning. **Ikke endre originalkilder, normative kontrollregler
   eller klassifiseringsstatus før repositoriets eier har gjennomgått saken.**
4. **Etter QA-beslutning:** Oppdater eller utvid `digital-archive-workflow`
   først dersom beslutningen tilsier det, med kildeproveniens, versjon, hash og
   beslutningsreferanse. Deretter oppdateres DWM sine maskinlesbare registre,
   tester, XPath-implementasjoner og dokumentasjon, med sporbar kobling tilbake.
5. **Ingen stille harmonisering:** Ikke bland XSD-er mellom versjoner, ikke
   erstatt lokale kilder med «nyeste» uten godkjenning, og ikke regn en omtale
   av et metadatafelt i XPath som en implementert normativ validering.

### Originale kilder til Noark 5 XPath-testene

Den historiske **KDRS Query Standard/U1/U2**-kilden er
[`IKAMR/KDRS_Query`](https://github.com/IKAMR/KDRS_Query), særlig
`doc/xml-queries_noark5_2026-05-26.txt`,
`doc/xml-queries_noark5_2026-05-26_U1.txt` og
`doc/xml-queries_noark5_2026-05-26_U2.txt`.
DWM har referansekopier under `docs/reference/kdrs-query/` og en egen
maskinlesbar katalog under `config/noark5/tests/`.
**KDRS Query er historisk testgrunnlag, ikke normativ Noark-spesifikasjon.**
Ved semantiske endringer må alle tre sammenholdes; forskjeller skal dokumenteres
og vurderes, ikke glattes over automatisk.

**Obligatorisk ved enhver ny Noark 5-utviklingsøkt:** Les denne filen,
`AGENTS.md` og de to originale kilde-repoenes relevante filer før implementasjon.
Når kildegrunnlag ikke er tilgjengelig, oppgi begrensningen og unnlat å påstå
at full kravdekning eller semantisk ekvivalens er verifisert.

---

## Katalog (kontrollert 2026-11-13)

| Standard/versjon | Innhold i kilderepoet | Katalog |
| --- | --- | --- |
| Noark 3 | Historisk spesifikasjon (PDF, 1994) | [noark3](https://github.com/IKAMR/digital-archive-workflow/tree/main/docs/kilder/noark/noark3) |
| Noark 4 / 4.1 | Del I/II, rettelser, endringsdokumenter og 100 `.DTD`-filer | [noark4](https://github.com/IKAMR/digital-archive-workflow/tree/main/docs/kilder/noark/noark4) |
| Noark 5 v1.0 | 4 XSD | [v1.0](https://github.com/IKAMR/digital-archive-workflow/tree/main/docs/kilder/noark/noark5/v1.0) |
| Noark 5 v2.0 | 5 XSD | [v2.0](https://github.com/IKAMR/digital-archive-workflow/tree/main/docs/kilder/noark/noark5/v2.0) |
| Noark 5 v3.0 | 5 XSD | [v3.0](https://github.com/IKAMR/digital-archive-workflow/tree/main/docs/kilder/noark/noark5/v3.0) |
| Noark 5 v3.1 | 5 XSD, standard og vedlegg (PDF), eksempel-XML | [v3.1](https://github.com/IKAMR/digital-archive-workflow/tree/main/docs/kilder/noark/noark5/v3.1) |
| Noark 5 v4.0 | 5 XSD, standard og vedlegg (PDF/DOCX), eksempel-XML | [v4.0](https://github.com/IKAMR/digital-archive-workflow/tree/main/docs/kilder/noark/noark5/v4.0) |
| Noark 5 v5.0 | 5 XSD, standard og vedlegg (PDF/DOCX), eksempel-XML | [v5.0](https://github.com/IKAMR/digital-archive-workflow/tree/main/docs/kilder/noark/noark5/v5.0) |
| Noark 5 v6.0 | Standard og vedlegg (PDF/DOCX); ingen XSD i denne samlingen | [v6.0](https://github.com/IKAMR/digital-archive-workflow/tree/main/docs/kilder/noark/noark5/v6.0) |

Se [kilderepoets README](https://github.com/IKAMR/digital-archive-workflow/blob/main/docs/kilder/noark/README.md) og
[SOURCE-MANIFEST.json](https://github.com/IKAMR/digital-archive-workflow/blob/main/docs/kilder/noark/SOURCE-MANIFEST.json).
Full kildeproveniens for Noark 5 er ikke ferdig kvalitetssikret i samlingen; fravær av et dokument betyr ikke at det aldri ble utgitt.

## Regler for bruk i DWM

1. **Versjonsspesifikt grunnlag:** Finn faktisk skjema-/standardversjon for uttrekket ved å sammenligne med lagrede XSD-er, namespace, struktur og eventuelt SHA-256. Ikke stol på versjonsteksten i `arkivuttrekk.xml` alene. Behold usikkerhet når grunnlaget ikke er entydig.
2. **Tre ulike vurderinger:** Skill mellom XSD-validitet, sammenligning med standardens verdilister og depotfaglig vurdering. En verdi som ikke samsvarer med en historisk liste er ikke automatisk en XSD-feil eller et regelbrudd.
3. **Siter nøyaktig:** Når DWM viser et krav eller metadata-ID (for eksempel `M300`), oppgi Noark-versjon, eksakt kildefil og helst avsnitt/side eller XSD-komponent. Referanser til feil versjon må ikke brukes som normativt grunnlag.
4. **Spor kilden:** Knytt avvik til original XML-fil, XPath, linje og identifikator når det finnes faktisk evidens. Ikke konstruer manglende forekomster.
5. **Reproduserbarhet:** Ved bruk som maskinelt regelgrunnlag, lås kilderevisjon/commit, kildefil og verifisert hash. Lenker til `main` er navigasjon, ikke en immutabel kildeversjon.
6. **Erfaringsdata separat:** Delbare erfaringer og lokale valg er ikke offisiell standardtekst; automatiske forslag krever synlig kilde og faglig godkjenning.

DWM sitt nåværende standardverdiregister ligger i
`config/noark5/standards/noark5_standard_values.json` og er **et eget, delvis maskinlest kontrollgrunnlag**, ikke en fullstendig kopi av spesifikasjonene i kildebiblioteket. Se [NOARK5-STANDARD-VALUES.md](NOARK5-STANDARD-VALUES.md).

Ingen automatisk nedlasting, kopiering eller synkronisering av Noark-kildene er implementert med denne dokumentasjonsendringen.

## Kildebasert DOCX/XLSX-kravregister – v0.2.1-a9

`app.noark5_requirement_registry_v021_a9` lager et **ikke-godkjent kravregister for
faglig QA** på grunnlag av kilderepoet. Dette erstatter ikke normative dokumenter.
De 12 avledede Word-kopiene lagt til i kildecommit
`8d28e312e1` finnes på GitHub. Ved enhver ny kjøring lagres faktisk
kilderevisjon og SHA-256 for hver DOCX. `SOURCE-MANIFEST.json` beskriver
foreløpig original-PDF-ene, men ikke alle avledede DOCX-kopiene. Deres
manifeststatus vises derfor som `not_registered_derived_working_copy`; dette er
ikke automatisk et manglende kildekrav.

Kjør først a8 og behold dens `noark5-a8-requirements.json`, deretter fra DWM-repoet:

```bat
py -m app.noark5_requirement_registry_v021_a9 --a8-report "C:\temp\noark5-a8-qa\noark5-a8-requirements.json" --source-root "C:\git\IKAMR\digital-archive-workflow" --output-dir "C:\temp\noark5-a9-qa"
```

`--output-dir` må være ny eller inneholde ingen av rapportene. Programmet
oppretter fem filer:

- `noark5-a9-requirements.json`: hele registrerte kildeordlyden med
  versjon, kravnummer, kravtype, merknads-/betingelsesfelt, Word/XML-radanker,
  kilde-SHA og individuelle QA-behov. Ingen normative krav er godkjent.
- `noark5-a9-requirements.csv`: filtrerbare kildekandidater til gjennomgang.
- `noark5-a9-source-inventory.json`: kildeversjon, PDF-identitet mot manifest,
  DOCX-hash, dokumentlesbarhet, OOXML-variant og tabell-/teksttelling.
- `noark5-a9-unresolved.csv`: **FEIL/WARNING/NOTE** for manglende dokumenter,
  ulik ordlyd, kildeidentitet, duplikater, ikke fullførte krysskontroller osv.
- `noark5-a9-summary.md`: samlede resultater og begrensninger.

v3.1 bruker den originale, SHA-kontrollerte XLSX-kravtabellen som **primær kilde**,
og sammenholder kravnummerrader og ordlyd med den konverterte DOCX-hovedstandarden.
Krav som bare står i ett av dokumentene eller som har vesentlig avvikende
tekst, flagges for manuell kontroll. v4.0 og v5.0 bruker DOCX-tabellceller
fra hovedstandardene. Begge OOXML-varianter støttes: Strict og Transitional.
Nummererte fritekstavsnitt som ikke kan knyttes til kravtabell, skilles ut
som separate uverifiserte kandidater i JSON-filen. Ingen avvik glattes over
eller fører automatisk til nye regler.

For **alle** versjoner brukes de øvrige DOCX-vedleggene i en kildeinventar-
kontroll, med lesbarhet og tabelltelling; vedleggene utvides ikke til
normative funksjonskrav uten særskilt QA. DOCX/XML-ankre er ikke
originale PDF-sidetall. At PDF-kildens SHA-256 stemmer med manifestet, er
ikke bevis på at Word-kopien inneholder nøyaktig samme ordlyd og tabellstruktur.
Dette krever visuell/manuell gjennomgang; uleselige eller tvetydige dokumenter
skal meldes fra til kilderepoets eier. Verken originale PDF-er, DOCX-er,
XSD-er, XPath-tester eller kilde-manifest blir endret av analysekommandoen.

I Qt: `Resultatvisninger → XPath` og fanen `Krav- og KDRS-review a8 →
Kravregister DOCX a9`. Åpne a9-JSON, velg Noark-versjon og filtrer
FEIL/WARNING/NOTE. Underfanen **Kildeavvik og manuell QA** viser også feil
som gjør at en hel kilde ble utelatt fra kravkartleggingen.

Faglig avgrensning: a9 er kildetranskripsjon og QA, **ikke** full normativ
kravdekning, godkjente statiske XML-kontroller, KDRS/Saxon-paritet,
resultatsamsvar eller depotgodkjenning.

## Krav–kontroll-kandidater – v0.2.1-a10

`app.noark5_requirement_coverage_v021_a10` sammenholder den lokale, uverifiserte
kravregistreringen fra a9.2 med faktisk DWM-kode/katalog og registrerer bare
**mulige tekniske koblinger**, aldri automatisk godkjent kravimplementasjon.
Arbeidsbeskrivelse, fem rapportfiler, eksakt PowerShell-kommando og GUI-plassering
står i [NOARK5-KRAV-KONTROLL-MATRISE-V021-A10.md](NOARK5-KRAV-KONTROLL-MATRISE-V021-A10.md).
Kilde-QA og Saxon/lxml-paritet forblir egne vurderinger; intet normativt
kildegrunnlag endres av a10.
