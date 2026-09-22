# Rapport-output

A15 etablerer en felles retning for rapport-output i Data Workflow Manager.

## Bruk

Arkade 5-analysen kan eksporteres direkte fra analysevinduet med
`Generer rapport...`.

Fra `Resultatvisninger -> Ekstern evidens` kan alle importerte Arkade 5-
analyser eksporteres samlet med `Generer alle rapporter...`.

Brukeren velger output-mappe. Sist brukte rapportmappe huskes som
`last_report_output_dir`, slik at neste eksport starter samme sted.

## Formater i a15

Hver Arkade 5-analyse genererer:

- HTML: selvstendig, lesbar rapport for praktisk bruk og utskrift.
- JSON: strukturert sidecar med samme analysegrunnlag og proveniens.

Rapportnavnet inneholder Arkade testdato og import-ID.

## Videre retning

Rapport-output er lagt i `noark5_workflow/reporting/` slik at andre DWM-
rapporter senere kan bruke samme output-mekanisme. Målet er at brukeren skal
kunne velge ønskede rapporttyper og generere dem samlet til én valgt output-
mappe, uten å lete etter resultatfiler i Work-strukturen.
