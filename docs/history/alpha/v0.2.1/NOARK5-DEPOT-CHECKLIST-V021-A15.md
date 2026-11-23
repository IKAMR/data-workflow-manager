# DWM v0.2.1-a15 – depotets sjekkliste og METS-kontekst

## Avgrensning

Integrert, manuell sjekkliste i **eksisterende Resultatvisninger → Faglig vurdering → Visning: Depotvurdering**. a15 bruker de to foreløpige dokumentene:

- `docs/reference-material/checklists/sjekkliste-mets.docx` – **hovedstruktur og formuleringer** (METS-header, kontrollpunkt og fritekst).
- `docs/reference-material/checklists/sjekkliste.docx` – eldre utkast, fremdeles tilgjengelig som **kildereferanse**, ikke en konkurrerende sjekkliste.

Begge er *utkast*. Referanser til arkivforskrifta §§ 23 og 26–34 gjenspeiler dokumentenes faglige referanseramme, ikke automatisk bindende krav for kommunale depot. DWM gjør dem ikke om til nye normative regler. Spørsmål om nye bindende kontrollregler avklares særskilt med prosjektansvarlig.

## Brukerflate – eksakt sti

1. Åpne DWM og velg jobben `JOB-001 – content` i jobblisten.
2. Klikk **Resultatvisninger**.
3. Velg toppfanen **Faglig vurdering**.
4. Under **Visning:** velger du **Depotvurdering**.
5. Velg raden **JOB-001 – content** for hele uttrekket, eller velg en navngitt arkivdel med system-ID.
6. Nederst, **ved siden av** knappen **«KS / depot: vurder funn og lag rapporter…»**, klikker du **«Sjekkliste / METS…»**.

Sjekklistevinduet har **to faner**:

- **Kontrollpunkter:** 49 eksplisitte kontrollpunkter fra METS-utkastet, ordnet i områdene opplysninger, arkivpakken, avklaring/godkjenning, database/SIARD, format, tegnsett, teknisk beskrivelse, koblinger, kryptering og øvrige sjekkpunkt. I tillegg 8 fritekstfelt om systemhistorikk, uttrekksmetode, periode, kjente avvik, Noark 5-funn, Noark 5-oppsummering, gjennomført testing og samlet faglig vurdering (ikke vedtak). Bruk `Område` eller `Søk`. Feltet **Svar** har `Ikke vurdert`, `Ja`, `Nei`, `Ikke relevant`; fritekstfeltene har bare `Faglig tekstfelt`. `Nei`, `Ikke relevant` og fritekst krever begrunnelse. Ingen status fylles automatisk fra tekniske resultater.
- **METS / kildedokumenter:** 21 metadatafelter fra sjekklistens METS-header med separate kolonner for *registrert i Work* og *bevart info.xml*. Blant annet `METS LABEL`, `DELIVERYSPECIFICATION`, `ARCHIVIST`, `IPOWNER`, `SUBMITTER`, `CREATOR`, arkivsystem/-versjon, uttrekksverktøy, `STARTDATE`/`ENDDATE`, pakke-ID `OBJID` og `CREATEDATE`. Feltene skal ikke utledes fra LABEL når de finnes som egne METS-opplysninger. Avvik mellom faktisk sammenlignbare felter synliggjøres. Begge opprinnelige DOCX-utkastene kan åpnes via knapper; ikke rediger kildene som del av denne arbeidsflyten.

**Noark 5-funn skal ikke registreres på nytt i sjekklisten:** a13s per-funnkommentarer
og originale Arkade-/DWM-resultater er fortsatt primærgrunnlaget. Bruk
Noark 5-fritekstfeltene bare til særskilt oppsummering og henvisning.

Hver manuell registrering gjøres med **«Lagre sjekkpunktvurdering»**. Eksisterende DWM-brukerprofil gjenbrukes, uten å opprette en ny identitetsmodell. Velg uavhengig om **kommentaren** skal følge med i KS-rapporten og/eller depotrapporten. Standard: depotrapport ja, KS-rapport nei. Et kontrollpunkt kan oppdateres, men forrige hendelse blir bevart.

## Kildetilknytning og Work-historikk

Lagring skjer append-only i den valgte jobbens `Work/noark5_evidence/depot_checklist_events_v021_a15/<UUID>.json`. Hver hendelse har egen SHA-256-integritet og identifiserer bruker, tid, uttrekkets varige jobb-UID, SHA-256 for eksakt original `depot_validation_report.json`, katalogversjon, kontrollpunkt-ID, omfang (`uttrekk` eller `arkivdel`), arkivdelens system-ID, J/N/ikke relevant/notat, begrunnelse og rapportmottaker.

**Eldre vurderinger gjelder ikke automatisk ny kildeversjon eller endret sjekklistekatalog.** Sjekklistemodulen avviser ukjent/endrede hendelser, ugyldige vurderingsomfang, feil brukeridentitet, symlink-omdirigering og ugyldig rapporttilknytning.

