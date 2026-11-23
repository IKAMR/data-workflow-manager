# Work-output layout

Fra v0.1.4-a6 skiller Data Workflow Manager mellom tre nivåer:

```text
Work - operations
└── App-undermappe
    └── Jobblistens undermappe-regel
        └── artefakter / tester / RUN-resultater
```

## Standard

Global innstilling:

```text
App-undermappe i Work = dwm
```

Med jobblisteregel `_test-<nnn>` blir eksempelvis:

```text
administrative_metadata\
  repository_operations\
    arkade5_v2.13.0\
    dwm\
      _test-001\
      _test-002\
```

`arkade5_v2.13.0` og `dwm` er dermed parallelle produsent-/verktøyområder under
`repository_operations`.

## Blank app-undermappe

Blank global verdi betyr at Data Workflow Manager bruker `Work - operations`
direkte som app-root.

Med jobbregel:

```text
repository_operations\_test-001
repository_operations\_test-002
```

Med både blank app-undermappe og blank jobbregel:

```text
repository_operations\
```

Dette er tillatt, men kollisjonskontroll gjelder fortsatt dersom flere jobber
ville ende på samme effektive output.

## Ansvarsdeling

`App-undermappe i Work` er globalt setup og ett fast mappenivå.

`Undermappe-regel for Work - operations` tilhører jobblisten og er nivået under
app-mappen. Den kan bruke `<jobno>`, `<jobid>`, `<nnn>`, `<name>` og `<source>`.

Denne delingen gjør at app-identitet og jobbisolasjon ikke blandes sammen i én
streng.
