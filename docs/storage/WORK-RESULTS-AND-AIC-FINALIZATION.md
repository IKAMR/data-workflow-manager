# Arbeidsresultater, testhistorikk og AIC-finalisering

Dette dokumentet beskriver skillet mellom resultater som oppstår under arbeid med et Noark 5-uttrekk og det kuraterte utvalget som senere skal inngå i en bevaringspakke/AIC.

## Grunnprinsipp

En arbeidsflyt kan kjøres mange ganger. Tester kan feile, gjentas etter rettelser eller kjøres med andre parametre. Disse kjøringene er en del av arbeidshistorikken og skal ikke automatisk tolkes som innhold som skal bevares i endelig AIC.

Vi skiller derfor mellom:

1. **Kilde/evidens** – mottatt Noark 5-uttrekk.
2. **Arbeidsresultater og kjøringshistorikk** – testresultater, rapporter, logger, PREMIS-hendelser, mellomprodukter og nye testkjøringer.
3. **Finaliseringsutvalg** – eksplisitt valgt subset av arbeidsresultater som er faglig relevant for bevaring.
4. **AIC/AIP-utdata** – endelig kuratert bevaringspakke.

## Gjentatte tester

Det skal være normalt å kunne:

- kjøre samme test flere ganger
- rette et problem og kjøre testen på nytt
- beholde tidligere kjøringshistorikk
- sammenligne tidligere og ny kjøring
- dokumentere at et avvik senere ble rettet

En ny kjøring skal derfor ikke stille overskrive historikk fra en tidligere kjøring. Filer som ikke naturlig får unike navn må ha en eksplisitt output-policy, for eksempel `append`, `versioned`, `fail` eller eksplisitt `replace`.

Workflow-PREMIS er historikk og skal akkumulere hendelser ved gjentatte kjøringer i samme arbeidsområde.

## Flere jobber og output

Forskjellige jobber i samme jobbliste skal ha forskjellige `output_root`. Output-locking beskytter mot samtidig skriving, men beskytter ikke mot at jobb B senere overskriver filer fra jobb A. Derfor er identisk `output_root` mellom forskjellige jobber en konfigurasjonsfeil.

Samme jobb kan derimot kjøres flere ganger mot sitt eget arbeidsområde. Resultatene må da bevares eller versjoneres i henhold til operasjonens output-policy.

## Finalisering til AIC

Endelig AIC skal ikke automatisk inneholde alt som noen gang er produsert i arbeidsområdet.

En senere finaliseringsoperasjon bør kunne velge et eksplisitt subset, for eksempel:

- siste gyldige rapport fra en test
- både første feilede og senere vellykkede test når dette er dokumentasjonsmessig relevant
- utvalgte logger og PREMIS-proveniens
- valideringsrapporter som skal følge bevaringspakken
- eksplisitt godkjente avledede filer

Utvalget bør kunne uttrykkes som en manifest-/seleksjonsmodell slik at det er etterprøvbart hvorfor bestemte resultater ble tatt med eller utelatt.

## Videre design

Følgende hører til senere utvikling:

- run-ID for hver konkret kjøring
- eksplisitt output-policy per operasjon
- resultatregister per jobb og per run
- markering av resultater som kandidater til finalisering
- finaliseringsmanifest
- egen workflow-operasjon for AIP/AIC-finalisering

Dette bygger videre på checkpoint-, jobb- og batchmodellen uten å blande arbeidsområde og ferdig bevaringspakke.

## Mange tester, rettelser og gjentatte kjøringer

En avlevering kan gjennomgå mange tester. Tester kan avdekke feil som fører til manuelle eller automatiserte rettelser, etterfulgt av nye testkjøringer.

Arbeidsområdet skal derfor kunne bevare flere testresultater og kjøringer uten at nyere kjøringer utilsiktet overskriver tidligere dokumentasjon. På sikt bør hver operasjonskjøring få en stabil run-ID og registreres i et resultatregister.

## Utvalg til endelig AIC

Alt som produseres under arbeidsflyten skal ikke automatisk tas med i endelig AIC. AIC-finalisering skal kunne velge et eksplisitt subset av arbeidsresultatene. Dette kan være siste gyldige rapport, relevante tidligere rapporter som dokumenterer feil og rettelser, nødvendig PREMIS-proveniens og annen dokumentasjon som er valgt for bevaring.

Dersom første test er dekkende, komplett og feilfri, kan subset i praksis være lik hele resultatsettet. Det skal likevel være et eksplisitt finaliseringsvalg, ikke en tilfeldig konsekvens av hva som ligger i arbeidsområdet.

## Planlagt resultatmodell

Videre utvikling bør innføre:

- run-ID per operasjonskjøring
- resultatregister per jobb
- kobling mellom resultat, operasjon, tidspunkt, status og genererte filer
- eksplisitt output-policy per operasjon: `unique`, `append`, `versioned`, `replace` eller `fail`
- markering av hvilke resultater som skal tas med videre
- finaliseringsmanifest for AIC
- AIC-finalisering som eget workflow-steg
