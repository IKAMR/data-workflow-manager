# Delta-preflight

Denne kontrollen er obligatorisk før en AI-levert ZIP/delta sendes til bruker.

Bakgrunnen er en gjentatt feiltype: produksjonskoden flyttes til et nytt runtime-lag
eller en etablert kodelinje omformateres, mens eldre regresjonstester fortsatt låser
forrige modulnavn eller en eksakt implementasjonsstreng. Resultatet blir testfeil som
kunne vært oppdaget før levering.

## Obligatorisk regel

Et delta er **ikke leveringsklart** før følgende er kontrollert:

1. Identifiser alle produksjonsfiler som er nye eller endret siden leveransens base.
2. Finn eksisterende tester som refererer til disse filene, klassene, funksjonene eller
   runtime-kjeden.
3. Kontroller eksplisitt `main.py` mot alle tester som låser aktiv `run_gui`-runtime.
4. Kontroller tester som bruker eksakte `assertIn(...)`-strenger mot endrede filer.
5. Oppdater foreldede tester i samme delta når kontrakten er bevart, men
   implementasjonen har flyttet seg.
6. Kjør berørte tester før pakken bygges.
7. Når miljøet tillater det, kjør full testsuite før pakken bygges.
8. Lever ikke delta dersom preflight har en `[BLOCK]`.

Dette supplerer reglene i `docs/DEVELOPMENT.md`; det erstatter dem ikke.

## Verktøy

Fra repository root:

```text
py tools\delta_preflight.py --base HEAD
```

Dette:

- finner endrede og nye filer i working tree
- finner berørte eksisterende tester
- blokkerer foreldede forventninger om aktiv runtime
- blokkerer kjente eksakte strengkontrakter som ikke lenger finnes i endret fil
- kjører berørte tester

For full kontroll:

```text
py tools\delta_preflight.py --base HEAD --full
```

Kun statisk skann:

```text
py tools\delta_preflight.py --base HEAD --scan-only
```

## Leveransekrav for AI

Før AI lager eller sender en ZIP skal resultatet kunne oppsummeres som:

```text
DELTA PREFLIGHT: OK
- runtime-kjede kontrollert
- eksakte testkontrakter kontrollert
- berørte tester kontrollert/kjørt
- full suite kjørt når miljøet tillater det
```

Hvis AI ikke har et komplett repository-checkout der testene kan kjøres, skal dette
sies eksplisitt. I så fall er statisk gjennomgang av alle berørte tester minimumskrav,
og pakken skal ikke omtales som fulltestet.

## Særlig runtime-lag

Ved overgang fra for eksempel `persistent_app_a33` til `persistent_app_a34` er det
ikke nok å legge til en ny test som forventer `a34`. Alle eldre tester som inneholder
forventninger til aktiv `run_gui` må gjennomgås samtidig.

Historiske runtime-importer med alias kan beholdes for kjedekontrakt. Det er den
u-aliasede aktive `run_gui`-forventningen som må samsvare med `main.py`.

## Særlig GUI-kode

Ved endring av felles GUI-filer som `gui/workflow_panel.py` skal tester som leser
filen som tekst alltid skannes. Om en eksisterende test med vilje låser en eksakt
streng, skal enten:

- koden bevare den kompatible formen når det ikke koster noe, eller
- testen endres til en semantisk kontrakt i samme delta.

Brukeren skal ikke måtte oppdage samme type testbrudd etter hver leveranse.
