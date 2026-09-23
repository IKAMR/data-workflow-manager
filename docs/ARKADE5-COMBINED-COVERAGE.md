# Samlet DWM- og Arkade 5-dekning

a4 etablerer en eksplisitt samlet dekningsmodell for Noark 5-kontroller.

Målet er at Arkade 5 skal kunne tette dokumenterte hull i DWM uten at Arkades
resultater blir gjort om til interne DWM-resultater eller at to tester feilaktig
blir behandlet som semantisk like.

## Kilder

Modellen bruker fire separate kunnskaps-/resultatlag:

1. `config/noark5/external/arkade5_test_catalog.json` beskriver hva Arkade 5
   v2.13.0 tester.
2. `config/noark5/external/dwm_arkade5_mapping.json` beskriver den verifiserte
   relasjonen mellom Arkade- og DWM-kontroller.
3. Importerte Arkade-resultater ligger under
   `work_operations/external_evidence/arkade5/<import_id>/`.
4. DWM-resultater beholder sin eksisterende interne resultat-/mastermodell.

Ingen av lagene erstatter et annet.

## Samlet status

For hvert av Arkades 54 kontrollområder beregnes en kjøringsspesifikk status:

- `covered_by_both`: begge kilder har resultat/evidens.
- `covered_by_arkade`: Arkade har resultat og fyller dermed et DWM-hull eller
  en manglende DWM-kjøring.
- `covered_by_dwm`: DWM har resultat, men Arkade-resultat er ikke importert.
- `not_covered_in_run`: ingen av kildene har resultat i den aktuelle kjøringen.

Dette er **dekningsstatus**, ikke faglig godkjenning.

## Hvordan Arkade tetter hull

For `arkade_only`-kontroller, eksempelvis N5.30, N5.32, N5.47 og N5.64, kan et
importert Arkade-resultat gjøre kontrollområdet `covered_by_arkade`.

Dette betyr:

- kontrollområdet har ekstern teknisk evidens,
- Arkades egne feil, advarsler og funn beholdes,
- DWM skal ikke vise kontrollen som en intern DWM-test,
- DWM-masterresultater endres ikke.

## Delvis og komplementær dekning

Ved `partial` og `complementary` skal begge resultater beholdes separat. Arkade
skal ikke overskrive DWM og DWM skal ikke skjule Arkade.

Eksempel N5.24:

- DWM `kdrs.c22` rapporterer sin egen telling,
- Arkade bruker egne unntaksregler,
- samlet status kan være `covered_by_both`,
- relasjonen forblir `partial`.

## Ekvivalens

Kun eksplisitt verifiserte mappinger kan ha `equivalent`. Felles N5-nummer,
likt navn eller likt resultat er aldri alene tilstrekkelig.

## DWM-only

DWM-kontroller uten direkte Arkade-test beholdes som egne `dwm_only`-rader.
Dette gjelder blant annet historiske KDRS-kontroller og U1/U2. Arkades manglende
implementasjon av et nummer gjør ikke KDRS-nummeret til et Arkade-nummer.

## Implementasjon

`noark5_workflow/external_evidence/combined_coverage.py` bygger modellen fra:

- normalisert Arkade-evidens,
- listen over DWM-test-ID-er som faktisk finnes i aktuell kjøring,
- a2-mappingen,
- Arkade-katalogen fra a1.

Modellen er bevisst uavhengig av GUI og depotkonklusjon, slik at den kan brukes
av rapporter, analyser, andre grensesnitt og andre prosjekter.
