# Adaptiv ressursstrategi

Fra v0.1.4-a3 har Data Workflow Manager et generisk beslutningslag for ressursbruk.

Støttede strategier:

- `auto` – standard. Velger strategi ut fra filstørrelse, tilgjengelig RAM, lagringstype og forventet gjenbruk.
- `memory` – les hele input til RAM før behandling.
- `streaming` – les kilden sekvensielt/chunked og hold minnebruken begrenset.
- `disk` – arbeid direkte mot filen uten å lage en separat RAM-buffer.

## Auto

`auto` er konservativ for store tree-baserte XML-arbeidsmengder:

- svært store filer velges som `streaming`
- hvis estimert tree-minnebruk blir for stor i forhold til ledig RAM, velges `streaming`
- en moderat fil på nettverkslagring kan velges som `memory` når samme kilde skal gjenbrukes og det finnes god RAM-margin
- moderate lokale filer kan behandles direkte som `disk`

XML tree-behandling beregnes konservativt med høyere minneoverhead enn selve filstørrelsen.

## Worker-grunnlag

Beslutningen beregner også `recommended_workers` basert på:

- logiske CPU-er
- tilgjengelig RAM
- estimert minnebruk per worker

v0.1.4-a3 bruker **ikke** dette til å starte parallelle workers. Feltet er beslutningsgrunnlaget for neste trinn, slik at parallellisering ikke baseres på CPU-antall alene.

## Logging

Operasjoner som bruker ressursstrategien skal logge valgt strategi og begrunnelse, for eksempel:

```text
RESSURSSTRATEGI: streaming | storage=network | file=4429332519 |
available_ram=... | estimated_memory=... | workers=1 |
stor fil overstiger terskel
```

Beslutningen lagres også i det strukturerte resultatet slik at benchmark og senere klient/server-sammenligning kan forklare hvordan dataene ble behandlet.

## Første integrasjon

v0.1.4-a3 integrerer strategien i XML/XSD-valideringen.

Den tidligere streamingveien for svært store XML-filer beholdes. Adaptive valg skal aldri føre til at en stor fil ukritisk lastes som komplett XML-tree bare fordi maskinen har mye RAM.
