# v0.1.15-a5 – dokumentert referansenivå og Siegfried-identifikasjon

## Implementert

- `canonical-context.json` beholder eksisterende `link_status` for bakoverkompatibilitet, men får to nye eksplisitte indikatorer på hver faglige vurdering: `reference_status` og `evidence_verification` (`not_verified`). `human_verification` er `not_recorded`. En registrert `test_id`, selv ved samme `metadata_id`, er **aldri automatisk bevis for at XML-feltet er faglig eller teknisk undersøkt**. Eksempel: M300-hendelsen med `kdrs.c02` er kun en registrert test-ID-referanse.
- Den valgte eksterne evidensen undersøkes kun når den er en JSON-fil med gjenkjennelig Siegfried-signatur (`siegfried` og `files[*].matches`). Adapteren registrerer antall filer, treff og PRONOM-identifikatorer som **formatidentifikasjon**, aldri som resultat av en bestått Noark-/integritetskontroll.
- Andre filer, herunder Arkade 5 JSON/XML uten dokumentert maskinlesbart skjema, registreres fortsatt som `external_opaque` med SHA-256 og `not_parsed`. Ingen feilaktig oversettelse fra tilfeldig tekst eller ukjente statusfelt.
- GUI-teksten viser antallet **ikke-verifiserte** faglige vurderinger separat fra antallet manglende test-ID-referanser. Vurderingsfilen `experience_assessments.json` foreslås i filvelgeren når den finnes på standard Work-plassering.
- Eksisterende `canonical-results.json`, historiske råresultater og Source beholdes uendret. Brukeren velger kildene eksplisitt og bekrefter skriving til separat kontekstindeks.

## Begrensninger / neste arbeid

- Siegfried-strukturen som behandles er den native JSON-varianten. Dersom DWM har lagret CSV, YAML eller Arkade-avledet resultat, kreves dokumentert eksempel og egen adapter. Formatidentifikasjon innebærer ikke at hver eneste fil er identifisert tilfredsstillende.
- Arkade 5 Noark 5 og Arkade 5 PRONOM **tolkes ennå ikke til individuelle testobservasjoner**; en korrekt adapter må baseres på faktiske eksempelrapporter fra brukerens Work og kildeformat/versjon. Det er ikke faglig forsvarlig å gjette feltnavn og produsere falske «bestått».
- Kontrollplan/dekningsmatrise, sann XML-treffverifisering for M-ID, sammenkobling til rapportmotor og AIP er videre arbeid. Se [NOARK5-CONTROL-TO-PRESERVATION-ROADMAP.md](NOARK5-CONTROL-TO-PRESERVATION-ROADMAP.md) og [DWM-BACKLOG-CONSOLIDATED.md](DWM-BACKLOG-CONSOLIDATED.md).

## Test

`py -m unittest tests.test_v0115_a5_external_links` og ordinær `test.bat`. I GUI: **Rapport → Kanoniske resultatdata… → Koble vurderinger / ekstern evidens…**. Etter valget `experience_assessments.json` skal oppsummeringen skille «Vurderinger uten test-ID-kobling: 0» fra «Faglig ikke-verifiserte vurderinger: 1». For gjenkjent Siegfried JSON oppgis antall identifiserte JSON-kilder; ingen teststatus eller godkjenning utledes.

## Oppdagelse av eksterne kandidater

Ny handling «Finn ekstern evidens» lister inntil 150 kandidater i kjente undermapper (`external_evidence`, `external_runs`, `arkade5_v2.13.1`), med begrenset dybde og uten å følge symbolske lenker. Listen er rådgivende: kildene må fremdeles velges eksplisitt via «Koble vurderinger / ekstern evidens…». Filnavn alene brukes ikke til å utlede gyldige testresultater.
