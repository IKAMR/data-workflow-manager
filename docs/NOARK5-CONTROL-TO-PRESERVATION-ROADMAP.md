# DWM: Fra Noark 5-mottak til kontrollert bevaring

Status: styrende utviklingsplan, faglig presisert i v0.1.15-a16 (tidligere grunnlag a4). Dette er **ikke** en erklæring om at de planlagte funksjonene finnes. Se også `NOARK5-CANONICAL-A4.md`.

## Mål

Ett uttrekk skal kunne følges fra mottak og identifikasjon via komplett teknisk/faglig kontroll, avklaringer og arkivskapers bekreftelse til depotets godkjenning, journalføring, AIP-produksjon og bevaring. Den kanoniske modellen skal være felles datagrunnlag for *flere* rapporter og for sammenligning/statistikk. **Kontroll, vurdering, godkjenning og bevaring er separate prosesshendelser**. Fullført kontroll er ikke aksept.

## Dokumentasjonskjeden

1. **Mottak / Source:** registrer identitet, proveniens, DIAS `info.xml`, leveransemetadata, filmanifest og sjekksummer. Source forblir uendret. Bevar både mottatt `info.xml` og redigert arbeidskopi under Work; koblingen LABEL/DELIVERYSPECIFICATION er foreløpig standard `True` og må senere kunne styres via DIAS-profil globalt/per jobb. Fremtidig CRM kan levere metadata gjennom samme jobbmodell.
2. **Kontrollplan før kjøring:** identifiser faktisk Noark 5-versjon fra XSD (inkl. `xs:schema version`, endringshistorikk, namespace, checksums); ADDML `arkivuttrekk.xml` er sammenligningskilde som kan være foreldet. Støtt Noark 5 v3.1, 4.0, 5.0 (ofte omtalt Noark 5.5, men registrer standardversjon 5.0). Definer obligatoriske, betingede og valgfrie tester for uttrekk og leveranseprofil. Hver test får relevant regelversjon, forventet evidens og begrunnelse ved «ikke relevant».
3. **Validering:** kjør nødvendige interne kontroller, XSD, XPath, dokumentreferanser, manifest/sjekksummer, Siegfried PRONOM, Arkade 5 Noark og PRONOM, relevante KDRS Query-resultater og DIAS/proveniens. Sikre rekkefølge (DWM Noark → Arkade Noark; Siegfried → Arkade PRONOM), selektiv avbrytelse og riktig videreføring; en stoppet kontroll er aldri bestått. Eksisterende motstridende kilder skal ikke skjules.
4. **Kontrolldekningsmatrise:** mål *hva som skulle kjøres* mot *hva som faktisk ble kjørt*; skille bestått, avvik, merknad, uavklart, ikke kjørt, avbrutt og ikke relevant. «58 tester» alene betyr ikke fullstendig kontroll. En totalsats krever dokumenterte nevnerverdier og kompetente beslutningsregler.
5. **Kanonisk resultatmodell:** arkiver strukturert observasjon per kilde/test/kjøring med stabil ID, Work-relativ evidenssti, kontrollsum, regel-/skjemaversjon, metadata-ID, XML XPath/linje/system-ID der dokumentert, datadekning og separate vurderingshendelser. DWM-mastertester, råresultatledger, Arkade, Siegfried, KDRS Query og faglige vurderinger beholder sine ulike roller. En etterfølgende kjøring skal ikke stille gamle funn som «null» eller overskrive historie.
6. **Kvalitetssikringsrapport til arkivskaper:** presenter uttrekksidentitet, system/leverandør, arkivskaper/arkiveier, struktur og periode, dokumentdekning, teknisk resultat, proveniens, avvik og konkrete spørsmål. Arkivskaper kan bekrefte innhold/proveniens eller svare på avklaringer; beslutning og signatur/dato må journalføres sporbarhetsmessig. Rapporten må tydelig vise hvilket resultatøyeblikksbilde som ligger til grunn.
7. **Depotfaglig vurdering:** kontrolløren undersøker faktiske XML-forekomster og dokumenter, legger inn stikkprøver, merknader, akseptable avvik, begrunnelser og vedtak. Ikke bland sammen skrivevarianter og XSD-feil: M300 `Elektroniskarkiv` vs `Elektronisk arkiv` oppfyller den undersøkte Noark 5 v5.0-XSD-feltregelen `minLength=1`, mens eldre 4.0/3.1-lister er historisk referanse. Korrekt regelstatus må undersøkes *per metadatafelt*, ikke generaliseres fra M300.
8. **Godkjennings-/ferdigstillingsrapport:** avstemming av kontrollplan, restavvik, kvalitetssikringsuttalelser, dokumentert godkjenningsmyndighet, dato, beslutning, evt. forbehold og identifiserbare bevaringsobjekter. Produser journalførbar rapport og journalreferanse; teknisk pass-status gir aldri automatisk depotgodkjenning.
9. **AIP/Bevaring:** etter vedtak velges bevaringsprofil og materiale. Produser AIP med manifest, sjekksummer, relevante metadata (inkl. PREMIS der profil krever det), original og eventuelle transformerte filer og et *kuratert* evidenssett. Verifiser integritet, komplett referanseoppløsning og at alle bevaringsfiler kan åpnes; registrer pakkeidentitet, lagringsplass, kopier og hendelser. Source og originale Work-resultater skal forbli uendret.
10. **Evidensbevaring:** skill mellom (a) arbeidslogger i Work, (b) signifikant og etterprøvbar evidens i AIP, (c) dokumentasjon til journalføring. Bevar kildefil, utvalgspolitikk, produsent-/verktøyversjon, regelgrunnlag og hash for hver inkluderte evidensfil. Et AIP-manifest må knytte rapportens påstander til faktisk inkluderte data eller en uttrykkelig ekstern journalreferanse; ikke påstå at all Work er del av AIP.
11. **Analyse på tvers:** bygg søk, sammenligning og statistikk fra sammenlignbare, normaliserte og kildebelagte felter, med datadekning og regelversjon tydelig. Eksempler: systemtype, leverandør, arkivskaper, arkiveier, periode, arkivdel, antall mapper/registreringer/dokumentobjekter, formatprofil, avvikstyper, gjennomføringstid og erfaringer. Ikke summer overlappende mastertester eller bland deler fra ulike kjøringer.

