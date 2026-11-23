# Permanent regel: fra utviklingsalpha til ferdig DWM-release

Gjelder alle overganger fra `vX.Y.Z-aN` til `vX.Y.Z`. Ingen funksjonstester
skal bli ugyldige bare fordi alfasuffikset fjernes.

## Under utvikling – også før siste alpha

1. Bruk `VERSION = "X.Y.Z-aN"` i `version.py` og PEP 440-verdien `X.Y.ZaN`
   i `pyproject.toml`. Den fysiske `version.py` inneholder kun `APP_NAME`
   og `VERSION`.
2. Nye funksjons- og regresjonstester skal teste **funksjonalitet**, ikke låses
   til eksakt alpha-streng. Ved milepælkrav, bruk
   `tests/version_assertions.py` og `assert_release_at_least(...)`. En ferdig
   `X.Y.Z` og senere versjoner oppfyller milepælene.
3. Kjør `py tools/release_gate.py --development` eller
   `py tools/release_prepare.py --check` ved hvert alpha-trinn. Kontrollene
   varsler om hardkodede alpha-versjoner før disse skaper release-feil.
4. Kjør `py tools/docs_layout.py --check`. Nye utviklingsnotater for hver
   `-aN` skal ikke legges i `docs/`. Oppdater heller kanoniske dokumenter.
   Historiske alpha-notater i `docs/history/` beholdes som arkiv.
5. `test.bat` forblir eneste fullstendige regresjonstest for Windows. Ingen
   release-kontroll erstatter automatiske tester eller praktisk GUI-/Work-test.

## Når siste alpha er ferdig

1. Ferdigstill og les gjennom `docs/RELEASE-vX.Y.Z.md` og legg **én** ny
   `## vX.Y.Z`-seksjon øverst i `docs/RELEASES.md`, uten å fjerne historikk.
   Notatene skal beskrive faktiske endringer, verifisering og begrensninger.
2. Klargjør `version.py` og `pyproject.toml` for sluttversjon.
   Utviklerverktøyet `py tools/release_prepare.py --promote` kan utføre
   akkurat disse to versjonsbyttene **når** release-notater, historikk og
   alpha-beredskap er kontrollert. Det lager ingen notater eller testfiks.
3. Kjør `py tools/release_gate.py`, `py tools/docs_layout.py --check` og
   deretter hele `test.bat` med faktisk sluttversjon.
4. Kjør relevante manuelle tester, særlig oppstart, eksisterende jobblister,
   fortsettelse og bevaring av Work-evidens.
5. Ferdig delta-ZIP lages fra det samme testede filsettet og inneholder alle
   endrede filer i repo-relative stier. Kontroller også ZIP-en i ren arbeidskopi.
6. **Brukeren** godkjenner, committer, pusher, tagger og lager GitHub-release.

`release_prepare.py --promote` er et frivillig utviklerverktøy før release-
leveransen, aldri et skript brukeren må kjøre etter utpakking av en release-ZIP.

## Varige sperrer

- `tools/release_gate.py` er **read-only**, oppdager versjonssprik og
  aktuelle testsperrer. Under alpha kontrolleres framtidig ren sluttversjon.
- `tests/test_release_promotion_guard.py` og `tests/test_release_prepare.py`
  er ordinære regresjonstester, ikke engangsfiler.
- `tools/docs_layout.py --check` og `tests/test_docs_layout.py` hindrer
  at dokumentrot og gjeldende alpha-historikk fylles med nye filer.
- Det er **forbudt** å lage falske alpha-markører i `version.py`, endre
  `VERSION` i en test, filtrere bort feilede tester, skjule testfeil eller
  justere produksjonskode bare for å oppfylle en foreldet versjonsvakt.
- Ingen `apply-release.bat`, postinstall-patcher, manuelle kodeutskiftninger
  eller skript for selvmodifisering under `test.bat` skal følge en release-ZIP.
- Full test skal kjøres etter sluttversjonen, og releasepakke skal kontrolleres
  i en ny arbeidskopi. En statisk kontroll gir aldri alene release-godkjenning.

## Historisk erfaring – v0.2.1

Første release-ZIP for v0.2.1 krevde en separat patch og førte til flere
feil fra gamle alpha-vakter og manglende historikk. Slike problemer skal
oppdages mens alpha-utviklingen pågår, ikke først når sluttversjonen klargjøres.
