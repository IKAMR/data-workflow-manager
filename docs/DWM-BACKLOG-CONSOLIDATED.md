# DWM: konsolidert funksjons- og utviklingsbacklog

Planpunkter oppsummert fra arbeidsdialogene «N5 WF Man 24» (november 2026) og videreføringen «N5 WF Man 25». **Historisk diskutert** er ikke lik **implementert eller ferdig testet**. Behold dette dokumentet som varig oversikt; slett først et punkt etter implementasjon, regresjonstest og oppdatert dokumentasjon.

## Faglig kontroll, kilder og presentasjon

- [ ] Systematisk krav-/kontrollplan og dekningsmatrise for komplett uttrekk; skille ikke kjørt, ikke relevant, avbrutt, feilet og bestått; sikre riktige hovedtall og separat faglig godkjenning.
- [ ] Koble hver kontroll, advarsel, merknad og frivillig stikkprøve til faktisk XML-evidens: kildefil, XPath, linje, system-ID, parent/child/søsken, og dokumentfil hvis referansen finnes.
- [ ] Forbedre XML-evidens: justerbare vertikale/horisontale paneler, hele seksjonen i XML, trestruktur arkiv→arkivdel→klassifikasjonssystem→klasse→mappe→registrering→dokumentbeskrivelse→dokumentobjekt, «3 av 10» der eksakte søskentall er kjent, sorterbare kolonner, lange stier og tekstbryting. Avgrens lesingen for store XML-filer.
- [ ] Standardverdikontroller: egen smal M-ID-kolonne (M300/M082/M500/M502), synlig aktuell Noark-versjon fra XSD, bakoverrettet sammenligning 5.0→4.0→3.1, ingen falsk tredobbelttelling, relevante spesifikasjons-/XSD-referanser. Norsk språk i stedet for interne statustekster. Vis faktiske observerte og forventede verdier side om side.
- [ ] Identifiser XSD-revisjoner etter `xs:schema`, endringshistorikk, schema-struktur og SHA-256; bevar ukjente varianter som evidens med UUID/hash/proveniens; sammenlign ADDML uten blindt å stole på den. Delbare regeldata uten depotmateriale.
- [ ] Resultatvisninger: kort, evidensbasert oppsummering på Oversikt; lesbare navigasjonslenker til avvik; filtrering etter status, kilde, arkivdel, type, metadata-ID og uavklarte vurderinger; kolonneklikk for numerisk og alfabetisk sortering; mer plass til hovedinnhold enn knapper; bevar valgt splitterstørrelse.
- [ ] Årsfordeling: 0 bare når den relevante tellingen faktisk er gjennomført; ukjent er ikke 0; totalsummer skal markere ufullstendig grunnlag, med diagram/tall/begge og drabar skillelinje.
- [ ] Samle alle testresultater (DWM, Arkade, Siegfried, KDRS Query, manuell vurdering) uten å miste kilde-/kjøringsidentitet, inkludert gjenbrukbar kanonisk modell, rapportadaptere, uttrekkssammenligning og statistikk.

## Rapport, prosess og bevaring

- [ ] Kvalitetssikringsrapport for arkivskaper: innhold, proveniens, periodisering, dokumentkoblinger, avklaringer, bevis og formell aksept.
- [ ] Depotfaglig beslutningsflyt, revisjonshistorikk, godkjennings-/ferdigstillingsrapport, journalføring og sporbarhet til akseptert evidens.
- [ ] AIP-produksjon *etter* vurdering, med definert profil og kuratert evidens; preflight, manifest, integritetskontroll, eventuelle PREMIS-hendelser og sikker verifikasjon.
- [ ] Rapport- og statistikkgrunnlag på tvers av uttrekk, system/leverandør, arkivskaper/-eier, år, volum, kvalitet og format; statistikk skal bare bygge på sammenlignbare tall med datadekning.

## Jobb, arbeidsflate og Windows

- [ ] Enkel modus: lesbar og rolig trinnvis flyt Source/info.xml → Work → Kjøring, valgfri jobbliste synlig i Kjøring, «Ny kontroll» uten sletting, direkte drag-and-drop for Source/Work/info.xml/.n5jobs, fullstendige kopierbare stier, fornuftige mappeforslag.
- [ ] DIAS: behold original info.xml som evidens; redigerbar arbeidskopi; synlig LABEL; koble LABEL/DELIVERYSPECIFICATION per valgt policy (standard True), senere global DIAS-profil med per-jobb-overstyring. Fremtidig CRM-metadata må inn i samme datamodell.
- [ ] Work-sikkerhet: identifiser samme/annen/ukjent Source i gamle og nye Work; tilby relevant jobbåpning eller avvisning; aldri slett eksisterende resultater; ingen ekstra Work/dwm-nivå.
- [ ] Sikre testrekkefølge, valgfritt automatisk åpnede resultat-/kjøre-/loggvinduer og selektiv stopp uten falsk «bestått».
- [ ] Vindu/Qt: persister størrelse/posisjon på laptop + ekstern widescreen, popup på samme skjerm som hovedvindu, korrekt grense ved topp/høyre hjørne, varselindikator for reelle konsollfeil og egen GUI-krasjdiagnostikk. Ikke behandle små DPI-geometrijusteringer som alvorlig feil.
- [ ] Bedre Kjøredetaljer, resultatvisninger per deljobb versus rå resultatfil, loggåpning; bevar historiske kjøringer.
- [ ] Parallellisere interne Noark-kontroller *senere*, med deterministiske resultater og bevart ekstern Arkade-kompatibilitet. Egendefinerte versjonerte filformatprofiler og AIP er egne utviklingssteg.

## Erfaring og distribuert forvaltning

- [ ] Lokalt erfaringsregister med maskinlesbare mønstre (først M300), versjonsavhengig faglig tolkning, merknadsforslag, eksplisitt kontrollørbeslutning og historikk.
- [ ] Fire forvaltningsnivåer: sentral felles GitHub-regelbase → depotpolicy → brukerpraksis → klientcache; planlegg depotserver og eventuell KDRS-flerdepottjeneste uten å binde koden til disse nå.
- [ ] Eksport/import mellom klienter med versjon, konfliktstrategi, anonymisering og eksplisitt publiseringsbeslutning. Ingen automatisk publisering av mottatte uttrekksfiler, personopplysninger, interne stier eller jobbvurderinger.

## Gjennomføringsregler

- Behold ett felles jobb-/Work-/resultatgrunnlag i Enkel og Avansert modus.
- Delta-ZIP direkte over sist committede versjon, bare komplette repo-filer og korrekte relative stier; korte versjonsriktige filnavn, ingen midlertidige README/patch-oppgaver.
- Bruk versjonstester som tåler nyere versjoner og unngå hardkoding av gamle releaseversjoner.
- Dokumenter både implementert omfang og kjent uferdig arbeid; full Windows `test.bat` utføres av utvikler før commit.
