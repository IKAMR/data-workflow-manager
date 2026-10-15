# N5 WF Man 19 - utviklingsstatus og overlevering

Oppdatert 2026-10-14. Gjelder IKAMR/data-workflow-manager.

## Fast arbeidsavtale for alle neste tråder

1. **Utvikle fra siste faktiske commit på `main`.** Kontroller SHA og diff før arbeid.
2. **Lever delta-ZIP med kun nye/endrede filer i repository-strukturen**. ZIP skal pakkes rett over repo-roten; ingen apply-skript, hjelpe-BAT eller unødvendige mellomfiler.
3. **IKKE commit eller push.** Bruker kjører `test.bat`, tester i Windows, og committer/pusher selv. Foreslå kort, norsk committekst når leveransen skal committes.
4. Hold hvert steg lite, isolert, testbart og bakoverkompatibelt. Bevar eksisterende kilder, importer, rapporter, konfigurasjonsregler og lagring.
5. Dokumenter hva som faktisk er testet, og skill fokustest i utviklingsmiljø fra full Windows `test.bat`. Ikke oppgi at sistnevnte er bestått uten faktisk kjøring.
6. Alle nye tråder må først lese denne overleveringen og gjeldende kildekode. Bruk prosjektmaterialet `Data-WF-Repo_00-13.pdf` som historisk kontekst, men kodestatus i GitHub som autoritativ baseline.

## Baseline og formål

- Startpunkt: v0.1.7-a17, commit `62e886dc97d64155ffef0ede9d3e3ed9e2395319`.
- Denne deltaen: **v0.1.7-a18** (ikke committet av assistenten).
- Primærtest: 1502_024 / JOB-002 (MK, 43 arkivdeler).
- Brukerprioritet: periodevurdering for hele uttrekket, **deretter hver arkivdel**.

## Endringskontrakt a18

- Faglig periodevurdering kan opprettes og godkjennes manuelt også når DWM XPath mangler. KDRS Query Standard/U1 er separat periodeevidens, ikke automatisk DWM XPath eller faglig godkjenning.
- Uttrekksvurdering lagres i eksisterende v1 JSON (`status`, `selected_years`, `comment`). Forlengelse `archive_part_assessments` med oppslag på **arkivdelens native `system_id`**; ingen inkompatibel schema-migrering.
- Arkivdelvurdering lagres uavhengig fra uttrekksvurderingen og fra andre arkivdeler. Eksisterende vurderinger bevares ved nye lagringer.
- GUI har eget valg **Vurderingsnivå**, separat fra KDRS/DWM-velgeren for årskilder. KDRS U2-indeks/-tittel brukes ikke som automatisk system-ID.
- Periodegrunnlag i hovedrapportens kildeoversikt, vedlegg D og strukturert JSON inkluderer både faglig vurdert uttrekksperiode og opptil 43 separate arkivdelperioder.
- Vedlegg B har faglig vurdert periode per native arkivdel, uten å endre U2-antall, DWM-antall eller kildetilhørighet.
- Verken original XML, importerte KDRS-/Arkade-data eller eksisterende depotrapport blir endret av vurderingen.

## Kjente kilder/avklaringer - 1502_024

- KDRS Standard og U1 har samsvar for hovedtallene; 43 U2-arkivdeler gir samme summer i fem målområder.
- KDRS-årsserier omfatter mulige avvik i **1899** og **2099** som må vurderes faglig, ikke automatisk forkastes.
- Arkade 5-import med `mei` i filnavn registrert i MK-jobben trenger fortsatt kildeidentitetskontroll. `mei=1502_023`, `mk=1502_024`.
- Vurdert periode må ikke arves fra oppgitt/observert periode uten aktiv faglig godkjenning.

## Tester og leveransebegrensninger

