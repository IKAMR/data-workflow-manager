# v0.1.15-a7 – kontrollplanutkast og hovedmenyplassering

## Endringer

- `Rapport → Kanoniske resultatdata…` har ny **Kontrollplan (utkast)…**. Brukeren velger eksplisitt en JSON-kontrollprofil, og DWM sammenholder den med allerede registrert evidens fra valgt Work. Ingen nye kontroller kjøres.
- `config/noark5/control-profile-dwm-draft-v1.json` er et **utkast**, ikke en vedtatt kravprofil eller automatisk vurdering av Noark 5. Kravene er foreløpig kategorinivå, ikke komplett testkatalog. Betingede kontroller må konkretiseres per leveranse.
- En kontroll som er registrert, får `registered_unverified`. Manglende evidens får `not_documented`. Selv om samtlige kategorier har registrert evidens, forblir `requirements_verified=false`, `coverage_complete=null` og `archive_approved=false`.
- Ny plasseringsovervåker korrigerer toppmenyenes popup-posisjon etter at eldre global vindusplassering har flyttet en `QMenu` feilaktig. Den gjelder bare hovedmenyene, ikke modalvinduer eller delmenyer.

## Test

1. Kjør `test.bat`.
2. Åpne menyen **Rapport**. Kontroller at nedtrekksmenyen er forankret rett under menyteksten, ikke sentrert i DWM-vinduet.
3. Åpne **Kanoniske resultatdata…**, velg **Kontrollplan (utkast)…**, og velg `config/noark5/control-profile-dwm-draft-v1.json` i repoet.
4. Kontroller at det står **UTKAST**, at de to foreløpig påkrevde kontrollkategoriene vises, og at ingen godkjenningsstatus gis.

## Begrensninger og videre arbeid

- Et faglig godkjent, versjonert kravgrunnlag med komplette tester for Noark-versjon, uttrekkstype, avtale og eventuelle unntak mangler fortsatt. Først da kan DWM vurdere reell kontrollfullstendighet.
- Registrert Arkade- eller Siegfried-kjøring dokumenterer ikke automatisk beståtte individuelle kontroller. Faktiske resultatfiler må analyseres mot bekreftet skjema.
- Kvalitetssikringsrapport, arkivskapers aksept, depotgodkjenning, journalføringsgrunnlag og AIP-inkludert evidens er planlagt i `docs/NOARK5-CONTROL-TO-PRESERVATION-ROADMAP.md` fra a4, men ikke implementert i a7.
- Work er eneste lesekilde. Originale Source-filer, resultater, vurderinger og den kanoniske indeksen endres ikke av kontrollplanutkastet.
