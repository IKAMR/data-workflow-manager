# N5 WF Man 19 – a19-fix5: flat mottaksmappe (2026-10-15)

## Må ikke misforstås i senere tråder

**Brukerens avklaring:** En mottaksmappe er kun en **flat** katalog:

`K:\arkiv-karantene-08\E-1505-2026-0004\`

Den er for nedlasting/oppbevaring av kryptert(e) leveranse(r), eventuell tilhørende mottaksdokumentasjon og senere flere uttrekk under samme mottaksnummer. **Ikke opprett `repository_operations`, `content`, `descriptive_metadata` eller andre undermapper under E-mappen.**

To **loggfiler** ligger direkte i denne flate E-mappen:

- `ingest.events.jsonl` (kanonisk append-only historikk)
- `depot-log.txt` (lesbar projeksjon)

Ved opprettelse logges valgfri valgt `info.xml`-kildesti og SHA-256, utførende bruker (hvis registrert), tidspunkt, eierkommune, mottaksnummer, valgt LABEL, profil, disk/gruppe og opprettet mottaksmappe. Hendelsen markerer `delivery_state=awaiting_download` – ingen fil er lastet ned, kontrollert eller mottatt av denne operasjonen. Innleveringen skal lastes ned **manuelt** senere, og nedlasting må få egen reell hendelse når det støttes. Ingen passord, arkivfiler eller `info.xml` kopieres av denne operasjonen.

**Separat arbeidsnivå:** Handlingen **Uttrekk** oppretter egen søskenmappe:

`K:\arkiv-karantene-08\2026-10-15_1505_019_E-1505-2026-0004\`

Denne uttrekksmappen får `content/sip`, `content/tar`, `descriptive_metadata`, `repository_operations` med `abstract`, `quarantine`, `utilities` (fra ekstern JSON-setup), og portabel `repository_operations/depot-log.txt` samt `ingest.events.jsonl`. Mottaks- og uttrekkslogg knyttes sammen med samme `receipt_number` og opprinnelige hendelses-ID-er. Uttrekksopprettelsen tilføyes også kanonisk JSONL og lesbar logg på mottaksnivå. Uttrekk er ikke det samme som nedlasting/utpakking; de logges ikke som fullført før egne operasjoner er implementert.

## Endringsomfang fix5 (installeres over a19-fix4)

- `app/grouped_ingest.py`: mottakets plan inneholder bare root; loggdata merkes `awaiting_download`.
- `app/ingest_operation_log.py`: lesbar mottakslogg skrives direkte i E-root og rekonstrueres fra tidligere JSONL ved behov; ingen `repository_operations` opprettes der. Gammel fix4-logg slettes ikke.
- `config/receiving_folder_profiles.json`: IKAMR-profilens generiske mottaksstruktur settes til tom liste, mottakslogg legges ved rot. Uttrekksprofilens separate mappetre beholdes.
- `gui/grouped_ingest_dialog.py`: riktig forhåndsvisning og bekreftelse med neste manuelle nedlastingssteg; feltene for uttrekk er merket som kun uttrekk.
- Relevante a19-tester oppdatert; egne regresjonstester for valgt `info.xml`, flat mottaksmappe og tidligere fix4-mottak.

## Verifisering og arbeidsregel

- 56/56 a19-fokustester bestått i isolert Python-miljø (ingen hoppet over her).
- Syntaks/ZIP-kontroll kjøres ved pakking. Full Windows `test.bat` og GUI er **ikke** kjørt her; bruker kjører disse.
- Dette er **én liten delta over a19-fix4**, uten gamle a18-filer, commit eller push. Brukeren committer og pusher selv.
- Historisk a19-fix4-dokumentasjon beskriver et tidligere feiloppsett. Denne fix5 er **gjeldende funksjonskontrakt**.
