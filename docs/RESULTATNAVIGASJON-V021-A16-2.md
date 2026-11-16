# v0.2.1-a16.2 – knapper for faglig vurdering

## Formål

Under **Resultatvisninger → Faglig vurdering** erstattes nedtrekket «Visning» med
to tydelige, sideordnede knapper: **Periodevurdering** og **Depotvurdering**.
Valgt visning er markert. De opprinnelige resultatfanene og all faglig informasjon
beholdes uendret.

## Endringer

- To eksklusive, kontrastmarkerte og tastaturtilgjengelige knapper.
- Direkte navigasjon til eksisterende Periodevurdering/Depotvurdering.
- Synkronisering når faner åpnes programmatisk eller via andre DWM-handlinger.
- Siste valgte faglige visning beholdes når brukeren går til en annen gruppe og tilbake.
- Nedtrekk under Oversikt, Eksterne kontroller og Rapporter og evidens beholdes.
- Ingen endring i testmotorer, Work-hendelser, metadata eller rapporter.

## Installasjon / verifikasjon

1. Pakk `v0.2.1-a16.2.zip` over installert `v0.2.1-a16.1`.
2. Kjør `test.bat` og kontroller at testkjøringen er grønn.
3. Åpne et uttrekk og **Resultatvisninger → Faglig vurdering**.
4. Klikk **Periodevurdering** og deretter **Depotvurdering**. Bekreft at riktig
   eksisterende visning åpnes og at aktiv knapp er tydelig markert.
5. Bytt til en annen hovedgruppe, og tilbake til **Faglig vurdering**. Bekreft
   at siste vurderingsvisning åpnes.
6. Kontroller at de andre hovedgruppene fortsatt viser sine nedtrekk.

## Tester

`tests/test_v021_a16_2_review_navigation_buttons.py` omfatter kildeintegritet,
direkte knappvalg, markering, programmatisk synkronisering, historikk for
navigasjonsvalg og tilbakekompatibilitet med andre resultater.

Lokalt: 118 målrettede tester fra a12 til a16.2 bestått. Komplett `test.bat`
og visuell Windows-QT-kontroll utføres på operatørens maskin før commit.

**Versjon:** Programmet forblir `v0.2.1-a16`. `a16.2` er en inkrementell
rettingsdelta. Den planlagte releasen skal hete `v0.2.1`, ikke `v0.1.21`.
