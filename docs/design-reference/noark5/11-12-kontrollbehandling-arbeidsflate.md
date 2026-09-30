# Kontrollbehandling – visuelle målreferanser for a22

Disse to bildene er konseptskisser generert under utviklingen før a22.4. De er ikke skjermbilder av ferdig implementert funksjonalitet.

- `11-kontrollbehandling-arbeidsflate-mal-a.png` er hovedreferansen for arbeidsflaten: kontrolltre til venstre, resultat/evidens i midten og valgfri faglig vurdering til høyre.
- `12-kontrollbehandling-arbeidsflate-mal-b.png` er en supplerende variant som tydeliggjør status, relaterte kontroller, vurderingspunkt og fremdrift.

## Prinsipper som skal videreføres

1. Kontrollbehandling er først og fremst et analyse- og orienteringsverktøy. Brukeren skal kunne undersøke kontrollene uten å måtte skrive kommentarer.
2. Kontrollresultat, faglig vurdering og vurderingspunkt er tre ulike nivåer. Bare relevante funn skal løftes til vurderingspunkt.
3. Evidens skal vises i kontekst for valgt arkivdel og valgt kontroll. Rå kildedata endres ikke av faglig behandling.
4. Arbeidsflaten skal alltid vise hvor brukeren er: valgt arkivdel, kontrollgruppe, kontrollnummer, behandlingsstatus og samlet fremdrift.
5. Kontrollvisningen skal kunne tilpasses datatypen. Fordelinger, perioder, metadata og kildeutdrag bør presenteres forskjellig når datagrunnlaget tillater det.
6. Behandlingsvinduet er et normalt Windows-vindu med minimer/maksimer/lukk, åpnes maksimert som standard og skal presenteres foran Resultatvisninger ved åpning uten permanent always-on-top.

## a22.4

a22.4 begynner å materialisere denne strukturen: filtrerbart og grupperbart kontrolltre, tydelig valgt kontroll, faner for resultat/evidens, beskrivelse, relaterte kontroller og vurderingspunkter, samt valgfri faglig behandling. Videre a22.x skal gjøre midtfeltet stadig mer kontrollspesifikt og visuelt.
