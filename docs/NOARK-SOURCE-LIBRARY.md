# Noark-kilder: Digital Archive Workflow

**DWM sin faste referansesamling for Noark 3, 4 og 5 er**
[IKAMR/digital-archive-workflow / docs/kilder/noark](https://github.com/IKAMR/digital-archive-workflow/tree/main/docs/kilder/noark).
Samlingen forvaltes i et separat repo for å kunne brukes av flere verktøy og beholdes
uavhengig av endringer i eksterne nettsteder. Originale kildefiler kopieres ikke inn i DWM.

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
