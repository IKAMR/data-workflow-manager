# v0.1.15-a4: kanonisk kontekst og samlet utviklingsplan

## Implementert i a4

`noark5_workflow.analysis.canonical_context_v0115_a4.build_context()` kobler **eksplisitt valgte** faglige vurderinger og/eller eksterne evidensfiler i samme Work til eksisterende `noark5_evidence/canonical-results.json`. Det bevarer hele a1–a3-kontrakten og lager separat:

`<valgt Work>/noark5_evidence/canonical-context.json`

Koblingen har kanonisk filreferanse og SHA-256, Work-jobb-UUID, egne kildereferanser/filhash, separate vurderingshendelser med vurderingsstatus, og tydelige koblingsnivåer: test-ID alene, test + metadata-ID, eller ikke koblet. Vurderingsfilen `experience_assessments.json` er eksplisitt valgt. Eksterne filer er foreløpig **opake filreferanser**, ikke normaliserte kontrollobservasjoner eller bevis på bestått kontroll. Alle filer ligger innenfor valgt jobb-Work. Source leses ikke og endres aldri.

I `Rapport → Kanoniske resultatdata…` finnes ny handling «Koble vurderinger / ekstern evidens…». Den krever eksisterende canonical-results.json, eksplisitte filvalg og bekreftelse. Første opprettelse av den opprinnelige kanoniske indeksen er uendret. Begge indeksene kan leses sammen ved senere rapportutvikling. Oppdateres hovedindeksen, må kontekstindeksen bygges på nytt (SHA-256 av hovedindeks er referansen).

## Avgrensninger / neste steg

- Ingen automatisk parsing av Arkade 5-rapporter, Siegfried-utdata eller andre ukjente filformater i a4. Resultatbank v2 som a1 støtter er fortsatt egen kilde med sitt etablerte format.
- Ingen automatisk utfylling av `metadata_id`, `xpath`, `line` eller `system_id` uten dokumentert kildetreff. M300-vurdering koblet via `kdrs.c02` er bare en **test-ID-kobling**, ikke bevis for at den konkrete XML-forekomsten ligger i kanonisk snapshot.
- Ingen integrasjon med fullstendig rapportmotor, kontrollplan, kvalitetsrapport, aksept, journalføring eller AIP ennå.
- Ingen testresultater eller vurderingshistorikk omskrives, og ingen automatisk godkjenning utledes.

## Varig utviklingsplan

- [NOARK5-CONTROL-TO-PRESERVATION-ROADMAP.md](NOARK5-CONTROL-TO-PRESERVATION-ROADMAP.md) — ende-til-ende-prosess og versjonsplan.
- [DWM-BACKLOG-CONSOLIDATED.md](DWM-BACKLOG-CONSOLIDATED.md) — historiske og nye tekniske/faglige utviklingspunkter med implementasjonsgrenser.
- [NOARK5-CANONICAL-RESULTS-MODEL.md](NOARK5-CANONICAL-RESULTS-MODEL.md) — eksisterende a1-resultatmodell (berøres ikke av a4).
- [Digital Archive Workflow, Noark-kilder](https://github.com/IKAMR/digital-archive-workflow/tree/main/docs/kilder/noark) — autoritativt lokalt lagret referansebibliotek for spesifikasjoner og skjemaer.

De nye planene er konsolidert fra Word-vedlegget «N5 WF Man 24» og samtalen «N5 WF Man 25». De er ikke alle implementert i a4.
