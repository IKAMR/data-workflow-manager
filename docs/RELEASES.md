# Versjonshistorikk

Dette dokumentet samler releaseinformasjon for ferdige versjoner i samme
Git-historikk.

Fra v0.1.4-utviklingen heter prosjektet **Data Workflow Manager**.
Versjonene v0.1.0–v0.1.3 ble utgitt under navnet **Noark 5 Workflow Manager**.

Nyeste ferdige versjon står øverst. Alpha-trinn dokumenteres ikke som egne
permanente releaseversjoner.

## v0.1.14

Standardverdikontroller med sporbar XML- og XSD-evidens, lokal erfaringsbase, forbedret XML-kontekst og sikrere oppstart med frakoblede disker.

- **Standardverdier og XML-evidens:** Egne kontroller og treffvisninger for utvalgte Noark 5-metadatafelt, blant annet M300 (`dokumentmedium`), M082 (`journalposttype`), M500 og M502. Treff kan spores til kildefil, XPath, linje og nærmeste system-ID uten at originalfilene endres.
- **Versjonsbestemt XSD-tolkning:** Identifikasjon av Noark 5-versjon fra XSD-deklarasjon, med SHA-256 som støtte for konkret skjemavariant. Regelvisning kan sammenligne historiske Noark 5.0-, 4.0- og 3.1-definisjoner. ADDML-opplysninger behandles som separat evidens og overstyrer ikke dokumentert XSD-innhold.
- **Lokal XSD-evidens og erfaringer:** Kildereferanser, kjente lokale avvik, manuelle faglige vurderinger og gjenbrukbar lokal praksis holdes adskilt fra teknisk teststatus. Eksempelvis kan `Elektroniskarkiv` vurderes mot `Elektronisk arkiv` uten at en historisk regel feilaktig presenteres som et brudd på Noark 5.0-XSD.
- **Forbedret XML-kontekst:** Navigerbart strukturtre for arkivhierarkiet, mer lesbar XML med korrekt innrykk, kildekontekst, fulle XPath- og system-ID-verdier, sorterbare treff, tekstbryting, justerbare paneler og kontrollert autojustering.
- **Eksport av XML-utdrag:** Valgte XML-elementer eller hele avgrensede strukturer kan eksporteres som egne arbeidskopier med manifest under `custom_work/xml_extracts` i valgt Work. Originalt Noark 5-uttrekk forblir uendret. Avkortet forhåndsvisning skal ikke eksporteres som et fullstendig element.
- **Vinduer og flerskjerm:** Bedre lagring og gjenoppretting av vindusstørrelse og plassering, samt mer hensiktsmessige layoutjusteringer i evidensvisningene.
- **Frakoblede disker og jobblister:** DWM beholder referansen til sist brukte `.n5jobs` selv om en kryptert disk er låst eller frakoblet. Programmet åpner ikke en eldre jobbliste fra en annen disk som automatisk erstatning. Meldingen tilbyr «Prøv igjen» etter tilkobling eller «Fortsett uten jobb», uten at sist brukte referanse glemmes.
- **Dokumentasjon og tester:** Dokumentert kildebibliotek for Noark, lokal XSD-variant og vurderingsevidens, Windows-stisammenligning og plan for senere felles, versjonerte resultatdata på tvers av kontrollkilder.

Kompatibilitet: Eksisterende jobblister, Source, Work, tidligere kontrollresultater og DIAS `info.xml` videreføres. Vanlig kontroll og XML-eksport skal ikke endre originale arkivuttrekk. DWM, Arkade 5, Siegfried og manuelle depotvurderinger er fortsatt egne evidenslag. Fullført teknisk kontroll innebærer ikke automatisk faglig godkjenning.

Kjent avgrensning: Felles kanonisk resultatmodell og sammenlignende statistikk på tvers av uttrekk er planlagt for videre utvikling og er ikke del av v0.1.14. Praktisk validering er utført på Windows; støtte for andre kjøremiljøer er ikke verifisert tilsvarende.

