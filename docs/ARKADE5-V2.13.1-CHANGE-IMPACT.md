
# Arkade 5 v2.13.1 – konsekvens for Noark 5-integrasjonen

## Verifisert grunnlag

- Arkade 5 v2.13.0 baseline: `40a32ee0ae84ddf44d1f3c35f1860567ca262733`
- Arkade 5 v2.13.1 release: `b27136ede491d3ec8b9e0ec9973ba455a0febbdf`
- Verifisert: 2026-09-23

## Semantisk katalog

Ingen av de 54 Noark 5-testimplementasjonene er endret mellom v2.13.0 og
v2.13.1. Derfor beholdes den allerede kildekodeverifiserte v2.13.0-katalogen,
mappingen og dekningspolicyen som semantisk baseline.

v2.13.1 registreres som et eksplisitt release-delta. Dette unngår å omskrive
54 uendrede testdefinisjoner bare fordi validatorversjonen er oppdatert.

## ARKADE-826

v2.13.1 retter dokumentkatalogdeteksjon og relativ dokumentsti for TAR/DIAS.

Runtime-resultat kan endres for:

- N5.28
- N5.30
- N5.32
- N5.33
- N5.64

Undersøkt og ikke påvirket av denne endringen:

- N5.29
- N5.34

## Mappeinput

ARKADE-826 gjelder TAR/DIAS-løpet. Den forklarer ikke alene de observerte
Windows-feilene «enhet som ikke finnes» ved test av utpakket content-mappe fra
USB-disk.

## Versjonert evidens

DWM beholder Arkade `source_version` per import.

- v2.13.0 er kjent tidligere versjon.
- v2.13.1 er gjeldende versjon.
- rapporter fra begge versjoner kan importeres og sammenlignes.
- resultatene slås ikke sammen som om de kom fra samme validatorversjon.
