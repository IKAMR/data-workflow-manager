# Runtime environment

Fra v0.1.4-a2 registrerer Data Workflow Manager et generisk miljøsnapshot én gang per RUN.

Snapshotet er formatnøytralt og skal kunne brukes av alle profiler og senere worker/server-kjøring. Det omfatter blant annet:

- operativsystem og plattform
- maskinarkitektur
- Python-versjon og implementation
- logiske og fysiske CPU-er
- totalt og tilgjengelig fysisk minne
- host-identitet på maskinnivå

Miljøet lagres i `run.started`-eventet og kopieres til `artifact_manifest.json` for artefakter som produseres i samme RUN.

Dette etablerer grunnlaget for senere:

- benchmark mellom klienter/workere
- adaptiv I/O-strategi (`memory`, `streaming`, `disk`)
- adaptivt antall workers
- sporbarhet fra resultat tilbake til kjøringsmiljø

Miljøsnapshotet skal beskrive kjøringsmiljøet, ikke brukerens faglige profil eller Noark 5-spesifikke metadata.
