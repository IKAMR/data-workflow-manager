# A220: store eksterne evidensfiler

A220 analyserer bare valgte filer i Work. Den lagrer kildefilens Work-relative
sti, opprinnelige byteantall og SHA-256 i `noark5.external-analysis.v1`.
Originalfilen endres ikke. Arkade-status gjengis som kildetekst; Siegfried er
formatidentifikasjon. Teknisk validering og depotgodkjenning settes ikke.

## Ressursgrenser

| Kategori | Grense | Begrunnelse |
| --- | ---: | --- |
| Native Siegfried JSON og andre strømmeleste JSON-kandidater | 512 MiB kilde | `files` leses én post av gangen; bare antall og formataggregater beholdes. Ukjent struktur forblir ufortolket. |
| Normalisert Arkade JSON | 512 MiB kilde | Filer over 48 MiB leses som JSON-hendelser. Test- og resultatlister, `source_raw` og `result_set_tree` lastes ikke som hele objekter. |
| Normalisert Arkade PRONOM JSON, DWM Siegfried-statistikk og andre filtyper | 48 MiB kilde | Disse JSON-formatene dekodes fortsatt som ett dokument; andre filtyper er ufortolket. |
| `canonical-results.json` som referanse | 100 000 000 byte | Egen grense for kanonisk input. |
| Generert `canonical-external-analysis.json` | 128 MiB | Kontrolleres før atomisk publisering og ved senere innlasting i A230, kontrollmatrisen og QA-grunnlaget. |
| Én JSON-post i native Siegfried | 2 MiB UTF-8 | Hindrer at én post opptar ubegrenset minne. |
| Ett Arkade-teksttoken i strømleseren | 8 MiB rå UTF-8 | Kontrolleres under SHA-256-lesingen før JSON-parseren får feltet. |
| Ett fanget Arkade-felt / én projisert testposts funn | 2 MiB / 64 MiB | Rå duplikatfelter beholdes i kilden; avledet analyse har endelige minnegrenser. |
| Én Arkade-testpost i eldre helfilsti / PRONOM-rad | 2 MiB UTF-8 | Gjelder filer som fortsatt dekodes som ett dokument. |
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

En egen A210–A230-test med **25 000 Arkade-resultatposter og kilde på mer enn
95 287 457 byte** brukte 39 564 KiB som høyeste prosessminne i den samme
Linux-målingen. Den kontrollerer kilde-SHA, byteantall, rapportert status,
resultattelling, atomisk A220-publisering, A230, kontrollmatrisens lasting og
QA-leserens funn. A260s rapportgrunnlag er i tillegg testet med en kilde over
samme størrelse. Den valgfrie KS-innholdsrapporten leser store Arkade-kilder
hendelsesbasert og viser kildebelagte arkivdeler.

Siegfried-testen kontrollerer også at Python-allokeringer under analysen er
under 20 MiB. Dette er testmålinger, ikke et løfte om samme minnebruk på alle
plattformer eller for alle JSON-former. Filer på høyst 48 MiB bruker fortsatt
den tidligere helfilstien for Arkade; målingen på 286 212 KiB beskriver den.
Den avledede v1-analysen inneholder fortsatt alle rapporterte testposter og
funn som adapteren tar med. Store *avledede* analyser kan derfor bruke mer
minne ved JSON-serialisering og i QA-lesere; 128 MiB-utgrensen er en endelig
ressurssperre, ikke en påstand om konstant minnebruk i alle nedstrøms visninger.
Større grenser krever egne målinger med representative data.

Grensene gjelder teknisk ressursbruk. De gir ikke normativ Noark-dekning eller
faglig godkjenning av ekstern evidens.