## v0.1.13

Enkel modus med DIAS-metadata, sikrere Work-valg og forbedrede resultatvisninger.

- **Enkel modus:** Trinnvis oversikt over Source, Work og kjøring, med synlig aktiv fane, direkte navigasjon, fullstendige stier og dra-og-slipp av uttrekksmapper, `info.xml`, Work-mapper og jobblister. Ny kontroll kan startes uten å slette gamle jobber eller resultater.
- **DIAS-metadata:** Synlig og redigerbar LABEL og dialogen «Info.xml – Les / endre». Importert original bevares som kildeevidens; gjeldende depotmetadata og arbeidskopi lagres separat under Work. LABEL og DELIVERYSPECIFICATION kobles i denne versjonen.
- **Work-sikkerhet:** Kontrollerer valgt Work opp mot Source-identitet og tidligere DWM-jobbdata. Ved mulig gjenbruk vises innhold og bekreftelse eller tilbud om å åpne eksisterende jobb. Feil eller ukjent eierskap blokkerer automatisk gjenbruk. Valgt Work brukes direkte uten ekstra `dwm`-nivå i Enkel modus.
- **Valgfri jobbliste:** Jobbliste kan åpnes eller lagres fra Kjøring. Lagringsdialogen foreslår en passende plassering og filnavn; ved start uten lagret jobbliste kan brukeren velge å lagre, kjøre uten fil eller avbryte. Work-resultater lagres uavhengig av jobblisten.
- **Kontrollkjøring:** Rekkefølgen legger DWM sine Noark 5-kontroller før Arkade 5 Noark 5, og Siegfried PRONOM før Arkade 5 PRONOM. Kontrollvalg og automatisk åpning av Resultatvisninger, Kjøredetaljer og kjørelogg er separate innstillinger i Enkel modus.
- **Årsfordeling:** Kjent delsum vises også når enkelte arkivdeler mangler årsverdier, tydelig merket med ufullstendig dekning. Diagram og tabell kan vises sammen eller hver for seg, og panelhøyden kan justeres.
- **Tekniske kontroller:** Filtrering og sortering er forbedret i Resultatvisninger. Tidligere resultater og eksterne evidenskilder beholdes.

Kompatibilitet: Samme jobbmodell, DIAS-data, arbeidsflytmotor og lagrede resultater brukes i Enkel og Avansert modus. Ingen originalfiler i Source skal endres av vanlig testing. Teknisk fullført kontroll er ikke automatisk faglig depotgodkjenning.

## v0.1.12

Korrigert Setup-lagring for eksterne verktøy.

- Setup kan lagre konfigurasjonen for Arkade 5 CLI og Siegfried samlet, inkludert programstien til eksisterende `sf.exe` installert via SIARD Workflow Manager.
- Eksisterende arbeidsflyter og Work-resultater påvirkes ikke av rettelsen.

## v0.1.11

Enkel start, valgfrie kontrolloperasjoner og selvstendig Siegfried-filidentifikasjon.

Hovedendringer:

