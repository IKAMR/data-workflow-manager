# A17 – strømmende XPath-kontroller for store Noark 5-uttrekk

Status: Utviklingsalpha, **ikke godkjent som fullstendig regresjonsmotor**. Basert på `dev-0.2.7-alpha` a16.

## Årsak

På 1502_024 feilet 48 av 60 tester ved `etree.parse(arkivstruktur.xml)` med `OSError: failed to load external entity`. Testene C01/C02 lyktes fordi de allerede bruker filbasert `iterparse`. A16 behandlet manglende `values` og bevarte diagnostikken, men rettet ikke XML-innlesingen.

## Endring

- `a17_xpath_stream.py` installeres kun i isolert XPath-worker etter a13-implementasjonen.
- For `arkivstruktur.xml` på minst 512 MiB: strømmende skanning av telle-, gruppe-, dato-, års- og numeriske kontroller, med aggregater per arkivdel der støttet.
- XML forblir på Source; ingen gigantiske XML-trær lagres i RAM, og Source endres ikke.
- C01/C02 beholdes på a13s allerede validerte filbaserte `iterparse`-bane.
- Hver støttet kontroll returnerer sitt originale `values`-format. Kontroller som krever en spesialalgoritme eller har XPath-syntaks uten verifisert strømmesemantikk, får **teknisk `error` med `UnsupportedStreamMetric`**, aldri falsk OK.
- a16-regresjonsrapport, `index.json`, individuelle resultater og feildiagnostikk fortsetter å være autoritative.

## Begrensninger – må løses før full A190-friskmelding

Dette incrementet er et konservativt grunnlag, ikke full dekning av KDRS-katalogen. U01 benytter a12-strømmemotoren, I02 beregner datointervaller strømmende, og de viktigste klasse-/arkivdelvisningene har egne aggregater. Samtlige av disse trenger likevel sammenligning med det originale resultatformatet på representative testuttrekk, og alle kataloguttrykk må verifiseres individuelt. `UnsupportedStreamMetric` er **ikke** en feil i arkivuttrekket og må ikke telles som validert kontroll.

En del kataloguttrykk med utsatt evaluering av foreldrebetingelser er eksplisitt støttet. Støtte for andre mønstre skal først legges til etter en mot-`lxml`-regresjonstest. Sluttstatus for A190 bør derfor fortsatt være `Feil` inntil alle tekniske tester faktisk kan behandles.

## Verifikasjon

1. `py -m unittest discover -s tests -p "test_v027_a17*.py" -v`
2. `test.bat` (hele testpakken, inkludert testresultatene under `docs/test-results/`).
3. På et mindre uttrekk: sammenlign **hele JSON-resultatet per test** mellom tradisjonell XPath og strømmemotoren.
4. På 1502_024: følg memory, `performance-diagnostics.json`, `index.json` og `legacy-regression-comparison.json`.
5. Ikke nullstill JOB-001. Gjenopptakelse skal fortsatt starte fra A190, 8/17, etter godkjent test.

## Neste beslutning

Før full A190 kan anses løst må vi dokumentere hvilke kataloguttrykk som er ekvivalente, validere U01/U02, øvrige spesialhandlere og komplekse XPath-uttrykk mot originale resultater og eventuelt gjenbruke de allerede genererte A180-resultatene gjennom en identitets- og provenienssjekk. Langsiktig anbefales en generell SQLite-basert objektindeks for søk og innsyn, men ikke som erstatning for råevidens.
