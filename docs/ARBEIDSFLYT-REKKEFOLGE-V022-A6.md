# DWM v0.2.2-a6 – brukerbestemt rekkefølge på deljobber

**Delta over GitHub `main` `95ef735a1987078112648a6e8a4a2cdbdfd7b021` (committet a5).**

## Endringer

- **Avansert modus:** `Kjør → Endre rekkefølge på deljobber…`, samt `Endre rekkefølge…` i Arbeidsflyt-panelet.
- **Enkel modus:** `3. Kontroller / kjør → Endre rekkefølge på deljobber…`.
- Dialogen lister kun operasjonene som allerede er valgt for **den aktive JOB**. Velg en deljobb, flytt med **Opp/Ned**, eller bruk **Arkade-testene sist**. `Tilbakestill` forkaster endringene i den åpne dialogen.
- **Arkade-testene sist** flytter `arkade5_noark5_test` til nest siste og `arkade5_pronom_analysis` til siste plass, hvis begge er med. Resten beholder sin interne rekkefølge. Presetet er **ikke automatisk**; operatøren velger selv.
- `Lagre rekkefølge` bruker **eksisterende `DwmWorkbenchAPI.set_workflow`**, etterfulgt av **eksisterende `save_job_list`**. For Work-first jobber oppdateres den autoritative jobbdefinisjonen i Work, og `.n5jobs` er indeks. Ingen alternativ jobbliste eller lagringsformat introduseres.
- Enkle kontrollgrupper (avkrysning) bestemmer hvilke tester som er valgt. **Ved samme medlemskap bevares manuelt valgt rekkefølge** ved lagring, jobbytte og start. Hvis kontrollgruppene endres, bygges den nye listen fra profilvalgene; rekkefølgen kan deretter tilpasses igjen.
- Hver JOB har uavhengig rekkefølge. Ingen annen jobb i listen modifiseres.
- Pågående jobb kan **ikke** redigeres. På tidligere kjørt jobb må operatøren bekrefte at endringen nullstiller kjørestatus/kontrollpunkt for ny kjøring. Eksisterende tidligere resultater slettes ikke.
- Eksisterende standardprofiler, Qt-oppstartslogikk, Siegfried a5 og andre kjøremotorer er ikke endret.

## Viktig om Arkade-testene til slutt

Hvis `arkade5_noark5_test` og `arkade5_pronom_analysis` plasseres som deljobb 9 og 10 i en 10-stegs arbeidsflyt, kjøres **Arkade-import, resultatvisninger og depotrapport før de nye Arkade-kontrollene**. DWM kan derfor fullføre teknisk, mens den tidlige depotrapporten *ikke inkluderer nye Arkade-funn fra samme kjøring*.

Dialogen advarer ved denne rekkefølgen. Etter siste Arkade-test kan operatøren kjøre **Finn/importer Arkade 5-resultater**, **Noark 5 views/compositions** og **Noark 5 depotvalideringsrapport** som selektive deljobber i Avansert modus, dersom rapporten skal inkludere det nye Arkade-grunnlaget. Dette er ikke automatisk i a6.

Rekkefølgekontrollen er med vilje ikke en automatisk utledning av Noark-standardens faglige godkjenning. Kontrollstatus `Ferdig` er ikke depotgodkjenning.

## Filer i deltaen

- `app/workflow_order_v022_a6.py` – rene rekkefølgeregler, medlemskap og faglige advarsler
- `gui_qt/workflow_order_v022_a6.py` – Qt-dialog og lagring via eksisterende API
- `gui_qt/main_v020_a6.py` – snarveier i begge modus, ingen nye oppstartstimere
- `app/basic_multijob_v022_a1_2.py` – bevar manuelt valgt rekkefølge i Enkel modus
- `app/basic_start_v0111_a1.py` – eksisterende jobb gjenkjennes på *samme kontroller*, selv om rekkefølgen er annen
- `version.py` / `pyproject.toml` – v0.2.2-a6 / 0.2.2a6
- `tests/test_v022_a5_version_metadata.py` – a5-minimumskrav fremfor eksakt a5, fortsatt streng kilde-/distribusjonsidentitet
- `tests/test_v022_a6_workflow_order.py` – nye a6-regresjonstester

## Lokal kvalitetssikring

29 målrettede tester bestått (16 nye a6 + 2 a5-versjonskontroller + 11 etablerte flerjobbtester). Alle endrede Python-filer er syntakskontrollert. Qt/PySide6 kan ikke kjøres i Linux-testmiljøet her, og komplett Windows-`test.bat` er derfor ikke verifisert som del av leveransen.

## Praktisk test

1. Avslutt **pågående a5-kjøring** før a6-filene installeres.
2. Pakk ut ZIP-en over committet a5, start DWM.
3. Velg en **ny eller ikke-startet** jobb; i Enkel modus velg de ønskede kontrollene først.
4. Gå til `3. Kontroller / kjør → Endre rekkefølge på deljobber…`.
5. Klikk **Arkade-testene sist**, og se at Arkade Noark5-test er nest sist og Arkade PRONOM sist.
6. Klikk **Lagre rekkefølge**, lukk og åpne kontrollen på nytt. Kontroller rekkefølgen også fra Avansert modus.
7. Test **Lagre**, bytt mellom JOB-001 og JOB-002 og tilbake: kun den valgte jobbens rekkefølge skal ha endret seg.
8. Gjør en prøverunde på liten jobb før endring på stor jobb. Verifiser særskilt at import-/rapportsnapshotene stemmer med faktisk kjørerekkefølge.

Ingen Git-commit eller push er utført av leveransen.
