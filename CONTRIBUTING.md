# Contributing

Takk for interesse for Data Workflow Manager.

## Issues

Bruk repositoryets Issue Forms for feil og forbedringsforslag. Søk først etter
eksisterende saker.

Ikke publiser sensitivt arkivmateriale, personopplysninger, passord, interne
stier eller andre opplysninger som ikke bør være offentlige.

## Bug reports

Oppgi minst:

- programversjon
- operativsystem
- profil/domene og arbeidsoperasjon
- forventet og faktisk resultat
- trinn for å gjenskape feilen
- relevant loggutdrag, renset for sensitiv informasjon

## Feature requests

Beskriv behovet før løsningen. Oppgi gjerne om funksjonen er generisk eller
profilspesifikk (for eksempel Noark 5, SIARD eller ADDML).

## Development

Les først:

1. `docs/DATA-WORKFLOW-MANAGER.md`
2. `docs/IDENTITY-MIGRATION.md`
3. `docs/DEVELOPMENT.md`
4. `docs/ARCHITECTURE.md`
5. `docs/INTERFACE.md`
6. `docs/TESTING.md`

Gjør minst mulig nødvendig endring og unngå å omskrive større GUI- eller
kjernelag uten behov.

Mottatte kilder skal som hovedregel behandles read-only. Genererte logger,
rapporter, PREMIS og avledede data skal ikke skrives inn i originalkilden uten
en eksplisitt og dokumentert operasjon.

## Testing

Kjør `test.bat` etter meningsfulle kodeendringer og før commit. Gjør i tillegg
relevant praktisk test via `start.bat`.
