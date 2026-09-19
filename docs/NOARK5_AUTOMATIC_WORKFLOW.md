# Automatic Noark 5 workflow assignment

When `Finn jobber...` creates Noark 5 jobs, the selected discovery workflow can
be assigned automatically.

The default is the canonical `noark5_standard` sequence from
`config/workflow_sequences.json`:

1. Metadataoversikt
2. Valider XML mot XSD
3. Analyse arkivstruktur
4. Noark 5 XPath-tester 2026
5. Noark 5 views/compositions
6. Noark 5 depotvalideringsrapport

Historic U1/U2 and regression operations are deliberately not part of the
normal standard sequence.

Setup also offers:

- `Ingen automatisk workflow`
- `Noark 5 – grunnkontroll`

The workflow definition itself stays in `config/workflow_sequences.json`; the
discovery feature only selects and applies that definition.