- 9 nye fokustester for scoped periodevurdering er kjørt i isolert Python-harness: **9/9 bestått**.
- Syntakskontroll av alle endrede Python-filer: bestått.
- Full `test.bat` og faktisk Windows-GUI: **ikke kjørt her** (lokalt repository og Windows-data er ikke tilgjengelige i utviklingsmiljøet). De må kjøres hos bruker.
- Historiske tester som spesifikt forventet den foreldede meldingen «Kan ikke vurderes – DWM XPath mangler», eller intern GUI-tekststruktur, er oppdatert til gjeldende funksjonskontrakt.

## Neste verifisering hos bruker

1. Pakk ut delta direkte over bekreftet a17 i repo-root og kjør `test.bat`.
2. Åpne JOB-002 og **Periodevurdering**, velg `Hele uttrekket`; kontroller at importerte KDRS Standard/U1 er synlige uten DWM XPath.
3. Sett **faglig vurderte år manuelt**, skriv begrunnelse og lagre som godkjent; lukk og åpne på nytt og kontroller at vedtaket er bevart.
4. Velg minst to ulike arkivdeler og lagre uavhengige vurderinger; kontroller at deres år ikke endrer uttrekkets eller hverandres godkjenning.
5. Generer full rapport med `index.html`, vedlegg B, vedlegg D og JSON. Bekreft riktig status og periode både samlet og per arkivdel.
6. Verifiser at Arkade 5-kildeidentiteten i 1502_024 fremdeles flagges der den bør, og at antall/omfang fortsatt stemmer.

## Videre arbeid etter Windows-test

- Sørg for at også den eldre, generelle *Jobboversikt/Periodevurdering*-kolonnen bruker samme kildebevisste status før godkjenning som den nye *Periodegrunnlag*-seksjonen. Den eksisterende `_review_status` i `job_summary_a16.py` returnerer fremdeles `Kan ikke vurderes` for manglende DWM-observasjoner før lagret vedtak. Dette er et gjenstående statuskonsistenspunkt og skal ikke skjules.
- Vurder entydig, dokumentert kobling av KDRS U2 til native system-ID der ikke nok metadata finnes, uten å tilordne automatisk ut fra rekkefølge.
- Videreføring: fler-kildesammenstilling og kildeidentitet for Arkade / KDRS / DWM; periodeprofil per arkivdel med detaljer og avvik.

## a18-fix1 – lesbar årsfordeling før periodevurdering (2026-10-15)

**Utløst av praktisk test av 1502_024:** Vurderingsvinduet viste bare
KDRS Standard/U1-ytterår `1899–2099`, mens den nederste kildevisningen
åpnet på tomme **DWM XPath**. Brukeren hadde dermed ikke det nødvendige
antall per år for å kunne vurdere avvik i ytterårene.

Rettelse (delta **oppå a18**, samme `VERSION = 0.1.7-a18`):

- Ved manglende DWM årsdata velges den første kildeavgrensede, positive
  KDRS-årsserien automatisk, med `standard` foran `u01`. Brukeren kan
  fremdeles bytte mellom alle kildene. Ingen kilde endres i lagring.
- KDRS-visningen viser full matrise med ett år per linje og egne kolonner for
  mapper/saker (opprettet), registreringer (opprettet), journalposter
  (journaldato), løpende og offentlig journal og endringslogg. Datotypene
  skal **ikke summeres**. Prosentandeler for første og siste positive år
  gjelder **kun innenfor den aktuelle serien og importen**.
- Manglende årsverdi `–`, observert null `0` og kildekonflikt `!` er
  forskjellige tilstander. Endringslogg teller ikke i arkivperioden.
- Ved bytte til en native arkivdel velges bare arkivdelens egen DWM-visning.
  KDRS U2 velges aldri automatisk på grunnlag av posisjon/nummer.
- `1899` og `2099` markeres som mulige kontrollpunkter, ikke automatiske
  falske årstall. Vurderte år, godkjenningsstatus og begrunnelse er fortsatt
  fullt ut manuelt og separat lagret for uttrekk og arkivdeler.

**Faktisk testet:** 8 isolerte fokustester for lesbar årsprofil,
kilde-separasjon, zero/missing/conflict, kildevalg og GUI-koblingsstruktur.
Python-syntakskontroll og delta-ZIP valideres ved pakking. Full `test.bat`
og praktisk Windows GUI-test er **ikke kjørt her**.

