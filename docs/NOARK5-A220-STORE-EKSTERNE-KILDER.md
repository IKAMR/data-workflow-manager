# A220: store eksterne evidensfiler

A220 analyserer bare valgte filer i Work. Den lagrer kildefilens Work-relative
sti, opprinnelige byteantall og SHA-256 i `noark5.external-analysis.v1`.
Originalfilen endres ikke. Arkade-status gjengis som kildetekst; Siegfried er
formatidentifikasjon. Teknisk validering og depotgodkjenning settes ikke.

## Ressursgrenser

| Kategori | Grense | Begrunnelse |
| --- | ---: | --- |
| Native Siegfried JSON og andre strømmeleste JSON-kandidater | 512 MiB kilde | `files` leses én post av gangen; bare antall og formataggregater beholdes. Ukjent struktur forblir ufortolket. |
| Normalisert Arkade/PRONOM JSON, DWM Siegfried-statistikk og andre filtyper | 48 MiB kilde | Midlertidig grense mens normalisert JSON fortsatt dekodes som ett dokument; andre filtyper er ufortolket. |
| `canonical-results.json` som referanse | 100 000 000 byte | Egen grense for kanonisk input. |
| Generert `canonical-external-analysis.json` | 64 MiB | Kontrolleres før atomisk publisering og ved senere innlasting i kontrollmatrisen. |
| Én JSON-post i native Siegfried | 2 MiB UTF-8 | Hindrer at én post opptar ubegrenset minne. |
| Én Arkade-testpost eller PRONOM-rad | 2 MiB UTF-8 | Hindrer svært store enkeltposter i normaliserte kilder. |
| Siegfried filposter / matcher / format-ID-er | 100 000 / 1 000 000 / 100 000 | Hindrer ubegrenset akkumulering. |
| Arkade/PRONOM-poster / totalt / valgte kilder | 100 000 / 200 000 / 100 | Hindrer ubegrenset resultatvolum. |

Filstørrelsen kan være nøyaktig lik grensen. Én byte over grensen avvises.
Ved kapasitetsfeil viser operasjonsmeldingen hvilken Work-relativ kilde og
hvilken grense som er nådd. Ingen ny analyse publiseres. Den eksisterende
analysen, hvis en finnes fra en tidligere kjøring, beholdes til en vellykket
atomisk erstatning. Velg en mindre, **fullstendig** kilde eller reduser antall
valgte kilder; ikke klipp bort poster og bruk den forkortede filen som fasit.

## Kontrollert ressursbruk

Målt på Linux med Python 3.12, 19. november 2026, via `/usr/bin/time -f %M`
for de automatiske storfiltestene:

| Representativ test | Kildestørrelse | Høyeste prosessminne |
| --- | ---: | ---: |
| 90 000 native Siegfried-filposter, over 30 MB | over 30 MB | 60 600 KiB |
| 100 000 normaliserte Arkade-poster, over 30 MB | over 30 MB | 286 212 KiB |
| 100 000 normaliserte PRONOM-rader, over 30 MB | over 30 MB | 180 568 KiB |

Siegfried-testen kontrollerer også at Python-allokeringer under analysen er
under 20 MiB. Dette er testmålinger, ikke et løfte om samme minnebruk på alle
plattformer eller for alle JSON-former. Særlig normalisert Arkade bruker
betydelig mer minne enn kildefilens størrelse; 48 MiB er derfor en konservativ
midlertidig grense. En større grense krever måling med representative data.

Grensene gjelder teknisk ressursbruk. De gir ikke normativ Noark-dekning eller
faglig godkjenning av ekstern evidens.
