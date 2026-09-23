
# Arkade 5 – dekningspolicy for DWM

Fra v0.1.5-a11 er strategien for dokumenterte DWM-gap eksplisitt og
maskinlesbar.

## Hovedregel

Arkade 5 brukes som ekstern validator for kontrollområder som DWM ikke
implementerer selv. Et kontrollområde er derfor ikke et udekket hull i den
samlede valideringen bare fordi DWM mangler en intern test.

Arkade-resultatet:

- forblir ekstern evidens,
- blir ikke et DWM-masterresultat,
- beholder Arkade test-ID og proveniens,
- kan tette et dokumentert DWM-gap i samlet coverage,
- utløser ikke krav om umiddelbar reimplementering i DWM.

## Dagens 13 dokumenterte DWM-gap

Følgende Arkade 5 v2.13.0-kontroller har relasjonen `arkade_only`:

- N5.01
- N5.02
- N5.28
- N5.30
- N5.32
- N5.33
- N5.34
- N5.47
- N5.48
- N5.51
- N5.62
- N5.63
- N5.64

For alle disse er dagens strategi:

`current_coverage_strategy = use_arkade_external`

og:

`dwm_internal_implementation = deferred`

Dette er en eksplisitt prioritering, ikke en påstand om at kontrollene aldri
skal implementeres i DWM.

## Overlapp

- `equivalent`: begge kilder kan beholdes og sammenlignes når det finnes et
  sikkert felles resultat.
- `partial`: begge kilder beholdes.
- `complementary`: begge kilder beholdes.
- `dwm_only`: DWM-resultatet står på egne premisser.

Lik N5-nummertekst er aldri tilstrekkelig for ekvivalens.

## Maskinlesbar policy

Policyen ligger i:

`config/noark5/external/arkade5_coverage_policy.json`

`validate_arkade5_coverage_policy()` kontrollerer at listen over
`use_arkade_external` er identisk med de dokumenterte `arkade_only`-gapene fra
gap-/overlappanalysen.