**Windows retest:** `JOB-002 → Rapport valgte → Vurder ytterår → Hele uttrekket`.
Bekreft at nedre meny automatisk velger KDRS Standard (evt. U1 hvis
Standard ikke har positive årsverdier), og at årsfordelingen for 1899,
produksjonsår og 2099 **viser de faktiske antallene**. Bytt til U1 og
kontroller at kildene ikke summeres. Kontroller samtidig at årsfeltene
fortsatt er tomme hvis ingen periode er lagret/gitt som DWM-forslag.

**Fortsatt uavklart:** Importert U2 i 1502_024 har ingen entydig tolket
**årfordeling per arkivdel** i dagens kildemodell. U2-hovedtall i seg
selv gir ikke dato-grunnlag. Native DWM XPath eller dokumentert, entydig
arkivdelavgrenset tidsserie må fremskaffes for informert per-arkivdelvurdering.
Det er ikke akseptabelt å sette arkivdelens periode ut fra et tilfeldig
U2-indeks-/tittelmatch eller arve hovedperioden uten faglig grunnlag.

Arbeidsavtalen øverst i dokumentet gjelder uendret: kun delta-ZIP, bruker
tester og committer/pusher, ingen automatisk GitHub-commit fra assistenten.

## a18-fix2 – fullskjermsvindu for årsfordeling (2026-10-15)

**Utløst av praktisk Windows-test:** KDRS-årsprofilen i nedre del av
Periodevurdering viser nå riktige årsfordelinger, men hele tabellen er vanskelig
å lese inne i den delte dialogen.

- Knappen **«Åpne i eget vindu»** ligger ved overskriften til nedre årsprofil.
- Knappen åpner en stor, resizerbar, ikke-redigerbar **lesekopi** av hele
  tekstinnholdet som er valgt i nedre kildevelger: full KDRS/DWM-tabell,
  kilde/proveniens, år og eventuelle kildekonflikter. Ingen ny analyse startes.
- Vinduet viser **jobbid og valgt kilde**, maksimeres på Windows og får stor
  rulleflate. **«Kopier all tekst»** kopierer hele teksten til utklippstavlen.
- Ulike kilder eller jobber får egne vinduer som kan sammenlignes side ved side.
  Samme jobb + samme kilde løfter eksisterende vindu i stedet for å lage duplikat.
  De åpne vinduene oppdateres *ikke* automatisk hvis kilde endres i
  hoveddialogen, slik at kildeidentiteten aldri skifter under en vurdering.
- Faglig vurdering lagres fortsatt bare i den opprinnelige dialogen; dette
  tillegget endrer **ingen** periode-, rapport-, KDRS-/DWM- eller JSON-data.

**Delta:** `v0.1.7-a18-fix2` oppå `a18-fix1`. Filer:
`gui/period_assessment_dialog_a16.py`,
`tests/test_a18_fix2_detached_year_view.py`, denne overleveringen.
Applikasjonsversjon **`0.1.7-a18`** beholdes.

**Verifisert:** 4/4 nye headless callback-tester, inkludert full tekstkopi,
read-only, identitet, side-ved-side-vinduer, kopiering, lukking/gjenåpning og
fallback hvis maksimering ikke støttes. Syntakskontroll bestått. Full Windows
`test.bat` og manuell Windows-vindu-/fokustest gjenstår.

**Manuell test:** Åpne JOB-002 → Vurder ytterår → Hele uttrekket. Med
KDRS Standard valgt klikk «Åpne i eget vindu»: kontroller at hele årsprofilen
kan rulles og kopieres. Bytt til KDRS U1 i dialogen og åpne igjen: kontroller
at det første vinduet fortsatt viser Standard og det nye viser U1. Lukk ett
vindu og åpne samme kilde på nytt. Test også at redigering/lagring av vurderte
år fortsatt skjer uendret i hoveddialogen.
