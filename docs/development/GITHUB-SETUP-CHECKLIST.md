# GitHub setup checklist

Disse punktene kan ikke styres fullt ut av filene i denne pakken og må kontrolleres i GitHub.

- [ ] Issues er aktivert.
- [ ] De gamle `bug_report.md` og `feature_request.md` er slettet etter at de nye `.yml`-skjemaene er lagt inn.
- [ ] Kontroller at blank issues ikke tilbys (`config.yml` setter `blank_issues_enabled: false`).
- [ ] Opprett/rydd labels: `bug`, `enhancement`, `documentation`, `question`, `good first issue`, `help wanted`, `duplicate`, `not planned`.
- [ ] Legg bare til noen få komponent-labels ved faktisk behov, f.eks. `workflow`, `noark5`, `validation`, `ui` og eventuelt `siard`.
- [ ] Opprett milestone `v0.2.0`. Vent med flere versjonsmilestones til de faktisk trengs; bruk eventuelt `Future`.
- [ ] Vurder å aktivere GitHub Private vulnerability reporting før `SECURITY.md` peker brukere dit som primær kanal.
- [ ] Bruk Issues som arbeidsoppgaver og knytt commits/PR-er til dem når det er naturlig (`Fixes #...`).
- [ ] Ikke innfør GitHub Projects før Issues + Labels + Milestones + Pull Requests faktisk blir utilstrekkelig.
