# v0.1.15-a8 – Kontrollutfall og KS-grunnlag

## Faktisk funksjon

`Rapport → Kanoniske resultatdata… → Kontrollutfall / KS…` lar operatøren
velge **et eksplisitt kontrollprofilutkast**. DWM sammenholder dette med en
allerede opprettet `noark5_evidence/canonical-results.json` i valgt Work.
Utdata vises i GUI. **Ingen fil skrives** av denne kontrollen.

For hvert kontrollområde vises kilde, registrerte utfall og et konservativt
sammendrag. En `ok`-status i `dwm_raw` beskriver bare en vellykket kjøring;
den verifiserer ikke hva Arkade 5, XML/XSD eller Siegfried faktisk testet.
`ok` i `dwm_master` presenteres som *rapportert OK, ikke faglig verifisert*.
Registrerte feil og advarsler fremheves. Ukjent status behandles ikke som OK.

## Kvalitetssikringsrapport – planlagt arbeidsflyt

Den første KS-visningen lager en oppgaveliste for vurdering av arkivinnhold,
periode, arkivskaper, proveniens, betingede kontroller og funn. Den produserer
**ikke** et ferdig dokument, sender ingenting til arkivskaper og registrerer
ingen aksept eller godkjenning.

Neste steg må legge til:

1. en godkjent og versjonert kontrollprofil per relevant Noark-/leveranseprofil,
   med eksplisitt beslutning om betingede kontroller;
2. parser av faktiske Arkade 5- og Siegfried-rapporter med test-/filnivå,
   dokumentert skjema og evidenspeker;
3. faglige vurderinger per kontroll, avvik og M-ID, med person, tid og
   beslutningsgrunnlag;
4. KS-rapport til arkivskaper, arkivskapers svar og signert innholds- og
   proveniensbekreftelse;
5. depotets separat journalførbare ferdigstillingsrapport og AIP-pakking med
   definert, verifisert evidensutvalg, manifest og kontrollsummer.

## Sikkerhet og begrensninger

- Source forblir urørt. Ingen Work-indeks omskrives av denne visningen.
- Utkastprofil er alltid `approved: false` og kan ikke erklære kravoppfyllelse.
- Registrert test eller grønn arbeidsflyt er ikke godkjent teknisk kontroll.
- `required` + registrert evidens er ikke det samme som bestått påkrevd test.
- Faglig godkjenning, arkivskapers aksept og AIP-klarhet forblir ukjent.
- Forskjellen mellom **testutfall**, **faglig vurdering** og **godkjenning**
  er et fast premiss også i senere rapporter.

## Videre backlog

Fortsett fra den konsoliderte planen i
`docs/DWM-BACKLOG-CONSOLIDATED.md` og prosessbeskrivelsen
`docs/NOARK5-CONTROL-TO-PRESERVATION-ROADMAP.md`. Deres formål endres ikke
i a8. GUI-gjennomgang må også forbedre for lange knapper i små vinduer,
nettverksfilvelgerens opplevde ventetid og menyplassering på flere skjermer.
