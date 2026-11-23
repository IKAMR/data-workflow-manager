# Windows-stier: obligatorisk utviklings- og testregel

Denne regelen gjelder alle DWM-endringer som leser, lagrer, returnerer eller sammenligner fil- og mappestier. Windows er prosjektets primære testplattform. Regelen er generell, ikke knyttet til en bestemt alpha, og skal følges før nye deltaer leveres.

## Filidentitet er ikke tekstlikhet

En og samme fil eller mappe kan være representert med ulike strenger, blant annet:

- langt brukernavn (`C:\Users\eksempel.bruker\...`) mot DOS 8.3-kortnavn (`C:\Users\EKSEMP~1\...`)
- forskjellig bokstavstørrelse (`C:\Data` mot `c:\data`)
- `.`/`..`, symbolske lenker, junctions eller andre aliaser
- relative mot absolutte stier, og forskjellige skilletegn
- mapped drive mot UNC-sti (kan vise til samme ressurs, men ikke uten videre påvises med strengnormalisering)

**Det er forbudt å bruke `assertEqual(str(path_a), str(path_b))`, `Path(a) == Path(b)` eller tekstlig `resolve()`-likhet som bevis for at to eksisterende Windows-filer er ulike eller identiske.** `Path`-likhet er leksikalsk og kan ikke alene håndtere 8.3-aliaser.

## Velg sammenligningsmetode etter kontrakten

1. **Begge stier peker til eksisterende filer/mapper, og det er identitet som skal kontrolleres:** Bruk `Path.samefile(other)` (eller `os.path.samefile`) og håndter `OSError` når filen forsvinner eller ikke kan undersøkes.
2. **Stier kan mangle, og testen gjelder ønsket *plassering* snarere enn identitet:** Lag eksplisitt en forventet sti ut fra samme autoritative rot og test forelder, filnavn og struktur hver for seg. `Path.resolve(strict=False)` kan brukes for syntaktisk opprydding, men må **ikke** regnes som full identitetskontroll på Windows; 8.3-/UNC-aliaser kan bestå.
3. **Den faktiske strengrepresentasjonen er kontrakten** (f.eks. en bestemt JSON-verdi, eksportformat eller synlig tekst): Test strengen direkte, og dokumenter hvorfor skrivemåten er viktig. Ikke bruk `samefile()` når eksakt serialisering er det som skal testes.
4. **Kilder på ulike Windows-volumer eller diskbokstaver:** Ikke anta at likt relativt navn betyr samme fil. Ikke omskriv Source-stier for at tester skal passere.

Eksempel for **eksisterende** fil:

```python
from pathlib import Path

saved_path = Path(result_path)
expected_path = assessment_path(work)
assert saved_path.is_file()
assert expected_path.is_file()
assert saved_path.samefile(expected_path)
```

## Obligatoriske regresjonskontroller

- Nye eller endrede tester for Windows-filbaner skal minst vurdere lange navn, 8.3-kortnavn, store/små bokstaver og `TemporaryDirectory` under brukerprofilen.
- Der funksjonen skal tåle ulike aliaser til **samme eksisterende ressurs**, test filidentitet fremfor rå strenglikhet.
- Test separat når en av stiene ikke finnes; `samefile()` skal ikke brukes ukritisk.
- Tester må ikke anta at `tempfile` returnerer samme skrivemåte som Windows API, PySide6, `Path.resolve()` eller andre bibliotek.
- Unngå hardkodede brukernavn, diskbokstaver og tempbaner. Bruk testens egne midlertidige kataloger.
- Før en delta leveres, sjekk eksisterende tester for `assertEqual(...path...)`, `str(Path(...))`-sammenligninger og andre stiantakelser. Rett slike tester samtidig som relevant kode; ikke vent på at brukeren finner feilen via `test.bat`.
- Full `test.bat` på Windows er endelig verifikasjon. Dersom utviklingsmiljøet ikke er Windows, oppgi begrensningen og foreta statisk gjennomgang samt målrettede tester.

## Konkret erfaring fra v0.1.14-a7

`test_assessment_is_event_history_not_test_mutation` feilet fordi samme mappe ble representert som `C:\Users\<langt-navn>\AppData\Local\Temp\...` og `C:\Users\<8.3-navn>\AppData\Local\Temp\...`. Stiene pekte til samme fil, men `assertEqual` sammenlignet ulike tekststrenger. Riktig kontrakt var **samme lagrede fil**: `Path.samefile()`.

Denne regresjonstypen skal forebygges i alle kommende Windows-relaterte endringer, ikke bare ved vurderingshistorikk.