## Utviklingssekvens (foreslått etter v0.1.15-a3)

| Inkrement | Planlagt leveranse | Status |
| --- | --- | --- |
| a4 | Koble vurderingshistorikk og utvalgt ekstern evidens til kanonisk snapshot med sporbarhet og uten implisitt godkjenning | Første, begrenset adapter i a4: `canonical-context.json`; full strukturert parsing gjenstår |
| a5 | Dokumenterte XML-forekomster, XPath, system-ID, dokumentreferanser, metadata-ID og regelkobling | Planlagt |
| a6 | Kontrollplan og dekningsmatrise samt kort, riktig samlet resultatoversikt | Planlagt |
| a7 | Kvalitetssikringsrapport for arkivskaper, spørsmål/tilbakemeldinger og aksept | Planlagt |
| a8 | Depotvurdering, godkjennings-/ferdigstillingsrapport og journalføringsgrunnlag | Planlagt |
| a9 | AIP-profil, pakking, kuratert evidens, manifest, hash og pakkeverifikasjon | Planlagt |
| a10+ | Uttrekkssammenligning, statistikk, erfaringsbase/-deling og senere server-/CRM-integrasjon | Planlagt |

Denne sekvensen avløser ikke eksisterende backlog. Store arbeidsoppgaver kan kreve egne underinkrementer og revisjon av plan etter testing.

## Sikkerhets- og kvalitetspunkter

