# Lokal Noark 5-erfaringsbase (a7)

**Status:** Implementert som første avgrensede erfaringsflyt for M300. Noark 5/XSD-krav og rapporter påvirkes ikke av menneskelige vurderinger.

- Standardfrø: `config/noark5/experience/known_cases_v1.json` (medfølger DWM, kilde til forslag – IKKE en konklusjon om feil).
- Lokale gjenbruksmerknader (valgfritt): `%LOCALAPPDATA%/DataWorkflowManager/noark5/experience/local_practice.json` på Windows, tilsvarende hjemmekatalog på andre plattformer. Endres kun hvis kontrolløren velger gjenbruk.
- Jobbspesifikke manuelle vurderinger: `<Job-Work>/noark5_evidence/experience_assessments.json` med hendelses-ID, tidspunkt, test-ID, metadata-ID, observert verdi/antall, beslutning og merknad. **Tidligere hendelser beholdes ved ny vurdering**.
- `Erfaringsvurdering…` i Resultatvisninger → Standardverdikontroller, når aktuell metadata-ID og bekreftet Noark-versjon er tilgjengelig.

M300-funnet `Elektroniskarkiv` i Noark 5 v5.0 gir et forslag til merknad basert på `minLength=1` uten XSD-enumeration. Semantisk ekvivalens er **ikke** forhåndsgodkjent. Kontrolløren kan velge videre gjennomgang, vurdert som ekvivalent eller ikke akseptert, og lagrer selv en ny hendelse. Ved uavklart versjon, feil felt eller annet observert verdinavn gis ikke automatisk forslag.

## Avgrensninger

- Ingen sentral database, GitHub-synkronisering, kopiering av XML eller dokumentbinærer.
- Erfaringsregister og lokale overstyringer er *ikke* normative XSD-er, og skal aldri automatisk endre teststatus eller opprinnelig depotrapport.
- Ingen automatisk innhenting av gamle vurderinger fra andre uttrekk; gjenbruk gjelder kun valgfri lokal merknadstekst for bekreftede identiske tilfeller.
- Ingen automatisk «godkjenning» eller skrivemåtenormalisering i kilde-XML.
- For å gi en samlet grunnlagsmodell, sammenligne uttrekk og lage statistikk, se `docs/NOARK5-CANONICAL-RESULTS-AND-KNOWLEDGE-ROADMAP.md`. Dette er videre plan, ikke implementert av a7.
