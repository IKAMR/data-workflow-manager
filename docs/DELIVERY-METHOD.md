# Leveransemetodikk for alpha-inkrementer

Denne filen fastsetter navngivingen for AI-leverte arbeidsdelta i prosjektet.

## Nummerering av leveranser innen samme alpha

Den interne applikasjonsversjonen følger alpha-inkrementet og endres ikke for hver arbeidsleveranse.

Eksempel:

- `version.py`: `0.1.3-a11`
- første leveranse i arbeidet med a11: `v0.1.3-a11.1`
- neste leveranse: `v0.1.3-a11.2`
- deretter: `v0.1.3-a11.3`

Undernummeret `.1`, `.2`, `.3` osv. er leveransenummer innen samme alpha og skal ikke brukes som applikasjonsversjon i `version.py`.

## Obligatorisk navngiving

Samme leveranseidentifikator skal brukes konsekvent:

- i teksten på nedlastingslenken i samtalen
- i selve ZIP-filnavnet
- ved eventuell omtale av pakken i samtalen

Eksempel:

`v0.1.3-a11.2`

og ZIP:

`v0.1.3-a11.2.zip`

Ikke bruk alternative navn som `updated`, `fix`, `fix2`, `new`, `delta-next` eller tilsvarende i stedet for leveransenummeret.

## Commit

Når alpha-inkrementet er ferdig testet og godkjent, committes det som selve alphaen, for eksempel `v0.1.3 a11`. De midlertidige leveransenummerne `.1`, `.2`, `.3` er ikke egne applikasjonsversjoner eller separate alpha-commits.
