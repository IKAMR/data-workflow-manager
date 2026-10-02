# a27.2 – Arkade 5 som workflow-operasjoner

Arkade 5 CLI-integrasjonen fra a26 er nå tilgjengelig som ordinære operasjoner i Noark 5-profilen:

- `arkade5_noark5_test` – Arkade 5 – Noark 5-test
- `arkade5_pronom_analysis` – Arkade 5 – PRONOM-analyse

Operasjonene bruker samme generelle CLI-runner, Arkade-planlegging, outputregler og automatiske evidensimport som den eksisterende handlingen **Kjør Arkade 5…**. De er derfor ikke en ny parallell Arkade-implementasjon.

## Bevisst ikke standard ennå

Ingen av operasjonene er lagt til i `noark5_standard`, `noark5_dwm` eller `noark5_analyse` i a27.2. De kan legges til eksplisitt i workflow på én jobb eller senere via batch-oppsettet planlagt for a27.

## Parameterkilder

I dette steget bruker operasjonene eksisterende DWM-kontrakter:

- Arkade CLI-sti og Arkade output-undermappe kommer fra Setup.
- Source kommer fra aktiv jobs `Source - extraction`.
- output går relativt til jobs `Work - operations`.
- Arkades native output forblir ekstern-tool-eid.
- DWM-manifest/logg/evidens følger den eksisterende DWM Work-undermapperegelen.
- resultatet importeres/kobles automatisk til samme jobb etter vellykket CLI-kjøring.

Den mer generelle prioriteringen mellom global setting, workflow-default, job-verdi og eksplisitt override hører til a27.3.
