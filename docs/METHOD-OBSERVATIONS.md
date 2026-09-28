# Metodikkobservasjoner

Dette dokumentet samler erfaringer fra utviklingen av Noark 5 Workflow Manager som kan være relevante for det separate repositoriet `IKAMR/incremental-ai-development-method`.

Observasjonene her er **ikke metodikkvedtak**. De er kandidater som skal vurderes samlet i egne metodikketapper. Løpende prosjektutvikling skal derfor ikke automatisk føre til endringer i metodikk-repositoriet.

## Arbeidsregel

Når utviklingen avdekker en mulig generell metodikkforbedring:

1. Registrer observasjonen kort i dette dokumentet.
2. Ikke endre metodikk-repositoriet som en automatisk del av prosjektendringen.
3. Fortsett prosjektutviklingen dersom observasjonen ikke påvirker gjeldende increment.
4. Vurder flere observasjoner samlet i en senere metodikkrunde.
5. Klassifiser da hvert punkt som:
   - overføres til metodikken
   - slås sammen med andre observasjoner
   - beholdes som prosjektspesifikt
   - forkastes
6. Når et punkt er behandlet, flyttes det fra `Åpne observasjoner` til `Behandlede observasjoner` med resultat og eventuell referanse.

## Avgrensning mot teknisk gjeld

Dette dokumentet skal ikke brukes som vanlig feil- eller oppgaveliste for Noark 5 Workflow Manager.

- Prosjektspesifikke feil, begrensninger og teknisk gjeld hører hjemme i prosjektets ordinære oppfølgingsmekanisme.
- `METHOD-OBSERVATIONS.md` brukes bare når erfaringen kan ha generell verdi for AI-assistert utviklingsmetodikk.
- Samme hendelse kan gi både et prosjektspesifikt tiltak og en metodikkobservasjon, men de skal behandles som to forskjellige forhold.

---

## Åpne observasjoner

### MO-001 – Ikke-blokkerende tekniske funn må ikke forsvinne

**Oppstått:** v0.1.2-a13

**Bakgrunn:**  
Under test av a13 ble det observert en `lxml.etree`/Python GIL-advarsel samtidig som hele testsuiten bestod. Funnet var dermed ikke blokkerende, men var konkret og relevant for kjøremiljøet.

**Observasjon:**  
Et lite teknisk funn kan lett bli omtalt i samtalen og deretter forsvinne når utviklingen fortsetter. Samtidig er det uheldig dersom hvert slikt funn automatisk utvider aktivt scope.

**Mulig generell læring:**  
Metodikken bør ha en eksplisitt mekanisme der et konkret ikke-blokkerende funn enten:

1. prioriteres og håndteres i aktivt increment, eller
2. registreres varig i prosjektets eksisterende issue-/technical-debt-/known-issues-mekanisme for senere prioritering.

Dette kombinerer sporbarhet med scope-disiplin.

**Metodikkstatus:** Til senere samlet vurdering.

### MO-002 – Metodikkforbedringer bør samles før overføring til metodikk-repositoriet

**Oppstått:** v0.1.2-a13

**Bakgrunn:**  
En enkelt utviklingserfaring utløste først forslag om umiddelbar endring i det separate metodikk-repositoriet. Det gir risiko for at generell metodikk endres for reaktivt ut fra enkelthendelser i ett prosjekt.

**Observasjon:**  
Prosjektarbeid gir løpende små erfaringer som kan være metodisk interessante. Verdien og generaliserbarheten blir lettere å vurdere når flere observasjoner sees i sammenheng.

**Mulig generell læring:**  
Prosjekter som bruker metodikken kan ha en lokal oppsamlingsfil for metodikkobservasjoner. Kandidatene vurderes samlet i egne metodikketapper før den overordnede metodikken endres.

En observasjon skal derfor ikke automatisk bli en metodikkregel.

**Metodikkstatus:** Til senere samlet vurdering.

### MO-003 – Praktisk bruk avdekker domenegrenser som automatiserte tester ikke kan bevise

**Oppstått:** v0.1.2-a13

**Bakgrunn:**  
XML/XSD-funksjonen var automatisk testet, men første praktiske forsøk mot et reelt Noark 5-uttrekk avdekket at jobbmodellen ikke skilte tydelig mellom source, arbeidsområde og arkiv-/pakkeområde.

**Observasjon:**  
En grønn testsuite kan bevise implementert kontrakt, men ikke at kontrakten dekker den virkelige arbeidsprosessen. Praktisk test mot representativt materiale kan avdekke manglende domeneobjekter før selve funksjonen kjøres.

**Mulig generell læring:**  
Praktisk test bør brukes som eksplisitt kontrakt-/domenevalidering, ikke bare som sluttkontroll av GUI og kode. Når testen avdekker en manglende grunnmodell, bør denne avgrenses og korrigeres før videre funksjonsutvidelse.

**Metodikkstatus:** Til senere samlet vurdering.


### MO-005 – Regresjonstester må oppdateres sammen med endret kontrakt

