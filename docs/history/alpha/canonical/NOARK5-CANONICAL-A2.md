# v0.1.15-a2 – kontrollert resultatkildeoversikt

A2 legger til en separat, **skrivebeskyttet** Work-adapter for den kanoniske
v1-modellen fra a1. Den viser kandidater for `master-results.json`,
`raw-results.jsonl` og resultatbank v2 innenfor valgt Work, med status.
Historiske/regresjonskjøringer merkes og velges aldri automatisk.

Fra repo-roten:

```powershell
py -m noark5_workflow.analysis.canonical_work_adapter --work "I:\...\repository_operations\dwm" --discover
```

Velg deretter **bevisst** hvilke av de viste filene som skal inkluderes, og
bruk den eksisterende byggeren:

```powershell
py -m noark5_workflow.analysis.canonical_results --work "I:\...\repository_operations\dwm" --master "noark5_tests\xpath\RUN-...\master-results.json" --dry-run
```

Etter eksplisitt generering av `noark5_evidence/canonical-results.json`:

```powershell
py -m noark5_workflow.analysis.canonical_work_adapter --work "I:\...\repository_operations\dwm" --report
```

Rapportadapteren viser **dekning per evidenskilde**, ikke summer av arkivdata,
kontrollgodkjenning eller statistikk. Original Source, tidligere Work-evidens,
vurderinger og jobbstatus endres ikke.

## Neste arbeid

* Verifisere hvilke faktiske result-bank-stier og historiske kjøringsmapper som
  brukes i eldre Work, mot eksempler fra Windows.
* Koble eksplisitt kildevalg og dekning til GUI uten å gi historiske tester
  autoritativ masterrolle.
* Utvide modellen med kildebelagte identiteter og dimensjoner før sammenligning,
  aggregering, rapporter for godkjenning og statistikk på tvers av uttrekk.
