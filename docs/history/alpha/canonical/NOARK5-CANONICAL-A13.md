# Kanonisk resultatmodell – v0.1.15-a13

## Utvidet kvalitetssikringsrapport for arkivskaper

Eksisterende handling **KS-rapport til arkivskaper (utkast)** genererer fortsatt `Work/noark5_reports/QUALITY_ASSURANCE_DRAFT.html`. a13 utvider **innholdet**, ikke rapportmalen eller beslutningsprosessen.

- Synlig toppfelt viser `Data Workflow Manager (DWM)` og faktisk applikasjonsversjon fra `version.py`.
- `LABEL / leveranse-ID` hentes bare fra den kanoniske modellens `extraction.delivery_id`. Tom verdi blir «Ikke dokumentert»; ingen gjetning fra mappenavn eller arbeidsjobb.
- Toppfeltet forklarer skillet mellom **malbasert** tekst og **uttrekks-/evidensbasert** innhold.
- Identitet/proveniens: bekreftede eller ikke-bekreftede felt i kanonisk indeks vises separat fra Arkades rapporterte arkivskaper, system og periode. Et DWM job-ID er **ikke** verifisert kildeproveniens.
- Arkivdeler presenteres på egne linjer med `systemID`, rapportert status, antall mapper fra Arkade-test `N5.10`, og funn fra `N5.15` / `N5.22`. Arkivdelenes individuelle perioder utledes **ikke** fra Arkades overordnede periode.
- DWM-tall fra `kdrs.c02` gjengis som egen navngitt resultatkilde og **summeres ikke** med Arkade-tall.
- PRONOM-statistikk (inkludert `RAF-220301`, `Format-ID`, type, versjon og antall) vises som **kildetall**, ikke en depotgodkjenning eller integritetstest.
- Manglende kilde gir en eksplisitt mangel-/avklaringsmelding, ikke oppdiktede nuller eller automatisk beståttstatus.

Rapportens nye seksjoner kommer **etter** kontrolloversikten og konkrete Arkade-funn, **før** spørsmål og signatur-/avklaringsfelt.

## Kildesikkerhet og avgrensning

Bare operatorvalgte, analyserte eksterne filer som fortsatt samsvarer med lagret SHA-256 åpnes for detaljert rapportinnhold. DWM kontrollerer at kildefilen fortsatt ligger inne i valgt Work, og avviser fil-symlinker og filer over 30 MB. Rader og overskrifter HTML-escapes.

`canonical-results.json`, `canonical-external-analysis.json`, kildene, vurderingshistorikken og Source endres ikke. Generering av utkast registrerer **ingen** arkivskaperaksept, depotgodkjenning, journalføring eller beslutning om bevaring. Arkivdelstatus og antall er fortsatt eksternt rapporterte opplysninger som krever faglig vurdering.

## Avgrensninger / videre arbeid

- Ingen godkjent komplett kontrollprofil ennå.
- Ikke alle Noark 5-tall eller metadata har proveniens/verifikasjon i kanonisk modell; manglende felt markeres.
- Arkivdelvis periode, dokumentmigrering og faktiske antall fra andre DWM-tester krever videre dokumentert kildetilknytning.
- Arkivskapers tilbakemeldinger og depotets beslutning er et senere, selvstendig trinn (a14).
- Rapportens layout/mal, LABEL-identitet og journalføringsintegrasjon finjusteres senere mot faktiske organisasjonskrav.

## Testing

Nye regresjonstester dekker arkivdelindeks, kildehash, manglende valg, sikker HTML-escaping, separat antall og ingen utledet arkivdelperiode. Test med de to faktiske, lokalt opplastede 1525_004-eksemplene viser fire arkivdeler og 12 PRONOM-rader/704 filer. Ingen uttrekksdata eller reelle evidensfiler er inkludert i repo-deltaen.