METS-panelet bruker bare Work-registrerte metadata og SHA-256-verifisert **bevart kopi** av `info.xml`, aldri opprinnelig Source som skrivemål. Metadata uten dokumentasjon vises som ukjent, ikke som `Nei` eller `Ja`. Kildenes verdier slås ikke automatisk sammen. Merknader skrives aldri tilbake til `info.xml`, `arkivstruktur.xml`, opprinnelige depotrapporter eller eksterne testresultater.

## Eksisterende rapportmotor (a12/a13/a14/a20)

**Ingen ny rapportgenerator:** `build_review_snapshot()` utvider samme a12/a13/a14-rapportgrunnlag med et avgrenset `a15_checklist`-objekt. a12s **eksisterende** to HTML-rapporter får nå en seksjon **12**:

- **KS-rapport:** bare kontrollpunkt/notat som manuelt er valgt «Ta med i KS-rapport».
- **Depotrapport:** kontrollpunktene/notatene manuelt valgt til depotrapport; i tillegg framgår antall manuelt vurderte kontrollpunkter på *uttrekksnivå* av 49. Ikke-vurdert betyr aldri bestått.

`rapportgrunnlag.json` inneholder bare valgte tekstverdier; intern, ikke-valgt kommentar forblir i Work. Alle eksportfiler ligger i den samme a13-rapportpakken, med eksisterende SHA-256-manifest. **a20 Full-rapport og vedlegg A–D beholdes uendret** og genereres via samme etablerte tjeneste. Ingen formell godkjenning, arkivskapersvar, periodereparasjon, automatisk retting eller nye Noark-tester.

## Praktisk Windows-test

1. Pakk a15-deltaen over **committet a14**, og kjør `test.bat`.
2. Start DWM og følg **eksakt GUI-sti** ovenfor.
3. På **Kontrollpunkter**, filtrer `Database / SIARD` og velg punktet **«SIARD-validering er gjennomført der SIARD brukes»**. Velg *Ikke relevant*, begrunn med at dette uttrekket er et Noark 5-uttrekk, og klikk **Lagre sjekkpunktvurdering**. Velg depotrapport, ikke KS-rapport (test av mottakervalg).
4. Velg fanen **METS / kildedokumenter**. Kontroller at `1525_004` viser separate `METS LABEL` og `Innleveringsspesifikasjon`; `OBJID` og `CREATEDATE` fra den bevarte XML-kopien; `ARCHIVIST`, `IPOWNER` og `METS CREATOR` er separate. Verifiser at eventuelle kildemotsetninger blir vist, ikke automatisk vurdert som feil.
5. Tilbake på **Kontrollpunkter**: velg `Faglige tekstfelter / Noark 5` og **«Noark 5-avvik / vurderingspunkter»**. Skriv et *testnotat* med henvisning til N5.22, velg bare depotrapport og lagre. Ingen godkjenning skal oppstå.
6. Lukk sjekklisten. Klikk **«KS / depot: vurder funn og lag rapporter…»** i Depotvurdering.
7. Klikk **«Velg mål…»**, velg ny rapportmappe, deretter **«Lag KS + depot + Full-rapport (a20)»** og **«Åpne siste rapportpakke»**. Ikke overskriv tidligere mapper.
8. Verifiser at depotutkastet har **seksjon 12** med vurderingene, KS-rapporten ikke viser depot-interne notater, Arkades N5.22 fremdeles er `ERROR`, og a20 Full + vedlegg A–D er uendret. Pakk gjerne rapportmappen som ZIP for kontroll.
9. Prøv et annet uttrekk/arkivdel. Tidligere svar må ikke følge med på tvers av jobb-UID eller system-ID.

## Testdekning og avgrensninger

- **66 målrettede tester** er bestått i utviklingsmiljøet: 46 tidligere a12–a14 og 20 nye for a15. Testene omfatter kildeversjon, historikk, Work-identitet, brukeridentitet, manuell begrunnelse, mottakervalg, HTML-escaping, symlink, manipulert hendelse, METS-original kontra Work, original SHA-256, XML DTD-avvisning, a13-rapportpakke og uendret teknisk status.
- Et reelt **lagret `1525_004` Work-eksempel** ble kontrollert. Bevarte METS-data gav `OBJID`, `CREATEDATE`, perioden og rolleopplysninger uten nye valideringer. En testeksport med to manuelt registrerte sjekklistepunkter beholdt begge mottakerprofilene og et verifiserbart rapportmanifest.
- Full **Windows `test.bat` og PySide6 GUI-funksjonstest må gjøres av operatør** før commit. PySide6 er ikke tilgjengelig i utviklingsmiljøet for direkte GUI-prøve.
- **Videre (a16/a17):** arkivskapers svar, saksbehandling av restavvik, formaliserte beslutninger og signering. Oppslag i konkrete XML-forekomster fra N5.22 samt kontrasterende dialogrammer og «Åpne mappe»-knapper står fortsatt på ToDo.
