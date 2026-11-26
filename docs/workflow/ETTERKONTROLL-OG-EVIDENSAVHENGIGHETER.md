# Etterkontroll og avhengig etterbehandling

## Bakgrunn

Funksjonaliteten ble innfort i DWM v0.2.7-a15. Dette dokumentet beskriver
den varige arbeidsflyten, og er ikke et per-alpha endringsnotat.

En ferdig hovedkontroll (f.eks. JOB-001, 13/13) kan mangle A140 Siegfried,
eller en tidligere teknisk deljobb ma kores om igjen etter en feilretting.
Det er ikke riktig a nullstille og gjenta alle fullforte kontroller.
Det er heller ikke riktig a beholde utdatert rapportgrunnlag etter at en
ny teknisk evidenskilde er laget.

## Bruk

1. Apne den tidligere lagrede `.n5jobs`-listen og velg **3. Kontroller / kjor**.
2. Velg **Legg til / kjor deljobb pa nytt...**. Avansert modus har samme
   handling i Kjor-menyen og pa valgte deljobber i Arbeidsflyt-panelet.
3. Velg **A140 Siegfried** og ett eller flere uttrekk.
4. La **Oppdater avhengig evidens og rapporter automatisk** vaere avkrysset.
5. Kontroller den viste planen, godkjenn eventuelle forhandsadvarsler, og start.

For en historisk 13-deljobbs Noark 5-arbeidsflyt med A210-A260 allerede
registrert vil DWM kjore A140 og deretter A210, A220, A230, A240, A250 og
A260 i avhengighetsrekkefolge. Arkade 5, XML/XSD og XPath blir ikke kjort
om igjen i dette eksemplet. Original status (13/13, Ferdig) bevares.

## Historikk, feilhandtering og etterkontrollstatus

En egen `dwm_a15_aftercare`-registrering i Work-jobbens `operation_params`
lagrer kilden som ble kjort, identiteten pa den nye kjoringen, hvilke
etterjobber som er fullfort, og hvilke som gjenstar. Kjoringene har egne
subjob-logger i Work. Den eldre workflow-listen og kjorecursoren endres ikke.

Hvis en etterjobb feiler, stoppes bare den avhengige kjeden for dette
uttrekket. De resterende etterjobbene markeres som utdatert/venter.
Dialogen kan deretter fortsette ufullstendig etterbehandling uten a gjenta
A140, forutsatt at kildekjoringen ble dokumentert som fullfort.
Andre valgte uttrekk behandles separat.

A210 kontrolleres mot *den nye* Siegfried-kjoringens manifest og SHA-256.
A230 normaliserer den gamle `not_configured`-klassifiseringen for en
verifisert Siegfried-tilleggskilde, med versjonert arkivering av opprinnelig
revisjonsfil. A250 og A260 bruker deretter det oppdaterte grunnlaget.

Hvis en annen teknisk deljobb kjores selektivt, beregnes samme graf av
etterkommere, men statusen er konservativ (`kontroller kildevalg`) dersom
kildetilknytningen ikke verifiseres like spesifikt som A140.

### Avgrensninger

- Deljobber som ikke var konfigurert i den historiske jobben, opprettes ikke
  usynlig som etterjobber. De vises som manglende; en slik jobb merkes ikke
  automatisk `oppdatert`.
- Deljobber som ennå ikke er fullfort i hovedarbeidsflyten, kjores ikke
  utenom denne. De vil fortsatt kreve ordinart fortsett fra hovedjobben.
- Faglig godkjenning blir aldri gitt automatisk.
- Uendrede resultatfiler beholdes av DWM; aktuelle etterjobber kan publisere
  nye Work-resultater og bruker eksisterende versjonering/historikk.

## GUI i Enkel modus

Kontrollgrupper og automatisk vindusapning vises side om side pa store
vinduer og under hverandre pa smale vinduer. Etterkontrollstatus vises
separat fra statusen for hovedkontrollen. `Kjor alle klare (0)` og
`Fortsett og kjor resterende (0)` tar ikke plass nar de ikke er aktuelle.
Avansert valg for rekkefolge og a7-etterbehandling er samlet i `Flere valg`.

## Test

Kjor `test.bat` pa Windows. Verifiser i GUI at tre gamle, ferdige jobber
fortsatt er 13/13 for og etter en tilleggskjoring av A140, og kontroller
A210-A260 i Work-kjoreloggene. Test stopp/fortsett, og at Source er uendret.
