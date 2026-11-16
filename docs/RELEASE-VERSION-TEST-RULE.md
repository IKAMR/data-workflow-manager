# Permanent regel: fra utviklingsalpha til ferdig DWM-release

Denne regelen gjelder **alle** overganger `vX.Y.Z-aN` → `vX.Y.Z`, inkludert
v0.2.1-a16 → v0.2.1. Ikke bare Noark-arbeidspakken.

## 1. Versjon og semantikk

- Applikasjonsversjonen i `version.py` endres fra `X.Y.Z-aN` til **ren** `X.Y.Z`.
  Den fysiske filen inneholder kun `APP_NAME` og `VERSION`.
- `pyproject.toml` `[project].version` skal være **samme** `X.Y.Z`.
  Distribusjonsnavnet beholdes.
- Ferdig release er nyere enn alle `X.Y.Z-aN`. Funksjonstester fra alpha
  forblir bindende regresjonstester, men må bruke en **nedre versjonsgrense**,
  ikke hardkodet likhet med ett alpha-trinn.
- For milepæler brukes `tests/version_assertions.py`:
  `assert_release_at_least(self, f'VERSION = "{VERSION}"', "X.Y.Z", N)`.
  Bare en ekte sluttversjon eller en alpha med minst N oppfyller dette.
- Det er **forbudt** å gi `version.py` ekstra falske alpha-markører, endre
  runtime-`VERSION` i en test, filtrere bort feilede tester eller simulere
  tidligere versjonsstrenger for å få grønne tester.

## 2. Release-delta er komplett ved utpakking

- ZIP-en skal inneholde alle ferdig redigerte filer i riktige repo-relative
  stier, både kode, eldre versjonsvakter, release-tester og dokumentasjon.
- **Ingen** `apply-release.bat`, postinstall-patcher, manuelle kodeutskiftninger
  eller skjult selvmodifisering under `test.bat`.
- `docs/RELEASES.md` skal ha nøyaktig én ny `## vX.Y.Z`-oppføring og bevare
  hele den historiske releaseoversikten, uten å kutte eller skrive om gamle
  seksjoner. `docs/RELEASE-vX.Y.Z.md` beskriver faktisk omfang og begrensninger.
- En release-rettingsdelta kan hete `vX.Y.Z.1.zip`, `vX.Y.Z.2.zip` osv. som
  **pakkenavn**, mens programversjonen fortsatt er `X.Y.Z` inntil en faktisk
  ny release er besluttet.

## 3. Obligatoriske tester FØR ZIP leveres

1. Start med siste **committede alpha**. Gjør alle release-endringer i en
   isolert arbeidskopi (ikke i Source/Work eller ved å endre arkivdata).
2. Søk etter alle tester som krever bokstavelig `-aN`, for eksempel
   `assertRegex(VERSION, r'^X.Y.Z-a...')`, `assertEqual(VERSION, ...)`, og
   `assertIn('VERSION = "X.Y.Z-aN"', ...)`. Rettes semantisk – funksjonelle
   assert-er fjernes aldri.
3. Kjør den skrivebeskyttede **`py tools/release_gate.py`**. Den skal
   avsløre hardkodede alpha-versjonskrav, feil mellom runtime og distribusjon,
   og manglende releasehistorikk.
4. Kjør **hele** `test.bat` med den endelige, fysiske `version.py` og
   `pyproject.toml`. Ingen tilpasninger bare på brukerens maskin. Dokumenter
   antall bestått, feilet, feil under kjøring og hoppet over.
5. Lag ZIP-en **fra samme testede filsett**, pakk den ut i en annen ren kopi av
   siste alpha og kjør `release_gate.py` + full `test.bat` igjen.
6. Be bruker kjøre `test.bat` i Windows og relevante GUI-/Work-tester. Ikke
   be om commit/tag/push før full test og operatørkontroll er grønn.
7. **Brukeren** committer, pusher og oppretter release/tag i GitHub; assistenten
   oppretter aldri commit, tag eller release på brukerens vegne.

## 4. Egen regresjonssperre

`tests/test_release_promotion_guard.py` skal være en ordinær `test.bat`-test.
Den kjører samme release-preflight for ferdig versjon, og tester også at
preflight **finner** utgåtte alpha-vakter i syntetiske testfiler.

Denne statiske kontrollen kommer **i tillegg til** fulltest; den må ikke
brukes som erstatning for å kjøre alle eksisterende funksjonstester.

## 5. Hva gikk galt ved v0.2.1?

Første release-ZIP inneholdt `apply-v0.2.1.bat` i stedet for å inkludere de
ferdig korrigerte testfilene og den oppdaterte `RELEASES.md`. Brukeren fikk
seks feil: fem gamle alpha-vakter og én manglende historikkoppføring.
Det er en feil i release-leveransen, ikke dokumentasjon på feil i Noark-motoren.

**Fast leveranseregel:** En ZIP som trenger et ekstra manuelt patchsteg er
*ikke* en ferdig release-delta og skal ikke leveres som sådan.
