Data Workflow Manager - v0.1.7-a20.2 (delta, 2026-10-19)
========================================================
FORUTSETNING: v0.1.7-a20 og a20.1 er allerede installert.
Dette er en delta over a20.1, IKKE en komplett applikasjon og IKKE en delta over a19.

Installering
------------
1. Ta backup av nåværende repo / kontrollér git status.
2. Pakk ZIP-innholdet direkte over prosjektets rotmappe.
3. Kjør test.bat som vanlig. Ingen endring i jobbdata eller uttrekksfiler.
4. Åpne jobbliste 1502_023-028, velg Rapport valgte -> Full.
5. Eksporter index + vedlegg A/B/C/D til NY mappe (eksisterende rapportfiler overskrives ikke uten bekreftelse).

Kontroller:
- JOB-001 .. JOB-006 står på én linje i alle HTML-tabellene.
- Bredt arkivdelindeks i Vedlegg B rulles sideveis, ikke med skjulte/sammenpressede tall.
- Vedlegg C har uttrekksregister, tydelig JOB-/uttrekkskontekst, 
  og kollapsede kontroll- og KDRS-tabeller. U2-indekser vises med kildearkivdeltittel.
- Vedlegg D viser stolpediagram per KDRS-årsserie der data finnes,
  og originale årsverdier ligger under «Vis opprinnelig årsopptelling».
- JOB-002 1502_024 kan faglig periodevurderes med KDRS-evidens selv uten DWM XPath.
- Ingen perioder godkjennes automatisk.

OBS: Den gamle PDF-motoren videreføres. CSV/JSON og depotvurderinger endres ikke.
Forhåndsvisnings-ZIP kan brukes til å bedømme ny HTML-layout UTEN å endre DWM.

Innhold i denne delta:
- noark5_workflow/reporting/report_layout_a202.py (ny)
- noark5_workflow/reporting/report_service_a20.py (oppdatert)
- tests/test_a20_2_report_readability.py (ny)
- docs/REPORTING-ARCHITECTURE-A20.md (oppdatert)
- docs/plans/N5-WF-MAN-20-HANDOVER.md (oppdatert)

Ingen commit/push er gjort av assistenten. Programversjon beholdes uendret
inntil bruker godkjenner neste commit.
