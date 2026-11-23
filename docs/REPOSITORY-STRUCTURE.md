# Repositorystruktur

## Root-prinsipp

Repo-root skal bare inneholde filer og mapper med en tydelig toppnivårolle: entrypoint, installasjon, oppstart, testing, avhengigheter, lisens, toppnivådokumentasjon og etablerte hovedmapper.

Generell applikasjonskode som ikke er GUI og ikke er Noark 5-spesifikk legges under `app/`. Generell konfigurasjon og policy legges under `config/`.

`noark5_workflow/` skal kun inneholde funksjonalitet og data som er spesifikt knyttet til Noark 5-domenet.

## Dokumentasjon – fra v0.2.6-a1

- `docs/README.md` er inngangen til teknisk dokumentasjon. Brukerrettet hjelp ligger i GitHub Wiki.
- `docs/`-roten er reservert for et begrenset antall varige kontrakter, oversikter og `RELEASE-vX.Y.Z.md`-notater.
- Fagstoff hører hjemme i etablerte undermapper som `architecture/`, `development/`, `reference/`, `workflow/`, `integrations/` og `storage/`.
- Tidligere alpha- og deltafiler er bevart i `docs/history/`, men nye alpha-trinn skal oppdatere kanoniske dokumenter og **ikke** lage nye `V026-A*.md`, `DWM-A*.md` eller lignende engangsdokumenter.
- Enkelte eldre filer ligger fortsatt direkte i `docs/` fordi tester eller kode bruker de gamle stiene. De er eksplisitte kompatibilitetsunntak, ikke en åpning for nye rotfiler.
- `py tools/docs_layout.py --check` kjøres under utvikling. Sjekken inngår også i automatisert testing slik at fremtidig dokumentasjonsrot oppdages før commit.

## Nåværende opprydding

- `settings_portable.py` flyttes fra root til `app/settings_portable.py`.
- `config_example.json` flyttes fra root til `config/config_example.json`.
- generell operasjonsmetadata etableres i `config/operations.json`.

`settings.py` og `version.py` beholdes foreløpig i root fordi de er sentrale importpunkter. Eventuell flytting gjøres senere som en samlet refaktorering.