- Source er skrivebeskyttet. Work er **valgt rotmappe**, ikke et automatisk ekstra `dwm`-nivå.
- Ingen avvik skal merkes «bestått» fordi noen har skrevet en faglig merknad; teknisk evidens og beslutning er separate.
- Alle regelkilder må være versjonert og etterprøvbare. Lokalt referansebibliotek: [Digital Archive Workflow / Noark](https://github.com/IKAMR/digital-archive-workflow/tree/main/docs/kilder/noark) og [IKAMR Arkade-fork](https://github.com/IKAMR/arkade5). Ikke gjør SHA-256-likhet til eneste kriterium for XSD-versjon.
- Alle kontrollresultater skal ha en dokumentert proveniens. Der kobling til XML/fil/linje ikke finnes, vis «ikke registrert», ikke oppdiktet referanse.
- Lokal erfaring og overstyring skal ikke publiseres automatisk. Delbar JSON-modell: felles GitHub → depot → bruker → klient; mulig depotserver og eventuell KDRS-tjeneste senere. Pasient-, person-, depot- og interne stidata skal ikke havne i felles regelbase.
- `.n5jobs` er valgfri ved enkel kontroll, men må kunne brukes identisk i Enkel og Avansert modus. Gamle Work-områder skal identifiseres etter sikker Source-match. Frakoblede diskbokstaver skal ikke føre til feil jobbvalg.
- Windows: bruk `Path.samefile()` der faktisk filidentitet skal testes; støtt aliaser, 8.3-kortnavn, ulike bokstavstørrelser og flyttbare diskbokstaver. `Path.resolve()` alene bekrefter ikke filidentitet.
- Endringer skal regresjonstestes, særlig PySide6-levetid, fil- og mappevalg, fler-skjerm vindusgeometri, tidligere resultatdata, full `test.bat` og praktisk Windows-kjøring.


## Faglige føringer presisert 14. november 2026 (a16)

**Eksisterende løsning først:** DWM har allerede fungerende DIAS-pakkemodul, prøvd tidlig i DWM og brukt i SIARD Workflow Manager. `noark5_workflow/operations/dias_package.py`, `dias_mets.py`, `app/dias_info_v0113_a2.py` og DIAS-dialogene skal undersøkes og videreutvikles, ikke erstattes av ny AIP-motor. `info.xml`-feltverdiene, indre/yttre METS og kompatibilitet med Arkade 5 er sentrale. Se `DIAS-METADATA-MAPPING.md`. a15-evidenskandidaten i Work er **ikke** en DIAS AIP.

**Produksjonslinjens faglige hendelser:** Mottak/innlevering → validering → kvalitetssikring og arkiveiers kontroll av innhold/proveniens → dokumentert godkjenning, korrigeringskrav eller avvisning → eksisterende DIAS AIP-produksjon og bevaring → etterfølgende forvaltning. Teknisk test-OK er aldri en faglig aksept. Godkjenning/avvisning er en faktisk beslutning uansett hva steget senere betegnes i GUI.

**Godkjennings-/beslutningsrapporten er sentral bevaringsdokumentasjon:** Den skal kunne gjenfinnes fra bevart materiale og forklare hva uttrekket er, faktisk innhold/avgrensning, tilstand ved mottak, kontroller, arkiveiers uttalelser, dokumenterte avvik, begrunnelser, ansvarlig, dato og beslutning. Den er mer enn en teknisk testrapport eller en journalføringskvittering. a14-rapporten er ennå et utkast med uavklarte forhold.

**SIP/AIP/AIC:** Noark 5 kommer normalt som DIAS SIP (`.tar` eller utpakket). DIAS AIP produseres med den **eksisterende** pakkemodulen. AIC kan organisere flere AIP-er; første AIP håndteres i den etablerte modellen, ikke gjennom en alternativ modell innført i a16. Brukeren/depotet avgjør konkret hva som bevares av original SIP, uendret uttrekk, arkivversjoner og tilleggsdokumentasjon. DWM skal ikke innføre normative krav om å bevare eller utelate SIP. Originaler skal ikke endres; forskjeller og relasjoner dokumenteres.

**Innhold og bruk er ulike dimensjoner:** Skill mellom metadata, testgrunnlag, intern/ekstern rapportering, originaluttrekk, arkivversjon, manualer, eksternt produserte filer og andre manuelle tillegg. Det må være mulig å legge inn filer og mapper fra verktøy utenfor DWM; eksisterende DIAS `extra_files` støtter allerede tillegg under sine definerte målmapper. Hvilket materiale som inngår i AIP velges og dokumenteres. Etterfølgende innsyn, analyse, statistikk og CRM-katalog er ikke alternative AIP-varianter og skal ikke diktere AIP-innhold.

**Journalføring:** Arkiveier og depot dokumenterer på hver sin side kommunikasjon og dokumentutveksling i samme leveranseforløp; det er ikke to konkurrerende produksjonsutganger. Depot kan i tillegg ha dypere teknisk bevaringsinformasjon og egne katalog-/CRM-data. En fil kan være relevant flere steder uten at alle arbeidslogger skal bevares i AIP.

**Brukergrensesnitt:** Enkel modus kan foreslå AIP-mål, men faktisk plassering skal vises og kunne velges. a16-koblingskontrollen viser evidenskandidatens status uten å produsere AIP. Den er ikke en ny pakkefunksjon.

**Kilder og teori:** OAIS som begreps- og prosessreferanse, DIAS/Nasjonalarkivets pakkespesifikasjoner, KDRS Produksjonslinje og Arkade 5-praksis er fortsatt sentrale dokumentasjons- og kvalitetssikringsreferanser. Referansene forankrer arbeidet, men brukes ikke til å overstyre depotets etablerte praksis eller fungerende moduler.
