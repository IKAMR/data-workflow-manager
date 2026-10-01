# Arkade 5 CLI integration

## a26.3 - oppsett

Arkade 5 CLI konfigureres i Setup. Programstien lagres som den portable settingen
`arkade5_cli_path`. DWM validerer programfilen og identifiserer versjonen uten å
hardkode installasjonsmappe eller Arkade-versjon.

## a26.6 - kjøring

`Jobbhandlinger` kan starte Arkade 5 CLI for valgte DWM-jobber. Én DWM-jobb er
fortsatt ett uttrekk. Første støttede Arkade-operasjoner er:

- **Noark 5-test**: `test -a <Source extraction> -p <processing> -o <output> -t Noark5 -l nb`
- **PRONOM-analyse (Siegfried)**: `analyse -f <Source extraction> -o <output> -F filformatinfo -l nb`

Arkades processing-area for Noark-testen legges under konfigurert Temp-mappe,
eller operativsystemets temp når DWM Temp ikke er konfigurert.

## a26.7 - live-status

Den generelle eksterne CLI-runneren streamer stdout/stderr mens prosessen kjører.
GUI viser aktivitetsindikator, forløpt tid og Arkades siste statuslinjer. Dette er
aktivitetsstatus, ikke en beregnet prosent.

## a26.8 - output-layout og ansvar

DWM og Arkade har tydelig adskilt ansvar for output:

- DWM bestemmer bare **rotmappen** Arkade får og hvilken operasjon den tilhører.
- Arkade beholder ansvar for sine egne standard rapportmapper og resultatfiler.
- DWM sine egne prosesslogger og run-manifest ligger separat under `_dwm`.

Setup har settingen `arkade5_output_subfolder`. Standard er `arkade5_<ver>`.
Tokenet `<ver>` erstattes med oppdaget versjon inkludert `v`, for eksempel:

`arkade5_<ver>` -> `arkade5_v2.13.1`

Hvis feltet inneholder `arkade5_v2.13.1` brukes det bokstavelig.

Med `Work - operations = ...\repository_operations` blir layouten:

```text
repository_operations\
  arkade5_v2.13.1\
    noark5\
      <Arkades egne Noark 5-rapporter og mapper>
      _dwm\
        dwm_arkade5_run_manifest_<run-id>.json
        dwm_arkade5_stdout_<run-id>.txt
        dwm_arkade5_stderr_<run-id>.txt
    pronom\
      filformatinfo
      filformatinfo-statistikk.csv
      <andre filer Arkade selv produserer>
      _dwm\
        dwm_arkade5_run_manifest_<run-id>.json
        dwm_arkade5_stdout_<run-id>.txt
        dwm_arkade5_stderr_<run-id>.txt
```

DWM legger ikke lenger inn jobbnavn (`sip`), JOB-id eller en egen timestamp-mappe
mellom Arkade-roten og operasjonsmappen. Run-identitet bevares i DWM-sidecarfilene.