- **Enkel modus** med tre trinn: velg Noark 5-uttrekk (Source), velg Work og start kontroll. Valgt Work brukes direkte uten ekstra skjulte arbeidsmapper. Avansert modus og eksisterende jobblister er fortsatt tilgjengelige.
- **Fire uavhengige kontrollvalg:** DWM Noark 5-test og depotrapport, Siegfried PRONOM-filidentifikasjon, Arkade 5 CLI Noark 5-test og Arkade 5 CLI PRONOM-analyse. Valgene settes sammen til en arbeidsflyt i samme kjøremotor som Avansert modus.
- **Selvstendig Siegfried-integrasjon** som kan finne og bruke samme installerte `sf.exe` som SIARD Workflow Manager uten kopiering. Identifikasjoner, formatstatistikk, råresultater og proveniens lagres separat under valgt Work; egne Siegfried-resultater blandes ikke med Arkades resultater.
- **Arkade 5-integrasjon** med valgfrie CLI-operasjoner, import av lagret Noark 5- og PRONOM-evidens og korrigert bruk av direkte Work-mappe i Enkel modus. Historiske rapporter og vurderinger beholdes som separate evidenskilder.
- **PRONOM-visning** med separat presentasjon av Arkades historiske RAF-220301-vurdering og DWM-vurdering mot valgt formatregelprofil. Den daterte listen over Nasjonalarkivets aksepterte filformater (10. november 2026) er standard; et annet eksplisitt valg bevares. Tabell, kolonnebredder og detaljpanel er forbedret.
- **Kjørestatus i Enkel modus** med synlig samlet fremdrift, aktiv deljobb, fremdrift i deljobben og tid siden siste faktiske kjøremelding. Statusfeltet holdes synlig over det rullbare oppsettet. **Kjøredetaljer** gjenbruker Avansert modus sin kjørehistorikk og logger i eget vindu.
- **Setup for eksterne verktøy** med egne seksjoner for Arkade 5 og Siegfried, automatisk gjenkjenning, manuelt programvalg og versjonskontroll. DWM installerer ikke disse verktøyene fra Setup.

Kompatibilitet: Eksisterende `.n5jobs`-jobblister, avanserte arbeidsflyter, Arkade-importer, Work-resultater og den separate depotfaglige vurderingen videreføres. Ingen originale Source-filer endres ved vanlige kontroller. Fullført teknisk kontroll eller treff i en formatliste innebærer ikke automatisk depotgodkjenning.

Avgrensninger: Versjonen er beregnet for praktisk testing på Windows. Eksterne verktøy krever tilgjengelig lokal installasjon. Direkte Siegfried-kjøring er foreløpig begrenset til 250 000 filer per kjøring; større mengder avvises fremfor å produsere ufullstendig statistikk. Videre forbedring av enkelte dialogstørrelser og fremdriftsinformasjon fra eksterne CLI-prosesser gjenstår.

## v0.1.10

Forbedrede Resultatvisninger, sporbar filformatvurdering og mer tilgjengelig brukergrensesnitt.

Hovedendringer:

- Resultatvisninger i PySide6 har fått bedre oversikt over Arkivdeler, Tekniske kontroller, Arkade 5, PRONOM og Periodevurdering. Første relevante resultatrad velges automatisk, og tabeller har lesbare testnavn og tilpassede kolonnebredder.
- Valg mellom **Lesbar visning** og **Råtekst / JSON** for detaljer og evidens. Utvalgte faner har sidepanel i full høyde, mens andre har tilpasset panelhøyde. Delingslinjer kan justeres manuelt og tilbakestilles med **Auto størrelse**. Eksisterende lagret evidens beholdes.
- Arkade 5 Noark 5-tester kan vises fra lagret depotrapports dokumenterte testdekning når direkte normalisert kildelesing ikke gir resultat. Arkades teststatus, feilantall, kilde, import og proveniens holdes separat fra DWM-kontrollene; ingen tester eller resultater konstrueres ved manglende dokumentasjon.
- PRONOM viser **Arkades historiske RAF-220301-klassifisering** og en uavhengig PUID-vurdering mot en eksplisitt valgt, datert formatregelprofil. Valgt profil, utgave, kilde og SHA-256 synliggjøres og kan følge CSV-eksport. Datert Nasjonalarkivet-kopi fra 10. november 2026 inngår som et referansegrunnlag som ikke oppdateres automatisk.
- Setup har tydeligere lagringsprofiler og mappevalg, trygg standardprofil for nye oppsett og bedre skille mellom Source, Work og AIP. Lagrede, eksplisitte profilvalg og eksisterende jobber beholdes.
- Utvidede fargetemaer og helhetlige paletter, inklusive egne farger, samt mer fleksibel plassering av dialoger og popup-vinduer.
- Kontekstbaserte handlingsknapper og bedre navigasjon mellom resultatfanene, uten at tidligere rapport- og vurderingsfunksjoner erstattes.

