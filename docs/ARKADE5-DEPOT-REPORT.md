# Arkade 5 i depotvalideringsrapporten

v0.1.5-a5 kobler den samlede DWM/Arkade-dekningsmodellen fra a4 inn i
selve depotrapportgrunnlaget.

## Prinsipp

Arkade 5 er **ekstern teknisk evidens**. Importerte Arkade-resultater kan
dokumentere kontrollområder som DWM ikke tester selv, men de blir ikke gjort om
til DWM-masterresultater.

DWM beholder derfor tre adskilte nivåer:

1. interne DWM-resultater og intern teknisk status,
2. importert Arkade-evidens med Arkades egne resultater og funn,
3. depotets faglige vurdering.

Arkade-resultater kan gi vurderingspunkter, men a5 gjør ingen automatisk
faglig godkjenning eller avvisning.

## Alle Arkade-kjøringer beholdes separat

Depotrapporten velger ikke skjult «siste» Arkade-import. Alle Arkade-rapporter
som er importert i jobbens `work_operations` tas med som separate evidensgrupper.

For hver import registreres blant annet:

- `import_id`
- Arkade-versjon når kjent
- testdato
- originalt filnavn og SHA-256
- sti til bevart originalfil
- sti til normalisert resultat
- komplett combined coverage for den konkrete Arkade-kjøringen

Dette gjør det mulig å ha flere Arkade-kjøringer uten at en nyere import
overskriver eller skjuler en tidligere.

## Hvordan hull dekkes

For hvert av Arkades 54 kontrollområder brukes a4-modellen:

- `covered_by_both`
- `covered_by_arkade`
- `covered_by_dwm`
- `not_covered_in_run`

`covered_by_arkade` betyr at Arkade gir teknisk evidens der aktuell DWM-kjøring
ikke har et eget resultat. Dette er særlig viktig for `arkade_only`-kontroller
som filintegritet, sjekksummer og referanseintegritet.

## Rapportmodell

Maskinlesbar depotrapport får:

```text
external_validation.arkade5
```

med sammendrag og en separat post for hver importert Arkade-kjøring.

DWM sin eksisterende:

```text
technical_validation.status
```

endres ikke automatisk av Arkade. Arkade-feil og advarsler materialiseres i
stedet som egne vurderingspunkter under `deviations`.

## HTML-rapport

HTML-rapporten får en egen seksjon **Ekstern validering – Arkade 5** med:

- antall importerte Arkade-kjøringer,
- antall kontrollområder som dekkes av Arkade uten DWM-resultat,
- per Arkade-kjøring: testdato, versjon, import-ID, dekning, feil og advarsler.

Detaljert rå og normalisert evidens forblir bevart under:

```text
work_operations/external_evidence/arkade5/<import_id>/
```

Rapporten er dermed en visning over evidensen, ikke en erstatning for den.