**Oppstått:** v0.1.2-a15

**Observasjon:**  
Flere kodeleveranser har vært funksjonelt riktige, mens eldre regresjonstester fortsatt forventet forrige versjon, operasjonsliste, tekst eller utdataadresse.

**Mulig generell læring:**  
Før en kodepakke leveres skal endrede kontrakter kryssjekkes mot eksisterende regresjonstester. Særlig versjonsstrenger, registrerte operasjoner, fil-/mappestier og brukerrettede tekster skal kontrolleres. Testene skal oppdateres før levering når kontrakten bevisst er endret.

**Metodikkstatus:** Til senere samlet vurdering.

### MO-006 – Prosjektet skal selv fange kandidater til generell metodikk

**Oppstått:** v0.1.2-a15

**Observasjon:**  
Brukeren skal ikke måtte minne utviklingsprosessen på å registrere hver generaliserbar erfaring.

**Mulig generell læring:**  
Ved start og avslutning av et increment bør utviklingsagenten eksplisitt vurdere om nye erfaringer er prosjektspesifikke eller kandidater til generell metodikk, og registrere relevante kandidater i prosjektets metodikkobservasjoner uten særskilt bestilling.

**Metodikkstatus:** Til senere samlet vurdering.



### MO-007 – Teknisk feilhistorikk og bevaringsproveniens må skilles

**Oppstått:** v0.1.2-a16

**Bakgrunn:**  
Under praktisk test ble en ugyldig uttrekksmappe valgt for en jobb. Validering/preflight feilet, mappen ble deretter korrigert før relevant behandling av arkivmaterialet.

**Observasjon:**  
En utviklings-/brukerfeil kan være viktig i teknisk logg for feilsøking, men samtidig være misvisende dersom den automatisk blir varig proveniens for objektet som senere behandles korrekt.

**Mulig generell læring:**  
Systemer som både fører teknisk historikk og domeneproveniens bør klassifisere hendelser etter semantisk betydning. En rik teknisk logg kan være kildegrunnlag, men domeneproveniens bør genereres gjennom eksplisitte regler og ikke som ukritisk kopi av tekniske logger. Preflight-/konfigurasjonsfeil før faktisk behandling bør normalt ikke tilskrives objektet som en behandlingshendelse.

**Metodikkstatus:** Til senere samlet vurdering.



### MO-008 – Rå observasjon må skilles fra senere faglig konklusjon

**Oppstått:** v0.1.2-a17

**Bakgrunn:**  
Et testresultat kan være teknisk korrekt registrert som `FAIL` på kjøringstidspunktet, men senere vise seg å være en falsk feil fordi selve testen, XPath-en eller regelimplementasjonen var feil. Historikken om at testen feilet er fortsatt sann, mens påstanden om at uttrekket hadde et avvik ikke lenger er faglig gyldig.

**Observasjon:**  
Dersom råresultat og endelig konklusjon lagres som samme verdi, må systemet enten miste historikk ved retting eller risikere at underkjente testfunn forurenser sluttrapporter og proveniens.

**Mulig generell læring:**  
AI-assisterte og andre automatiserte kvalitetssystemer bør bevare rå observasjoner uendret og legge senere vurdering som et eget, sporbar lag. Endelige rapporter og domenespesifikk proveniens bør bygges fra et autoritativt resultatsett etter vurdering, ikke direkte fra alle historiske testresultater. Korrigering av testapparatet bør derfor kunne underkjenne eller erstatte et resultat uten å slette at den opprinnelige kjøringen fant sted.

**Metodikkstatus:** Til senere samlet vurdering.



### MO-009 – Nye hjelpevinduer må arve brukerens aktive arbeidskontekst

**Oppstått:** v0.1.2-a17

**Bakgrunn:**  
Et nytt hjelpevindu (`Jobber`) åpnet på en annen fysisk skjerm enn hovedapplikasjonen i et fler-skjermsoppsett. Funksjonen var teknisk tilgjengelig, men brøt brukerens aktive arbeidskontekst og gjorde arbeidsflyten unødvendig tung.

**Observasjon:**  
Automatiserte tester kan bekrefte at et vindu finnes og kan åpnes, men ikke nødvendigvis at det åpnes på et praktisk sted i brukerens faktiske desktop-oppsett. Når nye dialoger introduseres inkrementelt, kan de også få ulik plassering dersom hver dialog implementerer dette selv.

**Mulig generell læring:**  
Inkrementell GUI-utvikling bør bevare ikke bare funksjonell kontrakt, men også eksisterende arbeidskontekst. Nye hjelpevinduer bør som hovedregel arve eller beregne plassering fra vinduet som utløste dem. Tverrgående GUI-adferd som vindusplassering bør implementeres sentralt og låses med regresjonstester der dette kan automatiseres, supplert med praktisk test på representativt fler-skjermsoppsett. Dette reduserer risikoen for at små funksjonstillegg gradvis fragmenterer brukeropplevelsen.

**Metodikkstatus:** Kandidat til senere samlet vurdering i `IKAMR/incremental-ai-development-method`.