Denne versjonen er ment for videre **praktisk brukertesting**. Teknisk fullføring, formatlistetreff eller Arkade-status betyr ikke automatisk at et arkivuttrekk eller en AIP er depotfaglig godkjent. Historisk evidens, selvstendig formatvurdering og faglige beslutninger holdes adskilt.

Kjent forbedringsbehov: Ytterligere dynamisk utnyttelse av vindusstørrelser og finjustering av noen Resultatvisninger, særlig PRONOM og enkelte detaljer, videreutvikles etter denne releasen. Ut over Windows-desktop er kjøremiljøer ikke praktisk verifisert.

## v0.1.9

Sporbar kildeevidens, faglig depotvurdering og portabel lagring for selvstendige Work-jobber.

Hovedendringer:

- Utvidede Resultatvisninger i PySide6 med Kildeoversikt og Arkade-dekning: bevarte DWM-, Arkade 5- og KDRS Query-kilder vises separat med identitet og kildegrunnlag. KDRS Query får filtrering for Standard/U1/U2, og kildeoversikt kan eksporteres som CSV, HTML og JSON. Eksisterende rapport- og årsfordelingsvisninger videreføres.
- Ny Depotvurdering per uttrekk og per arkivdel (original system-ID), med teknisk status, periodegrunnlag og faglig beslutning som separate felt. Manuelle beslutninger krever begrunnelse og brukeridentitet, har historikk og er bundet til rapportens SHA-256. En fullført arbeidsflyt betyr ikke faglig godkjenning.
- Forbedret jobbliste med status for tilgjengelig/frakoblet Work, identitetskontroll, gjenoppretting fra Work og eksplisitt omkobling av flyttet Work eller Source. Varig jobb-UUID og historikk beholdes.
- Portabel lagringsmodell med kontrollert rotomkobling for flere jobber, for eksempel fra G:\ til H:\, med relativ delsti per lagringsrolle. Source, Work og AIP kan fortsatt ligge under forskjellige røtter. Work lagrer et eget `storage-roots.json` med rotmapping, jobbreferanse og relative delstier.
- Forhåndskontroll, identitetskontroll av Work og eksplisitt brukerbekreftelse før omkobling. Ingen arkivfiler kopieres, flyttes eller analyseres på nytt. Eksisterende `.n5jobs`-filer og det opprinnelige CustomTkinter-GUI-et videreføres.

Avgrensninger: Historiske absolutte stier i gamle rapporter og logger omskrives ikke. `storage-roots.json` er et tillegg til de autoritative `job.json`, `job-state.json` og `job-events.jsonl`; eksisterende runtime bruker fortsatt oppdaterte absolutte stier. En omkobling over flere jobber er ikke én atomisk transaksjon. SIARD-analyser, tverrjobbanalyse og parallelle workers inngår ikke i denne releasen.

## v0.1.8

Nytt fleksibelt brukergrensesnitt og selvstendige jobber i Work.

Hovedendringer:

- Nytt PySide6-basert GUI med flyttbare paneler, lagrede arbeidsflater og separate visninger av Kjøreløp, Kjørelogg og Systemlogg. Det opprinnelige CustomTkinter-GUI-et beholdes som alternativ.
- Felles applikasjons-API som skiller brukergrensesnitt fra arbeidsflytmotoren og viderefører eksisterende analyser.
- Jobbdefinisjon, status og hendelser lagres autoritativt i Work, med varig UUID, jobbliste som indeks og mulighet for gjenoppretting uten opprinnelig jobbliste.
- Selektiv kjøring av deljobber, varig Kjøreløp, logger og identifiserbare kjøringer.
- Førkjøringskontroll av uttrekk, lagringsroller, arbeidsflyt og Arkade 5 CLI, med samtykke før opprettelse av manglende Work-mapper.
- Resultatvisninger og rapportering fra lagrede DWM-, Arkade 5- og KDRS Query-resultater, inkludert årsfordelinger, arkivdeler, periodevurdering og samlerapporter.
- Forbedret valg av rapportmappe og husking av sist brukte kilde-, Work- og rapportmapper i det nye GUI-et.

