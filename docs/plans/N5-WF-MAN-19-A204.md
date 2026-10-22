# N5 WF Man 19 – a20.4

Baseline: committet a19 med påfølgende a20, a20.1, a20.2 og a20.3.

- a20.4 er en rapportjobb-/jobblistegjenfinning, ikke ny XPath-analyse.
- 1535, 1532, 1547, 1539: velg eksisterende `repository_operations/dwm`
  eller passende overmappe, og lag separate `.n5jobs` om JOB-ID kolliderer.
- Før fullstendig gjenoppretting av en kjøreklar jobb kreves opprinnelige
  workflow_ids, operasjonsparametre, checkpoint, kildestier og kjøringshistorikk.
- `test_a18_fix6_single_job_report` var foreldet etter a20.3 og er oppdatert.
- Ta ikke ut `source_extraction` fra historiske manifeste som autoritativ
  nåværende diskbane: bruke funnet report/work-sti for selve rapportlesingen.
- Manglende `depot_validation_report.json` må håndteres særskilt ved å bygge
  depotrapport fra eksisterende normale XPath-/view-resultater.