### MO-010 – Endret implementasjon krever samtidig kontroll av eldre tester

**Oppstått:** v0.1.2-a17

**Bakgrunn:**  
Flere a17-endringer styrket eksisterende GUI-kontrakter, men eldre regresjonstester var skrevet mot eksakte implementasjonsstrenger fra tidligere alphaer. Resultatet ble gjentatte testfeil først hos bruker, selv om produksjonsadferden var korrekt. I samme utviklingsløp ble det også opprettet en midlertidig `A17-*.md` i `docs/`, til tross for en eksisterende regel om at alpha-dokumenter ikke skal være permanente.

**Observasjon:**  
Det er ikke tilstrekkelig å legge til nye tester for den nye implementasjonen. Når en eksisterende funksjon endres, må hele den eldre testflaten som refererer til funksjonen eller filen kontrolleres samtidig. Tilsvarende må nye filer kontrolleres mot repository-regler før de leveres.

**Mulig generell læring:**  
Ved inkrementell utvikling bør hvert delta ha en obligatorisk «regresjons-preflight»: identifiser endrede produksjonsfiler/funksjoner, finn alle eksisterende tester som refererer til dem, vurder om testene uttrykker kontrakt eller tilfeldig implementasjonsdetalj, og oppdater foreldede tester i samme increment. Preflighten bør også kontrollere repository-strukturregler, slik at midlertidige utviklingsartefakter ikke introduseres som permanente filer. Dette reduserer gjentatte feil som ellers først oppdages i brukerens fulltest.

**Metodikkstatus:** Kandidat til senere samlet vurdering i `IKAMR/incremental-ai-development-method`.


---

## Behandlede observasjoner

Ingen foreløpig.

Ved senere metodikkgjennomgang bør behandlet punkt beholde ID og få dokumentert:

- beslutning
- begrunnelse
- eventuell sammenslåing med andre observasjoner
- hvor i metodikk-repositoriet endringen ble gjort
- issue-/commit-referanse når relevant

### MO-004 – Praktisk rollemodell må testes mot identitet, ikke bare lagring

**Oppstått:** v0.1.2-a14

**Bakgrunn:**  
Etter at Source – hovedmappe og Source – uttrekksmappe ble skilt, brukte gammel GUI-logikk fortsatt hovedmappen for å avgjøre om aktiv jobb samsvarte med valgt uttrekk. Dette kunne opprette en ny jobb uten de lagrede arbeidsmappene.

**Observasjon:**  
Når en eksisterende verdi splittes i flere semantiske roller, må alle steder som bruker verdien til identitet, matching, logging og persistens vurderes – ikke bare selve datalagringen.

**Mulig generell læring:**  
Ved raffinering av en datamodell bør praktisk test eksplisitt kontrollere både lagring og identitets-/matchingsemantikk.

**Metodikkstatus:** Til senere samlet vurdering.

### MO-011 – Visuelle sprang bør utforskes med målbilde før implementering

**Oppstått:** v0.1.6-a18–a20

**Observasjon:**
Små inkrementer er effektive for funksjonell utvikling, men kan gjøre GUI-et gradvis bedre uten at større muligheter i informasjonsarkitektur og visuell kommunikasjon blir oppdaget. I resultatvisningene ga eksplisitte før/etter-målbilder og designstudier et tydelig sprang i kvalitet og gjorde det mulig å diskutere retning før kode ble endret.

**Mulig generell læring:**
Utviklingsagenten bør være kreativ og proaktiv når eksisterende data åpner for en vesentlig bedre visualisering. Ved betydelige visuelle forbedringsmuligheter bør den foreslå eller lage et målbilde/mockup før implementering. Samtidig skal vesentlige endringer i struktur, informasjonsarkitektur, arbeidsflyt eller funksjonell rolle alltid avklares med brukeren før de implementeres. Eksisterende fungerende løsning skal ikke forkastes bare fordi et nytt design ser bedre ut.

**Metodikkstatus:** Kandidat til senere samlet vurdering i `IKAMR/incremental-ai-development-method`.

### MO-012 – Designreferanser er varig prosjektkunnskap, ikke engangsillustrasjoner

**Oppstått:** v0.1.6-a18–a20

**Observasjon:**
Flere GUI-målbilder ble sentrale i senere diskusjoner om Oversikt, Arkivdeler, periodeprofil og detaljert faktaprofil. Når slike bilder bare finnes i samtalehistorikken, må retningen gjenoppdages og forklares på nytt.

**Mulig generell læring:**
Godkjente eller viktige konseptbilder bør lagres i prosjektets repository sammen med kort dokumentasjon av hensikt, status og forholdet til nyere/eldre målbilder. De skal være eksplisitt utviklingsgrunnlag, men ikke behandles som uforanderlig spesifikasjon. Nyere beslutninger kan presisere eller erstatte deler av eldre bilder uten å slette historikken.

**Metodikkstatus:** Kandidat til senere samlet vurdering i `IKAMR/incremental-ai-development-method`.
