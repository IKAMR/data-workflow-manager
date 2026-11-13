# Noark 5: versjonsidentifikasjon fra XSD (v0.1.14-a5)

## Fast referanse

Kildebiblioteket er **[IKAMR/digital-archive-workflow — docs/kilder/noark](https://github.com/IKAMR/digital-archive-workflow/tree/main/docs/kilder/noark)**. XSD-signaturene for Noark 5 v3.0, v3.1, v4.0 og v5.0 i `config/noark5/standards/noark5_xsd_signatures_v0114_a5.json` er transkribert fra `docs/kilder/noark/SOURCE-MANIFEST.json` i kilde-repoet (kildetre SHA `82bd59f23aafdc2386e317e5492941862c2bab9a`). Kontrollsummer er ikke beregnet om fra alle originale binærfiler i denne implementasjonen. Ved oppdatering må de verifiseres mot kilderepoet.

Dette er et lokalt, versjonert **identifikasjonsgrunnlag**. Det er ikke en kopi av spesifikasjonene og er ikke en erstatning for XSD-validering.

## Identifikasjon og kildeprioritet (a5-fix1)

1. Les `version` på rot-elementet `xs:schema` i uttrekkets faktiske XSD, særlig `arkivstruktur.xsd`, og kontroller at `targetNamespace` er en Noark 5-namespace. `version="5.0"` betyr **Noark 5 v5.0**.
2. Les `metadatakatalog.xsd` og øvrige tilgjengelige Noark-XSD-er. Ulike angitte versjoner gir **konflikt**, ikke et automatisk valg av nyeste versjon. Manglende eller uleselig medfølgende XSD gir en delvis verifisert identifikasjon.
3. Bruk SHA-256-registeret for eksakt identitet til en kjent filvariant, ikke som eneste kriterium for standardversjon. For eksempel har Arkade 5-forken `IKAMR/arkade5` XSD-er for 3.1, 4.0 og 5.0 som ikke alltid er byte-identiske med `digital-archive-workflow`.
4. Les versjons- og vedlikeholdsopplysninger i XSD-kommentarer som **historikk**. Tekst om *5.5.0 – Vedlikehold (2023-11-09)* i XSD-ens endringslogg gjør **ikke** standardversjonen til 5.5.0; det er fortsatt Noark 5 v5.0 når `xs:schema version="5.0"`.
5. Sammenlign med eksplisitt Noark-versjonsopplysning i `arkivuttrekk.xml`, men opplysningen er sekundær og kan være foreldet. ADDML-`version` er ikke Noark-versjon.
6. Sammenligninger mot standardverdilister for 3.1, 4.0 og 5.0 må merkes med **regelversjon**, og må ikke automatisk kalles regelbrudd ved ukjent eller annen uttrekksversjon.

**Kildereferanser:**
- [Noark-kildebibliotek](https://github.com/IKAMR/digital-archive-workflow/tree/main/docs/kilder/noark)
- [Arkade 5 – innebygde XSD-er](https://github.com/IKAMR/arkade5/tree/master/src/Arkivverket.Arkade.Core/ExternalModels/xsd/Noark5)
- [Arkade 5 – skjemavalg og fallback](https://github.com/IKAMR/arkade5/blob/master/src/Arkivverket.Arkade.Core/Base/Archives/Noark5XmlUnits.cs)

DWM endrer ikke utførte XPath-kontroller, historiske resultater, depotrapport eller original XML som følge av denne identifikasjonen. `additional_observed_values` forblir en **observasjon**. At en verdi mangler i et referanseregister er ikke alene et XSD-brudd eller et bevis på et bindende kravbrudd.

## Avgrensning

Dette er **versjonsidentifikasjon**, ikke en XSD-validitetstest eller en semantisk ekvivalenstest av lokale skjemaendringer. En ukjent SHA-256-filvariant med korrekt `version` identifiserer den oppgitte Noark-versjonen, men er ikke bekreftet byte-for-byte mot referansematerialet. Dokumenter med feil eller villedende `version` kan derfor ikke avklares sikkert uten en separat skjemasammenligning. Oppdatering av kilderegister, fulltekst/PDF/Word-mapping og full XSD-validering behandles separat.

## Videreført i v0.1.14-a6

Feltvise XSD-restriksjoner og historiske sammenligninger vises **gjeldende først og deretter bakover** (for v5.0: 5.0 → 4.0 → 3.1). Data er avgrensede utdrag fra `metadatakatalog.xsd` for M300, M082, M500 og M502, ikke en erstatning for samlet XML/XSD-validering eller full standardtekst. Se `config/noark5/standards/noark5_xsd_field_constraints_v0114_a6.json` og `docs/NOARK5-CANONICAL-RESULTS-AND-KNOWLEDGE-ROADMAP.md`.

Lokal XSD-variantregistrering skjer etter uttrykkelig knappetrykk i jobbens Work, med SHA-256 som innholdsidentitet og UUID for evidenspost/observasjoner. Ingen eksport eller sentral database i a6.
