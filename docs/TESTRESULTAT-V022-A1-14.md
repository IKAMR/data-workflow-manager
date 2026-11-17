# DWM v0.2.2-a1.14 – målrettede testresultater

Miljø: Linux-container, Python 3.13.5. PySide6 er ikke installert i dette
miljøet. Testene bruker Qt-frie policyfunksjoner og testdobler for Qt-oppsettet.

Kilde: GitHub `IKAMR/data-workflow-manager`, commit `1d370a9ae5c3`.
Pakkens a1.13-utgangsfiler er kontrollert mot GitHub-blobhassher.

Testkommando (relevant del av det rekonstruerte GitHub-grunnlaget):

```text
python -m unittest discover -s tests -p 'test_v022_a1_*.py' -q
----------------------------------------------------------------------
Ran 106 tests

OK
```

Omfang:
- Tidligere flerjobbtester, kontekst og lagring.
- Tidligere auto-fit- og dialogkontrasttester (funksjonene beholdes,
  men aktiveres ikke ved normal oppstart).
- Eksisterende a1.12/a1.13-oppsprang-/diagnostikktester.
- Nye a1.14-tester: sikker standard, uavhengige opt-ins,
  Safe Mode-overstyring, init før `window.show`, ikke-skriving av jobbdata,
  og unike diagnostikkfilnavn.

Begrensninger: 106/106 er **målrettede** tester. Hele DWM-testpakken er ikke
kjørt i dette miljøet. Native Windows `0xC0000005` og Qt-maling kan ikke
reproduseres her. Brukerens `test.bat` og praktisk Windows-start må verifiseres.
