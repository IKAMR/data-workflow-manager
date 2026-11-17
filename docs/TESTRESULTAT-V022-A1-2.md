# DWM v0.2.2-a1.2 – målrettede tester

- Programversjon: **0.2.2-a1** (uendret).
- Delta-baseline: **v0.2.2-a1.1**, over utgitt v0.2.1.
- 15/15 nye flerjobbtester: **PASS**.
- 20/20 eksisterende v0.2.2-a1 depotprofil-/overgangstester: **PASS** i isolert kompatibilitetskopi (med en lokal stub kun for fraværende `app.user_profile`).
- Totalt 35/35 målrettede tester i isolert kontroll.
- Python 3.13: alle leverte Python-filer syntaksvalidert med `compileall`.
- `test.bat` (hele repoet): **ikke kjørt her**; må kjøres på brukerens Windows-maskin.
- Ekte visuell PySide6-kontroll: **ikke kjørt her**, ettersom PySide6 mangler i sandkassen.
- Ingen Git-kommandoer som skriver/committer/pusher er utført mot brukerens repo.

Kjør `test.bat` direkte etter utpakking, uten ekstra patch-BAT.