En teknisk fullført arbeidsflyt innebærer ikke at et uttrekk er faglig godkjent. Resultatgrunnlag og manuelle vurderinger holdes adskilt.

SIARD-analyser, analyser på tvers av ulike uttrekkstyper og en separat parallell arbeidsmotor inngår ikke i denne releasen.

## Navneovergang etter v0.1.3

Etter release v0.1.3 ble repositoryet renamet fra
`IKAMR/noark5-workflow-manager` til `IKAMR/data-workflow-manager` med samme
Git-historikk. v0.1.4-a1 er første utviklingstrinn med Data Workflow Manager som
applikasjonsnavn.

## v0.1.3

Robust flerjobbkjøring, sporbare resultater og forbedret validering av store Noark 5-uttrekk.

Hovedendringer:

- forbedret jobb- og batchhåndtering med gjenopptak etter lagringsfeil
- selektiv gjenkjøring og versjonerte resultatsett
- unike resultatmapper og `artifact_manifest.json` med `JOB`-/`RUN`-identitet
- regel på jobblistenivå for egne Work-undermapper per jobb
- kontroll av eksisterende resultater ved oppdagelse av jobber
- Noark 5 XPath-resultater, views og depotrapporter holdes adskilt per jobb og kjøring
- forbedret fremdriftsvisning for operasjoner og tester i jobblisten
- streamingbasert XML/XSD-validering for svært store XML-filer
- validering av `arkivstruktur.xml` over 4 GB praktisk verifisert
- resultat- og ytelsesdiagnostikk med bedre sporbarhet

## v0.1.2

Noark 5-validering og rapportering basert på kanoniske analyser.

Hovedendringer:

- Noark 5 XPath-analyser med `lxml` og eksterne definisjoner
- analyse av hele uttrekket og per arkivdel
- standardverdikontroller og avstemming av resultater
- U1/U2 beholdt som regresjonsgrunnlag
- gjenbrukbare views for presentasjon av analyseresultater
- depotvalideringsrapport med avvik, vurderingspunkter og sporbarhet

## v0.1.1

Job/Batch og vedvarende jobblister.

Hovedendringer:

- `Job`, `JobStatus` og `JobBatch`
- eget Jobber/Batch-vindu
- én jobb eier kilde, workflow, operasjonsparametre, output, status og logg
- `Start alle` kjører jobbene sekvensielt med `LocalExecutor`
- stopp av batch ved neste avbruddspunkt
- separat DIAS-konfigurasjon og output per jobb
- output/resource locking
- vedvarende `.n5jobs`-jobblister
- flere separate jobblister kan lagres og åpnes
- aktiv jobb, workflow, operasjonsparametre og relevant jobbstatus kan gjenopprettes
- store Noark 5-uttrekk lagres ikke i jobblistefilen; de refereres med sti
- automatisk arbeidsstatus utenfor repository per bruker
- kontroll mot output/source-kollisjoner
- kjøremiljø og framtidig plattformretning dokumentert

## v0.1.0

Første stabile dokumenterte baseline.

Viktig funksjonalitet:

- valg og deteksjon av Noark 5-kilde og workflow-GUI
- lokal kjøring gjennom `LocalExecutor`
- arkitekturgrense for framtidig `RemoteExecutor`
- DIAS metadata- og pakkedialog
- import av eksisterende METS/`info.xml`
- fil/mappe-tillegg og direkte streaming til ukomprimert TAR
- vedvarende mapper og testdokumentasjon
- sentral workflow-PREMIS
