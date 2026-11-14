# a10: Samlet kildevalg i Kanoniske resultatdata

## Endret arbeidsflyt

`Rapport -> Kanoniske resultatdata` viser DWM-kilder og kjente Arkade-/Siegfried-resultatfiler i samme kildeliste. Kildene oppdages innenfor valgt Work i en bakgrunnsoppgave. Eksterne resultater er merket `Ekstern - ikke analysert` fram til eksplisitt analyse. Tidligere lagrede eksterne kildevalg gjenopprettes som avkrysset; nye kandidater velges ikke automatisk.

- `Opprett resultatindeks` gjelder bare DWM-kilder; eksterne kilder inngår ikke i denne operasjonen.
- `Analyser valgte eksterne resultater` gjelder bare avkryssede eksterne kilder. Ingen ekstra dialog eller filvelger brukes. Knappen er deaktivert hvis ingen eksterne er valgt.
- Resultatet vises nederst i det samme vinduet. Statusfeltet viser antall valgte eksterne filer og at ny analyse erstatter forrige genererte `noark5_evidence/canonical-external-analysis.json`.
- Alle valgte eksterne kilder analyseres samlet. Kildeoriginaler, `canonical-results.json` og tidligere vurderinger endres ikke.
- Dette er registrert evidens, ikke en godkjenning. Uforståtte kildeformater rapporteres som `not_parsed`.

## Avgrensninger

`Finn ekstern evidens` er den eldre rådgivende kandidatvisningen. `Koble vurderinger / ekstern evidens` og kontrollprofilvelgerne er foreløpig egne funksjoner og endres ikke av a10-korrigeringen. Full praktisk GUI-test på Windows med nettverksdisk og `test.bat` gjenstår.
