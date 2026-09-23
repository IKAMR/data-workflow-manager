# Arkade 5 – samlet dekningsvisning i GUI

v0.1.5-a6 gjør den samlede DWM/Arkade-dekningen fra depotrapporten synlig i
resultatvisningene.

## Formål

Visningen skal gjøre det enkelt å se hvilke Noark 5-kontrollområder som i en
konkret kjøring er dekket av:

- DWM og Arkade 5,
- bare Arkade 5,
- bare DWM,
- ingen av kildene i den aktuelle kjøringen.

Dette er deknings- og evidensinformasjon. Det er ikke en ny testmotor og ikke en
automatisk depotkonklusjon.

## Datagrunnlag

GUI-et leser `external_validation.arkade5` fra den allerede materialiserte
depotvalideringsrapporten. Det kjører ingen ny XML/XPath-analyse og beregner
ikke dekningsmodellen på nytt.

For hver importerte Arkade-kjøring vises blant annet:

- Arkade-versjon,
- testdato,
- import-ID,
- kildefil og SHA-256,
- samlet dekningsstatus,
- Arkade test-ID og navn,
- relasjon til DWM (`equivalent`, `partial`, `complementary`, `arkade_only`),
- DWM-test-ID-er,
- Arkade-status og feil/advarsler.

## Prinsipp

Arkade-resultater forblir ekstern evidens. De blir ikke skrevet om til interne
DWM-masterresultater. `partial` og `complementary` beholder begge kilder som
selvstendige resultater. `arkade_only` viser eksplisitt hvor Arkade fyller et
dokumentert hull i DWM.
