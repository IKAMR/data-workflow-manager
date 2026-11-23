# v0.2.0-a4 – testplan etter delta

Baseline GitHub main: `406fbcea2982e1199315d02f39f501af7b076d1c` (a3).

1. Pakk ut ZIP i repo-roten. Kjør `test.bat`; krev 0 feil. Kjør `start.bat`.
2. Velg arbeidsprofil **Depot – produksjonslinje** og modenhetsfilter **0**
   eller **1**. Åpne en lagret jobb og trykk Startside → Rapportering.
3. Verifiser at jobb-ID, Work-sti og rapportstatus gjelder aktiv jobb.
   Teknisk status er **ikke** det samme som faglig depotstatus.
4. Åpne **Resultatvisninger** og **Faglig depotvurdering**. Den siste skal
   åpne eksisterende depotfane (uttak/arkivdeler) med synlig grunnlag.
   Ikke lagre produksjonsbeslutninger for å teste GUI-navigasjonen.
5. Åpne **Lag rapport / samlerapport** og **Kanoniske resultatdata**;
   avbryt skriverelaterte valg om ingen rapport skal genereres.
6. Gå fra Rapportering til Bevaring. Kontroller at eventuell
   `preservation_staging/dwm-aip-candidate-v1` vises som **ikke verifisert**
   før særskilt integritetskontroll. DIAS AIP opprettes **ikke** ved navigasjon.
7. Trykk **Til Kontroll**; kontroller at gamle dockpaneler gjenopprettes i
   Avansert modus. Gjenta med Startside → Bevaring → Rapportering → Kontroll.
8. Med en jobb uten depotrapport: Faglig depotstatus skal vise
   **Ikke faglig vurdert**, aldri automatisk akseptert.
9. Unngå å kjøre DIAS AIP-pakking eller teste mot produksjons-SIP i denne
   GUI-røykprøven. Full Ingest-test ble utsatt i a3 og er fortsatt utestet.

Automatiserte a4-tester dekker manglende rapport, lagrede faglige statuser,
arkivdelvurderinger, avvikende rapportversjon, utrygge rapportreferanser,
evidenskandidat uten manifest eller uten kontroll, navigasjon, og
versjon/distribusjon.
