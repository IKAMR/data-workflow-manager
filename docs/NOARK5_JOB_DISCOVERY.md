# A15.1 – Oppdag Noark 5-jobber fra Robocopy-liste

A15.1 støtter import av én eller flere Robocopy `/L`-logger som grunnlag for
automatisk opprettelse av Noark 5-jobber.

- Kandidat må inneholde `arkivstruktur.xml`.
- `arkivstruktur.xml` + `arkivuttrekk.xml` gir status **Sikker**.
- `repository_operations`, `schema`, `_debug`, `_work`, `_test`, `_temp`,
  `report/reports` og `arkade5_*` utelukkes.
- Funn vises i dialog før jobber opprettes.
- Dialogen har **Velg alle**, **Velg ingen** og **Inverter valg**.
- Eksisterende Source i jobblisten kan ikke legges til på nytt.
- En tom `JOB-001` gjenbrukes for første funn.
- Source og `profile_id=noark5` settes; Work/Storage kommer i neste increment.

Noark 5-deteksjonen ligger i `noark5_workflow/plugins/noark5/discovery.py`
som et første, lite steg mot den planlagte plugin-grensen.
