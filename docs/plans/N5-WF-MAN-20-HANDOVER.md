# N5 WF Man 20 – videreføring etter utviklingsdelta a20

**Oppdatert:** 2026-10-19. **Baseline:** a19 commit `b03cb2d`.
**Delta:** v0.1.7-a20, levert for testing (ikke committet eller pushet).

## Metodikk

- Sammenlign endringer med faktisk GitHub-baseline og repoets arkitektur/
  utviklings-/testdokumentasjon.
- Lever én overlay-ZIP med **bare** endrede/nye filer og samme relative stier.
- Ingen installer-/apply-skript og ingen endringer i uttrekksdata.
- Bruker tester med `test.bat` og reelle Windows-jobber før commit/push.
- Skill fokustest i utviklingsmiljø fra komplett Windows-test.
- Ikke mist `save_part_assessment`, `load_part_assessment`, KDRS U2-tilordning
  eller 43 arkivdeler i 1502_024: `a18-fix12` må **ikke** installeres.

## Hva som er lagt i a20

1. Ny `report_service_a20.py` – ett API for eksport HTML/PDF/JSON/CSV.
2. Ny `report_model_a20.py` – felles faglig rapportmodell per jobb og arkivdel.
3. Ny `report_views_a20.py` – korrigert faglig periodestatus, kompakt arkivdel-
   indeks og CSV med null/mangler atskilt.
4. `gui/report_selected_dialog_a16.py` bruker nå felles rapporttjeneste og
   tilbyr CSV. Eksisterende Enkel/Medium/Full og Vurder ytterår bevares.
5. `version.py` viser a20. Regresjonstester og arkitekturdokumentasjon følger med.

## Det som ikke skal blandes sammen

- `1502_023` er ePhorte MEI, `1502_024` er ePhorte MK. Historisk Arkade-fil
  med `mei` registrert ved `mk` må undersøkes ut fra reelt innhold, ikke bare
  filnavn. Ingen import fjernes automatisk.
- MK: dokumentert 43 arkivdeler. KDRS Standard/U1 samsvar for fem hovedtall,
  U2 er avstemt per arkivdel. Det er historisk kontrollgrunnlag; det er ikke
  bevist at andre uttrekk har samme kvalitet.
- Oppgitt arkivuttrekksperiode, observerte XPath/KDRS-ytterår og faglig
  godkjent produksjonsperiode er **tre forskjellige størrelser**.
- SIARD/Noark 4 er parallell evidens som skal integreres senere, ikke i a20.

## Prioritert reell test etter delta

1. `test.bat` og GUI oppstart på IKAMR-K21.
2. `1502_024` rapport og periodevurdering – hele uttrekket **før** arkivdeler.
3. 6 uttrekk `1502_023–028` – samlet rapport og korrekte kildevalg.
4. 28 uttrekk `1502_029–056` på IKAMR-K18.
5. Blandede 1535/1539/1543/1545/1547 i én jobbliste (og andre 1502 ved behov).

**Tester i leveranse:** lokale isolerte service-/formatregresjoner; ikke full
`test.bat`, ikke reelle depotdata. Reell akseptanse må gjennomføres på Windows.

## Neste etter godkjent a20

- Håndtere globalt unik jobbidentitet for rapportering på tvers av jobblister.
- Fjerne siste dupliserte rapportoppslag i eldre individuelle GUI-flater ved
  å føre dem over på det samme tjeneste-API-et.
- Forbedre faglig periodekildevalg, beslutningsproveniens og eventuelle
  manglende arkivdelvise årsfordelinger uten å kjøre alle analyser på nytt.

## Oppdatering 2026-10-19 – a20.1 innholdsprofil (før commit)

- Bruker testet a20: 2219 kjørt, 2217 bestått, 0 feil, 2 hoppet over.
- a20.1 er en **delta oppå a20**, ikke en delta direkte oppå a19.
- Gjenbruk eksisterende `report_service_a20.py` og autoritative a19-rapporter.
  Ikke innfør parallell innsamling av samme opplysninger.
- Nye adaptere: `report_content_a201.py` (lagrede normale C/F XPath-resultater,
  kontrollerte jobbspesifikke kjørebaner) og `report_content_views_a201.py`
  (én felles innholdsprofil i HTML/PDF/JSON/CSV).
- Hovedrapport: Medium får JP-type og andre hovedfordelinger; Full får kilde-
  og kategoridekning. Vedlegg A: uttrekksdetaljer. Vedlegg B: native system-ID.
- Eksterne KDRS og Arkade-kilder skal ikke presenteres som DWM XPath eller
  summeres inn i denne innholdsprofilen uten verifisert semantikk.
- Bevar eksisterende vurderingsdialog, manuelle perioder, a20-CSV-skjemaer,
  øvrige rapportfiler og alle tidligere a20-testkontrakter.
- Ingen commit/push fra assistenten. Full Windows-test og reell kildetest må
  gjennomføres av brukeren før commit.

## Oppdatering 2026-10-19 – a20.2 rapportlesbarhet (før commit)

- Utgangspunkt: a20.1 installert, samlerapport for seks uttrekk levert som
  `index.html` + Vedlegg A–D. Brukeren fant fire lesbarhetsproblemer.
- a20.2 installeres **over a20.1**. Nye `report_layout_a202.py` er kun siste
  presentasjonsadapter i felles `report_service_a20.py`.
- Global JOB-kolonne på én linje; tolinjede kolonneoverskrifter; egen
  horisontal HTML-tabellrulling ved mange tallkolonner.
- Vedlegg D: KDRS-årsdata får separate SVG-diagrammer for hver kilde/serie;
  originaltabellene bevares i utvidbare HTML-seksjoner. `Kan ikke vurderes`
  fra eldre XPath-only-tabell vises ikke som faglig sperre når KDRS er tilgjengelig.
- Vedlegg C: jobb-/uttrekksnavigasjon, sticky kontekst, innfoldede store
  kontroll-/KDRS-tabeller og 43 konkret navngitte U2-kildearkivdeler for JOB-002.
  Ikke anta at U2-nummer er lik DWM `system_id`.
- Ingen endring av JSON-fakta, CSV-kolonner, rapporttotaler, ekstern evidens,
  manuelle beslutninger, importfunksjoner eller analyser.
- Test i Windows med `test.bat` og 1502_023–028 først; sjekk særlig 1502_024,
  PDF-tabellbredder, 28-jobb-rapport og blandet jobbliste etterpå.
- Full dokumentasjon og godkjenning av PDF-layout er ikke utført på Windows.

### a20.3 – K18 diskbrudd under 28-jobbs samlerapport
- Screenshot: `Kunne ikke lage rapport: [Errno 22] Invalid argument`.
- Ikke dokumentert om dette var frakobling eller en annen fil-/sti-feil.
- Ny `report_recovery_a203.py`: bakgrunnsrapport, vent/gjenoppkobling,
  lokal staging og kontrollert atomisk filpublisering, lokal JSONL-logg,
  stopp fra GUI og kontroll av volumidentitet på Windows.
- Samme sentrale `report_service_a20` og tidligere a20.2-oppsett beholdes.
- Ingen data eller kildevurderinger endres. K18 testes med 28 valgte jobber,
  helst eksport til frisk lokal C:-mappe, og `test.bat` må kjøres på klienten.
- Full OS/USB-avbruddstest på Windows kreves; simulerte feil er dekket av
  `tests/test_a20_3_report_recovery.py`.
