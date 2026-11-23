# Loggformater i Setup

Fra z18.17 kan brukeren velge dagens fire output-formater direkte i Setup:

- tekstlig kjørelogg
- PREMIS
- JSON
- CSV

Dette valget styrer `enabled_log_sinks`.

Den generiske `*.events.jsonl`-loggen er ikke et valgbart format i Setup. Den er den
obligatoriske interne sannhetskilden og skal alltid produseres for en kjøring.

JSON og CSV er derfor ikke alternative sannhetskilder; de er formatteringer over samme
generiske hendelsesgrunnlag på lik linje med tekst og PREMIS.

Neste praktiske test skal aktivere alle fire formatteringene og kontrollere at filene
som faktisk produseres kan knyttes til samme `run_id`.
