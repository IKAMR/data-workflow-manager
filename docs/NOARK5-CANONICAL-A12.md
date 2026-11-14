# Kanonisk resultatmodell – v0.1.15-a12

## Kvalitetssikring for arkivskaper (arbeidsutkast)

`noark5_workflow/analysis/canonical_qa_report_v0115_a12.py` genererer en HTML-rapport for gjennomgang og dokumentert tilbakemelding fra arkivskaper. Rapporten er en **egen avledet fil**, og endrer ikke `canonical-results.json`, `canonical-context.json`, `canonical-external-analysis.json` eller Source. Utfil: `Work/noark5_reports/QUALITY_ASSURANCE_DRAFT.html`. Eksisterende utkast erstattes bare etter eksplisitt bekreftelse i GUI.

Rapporten inneholder:

- Identitet for valgt Work-jobb og kontrollprofilens ID, datert utkast.
- Kontrollområder og kravtype fra **versjonert, men ikke godkjent** kontrollprofil.
- DWM-observasjoner og separat antall eksterne testposter, **uten sammenslåing av overlappende resultater**.
- Arkades rapporterte feil/advarsler med test-ID, tekst, arkivdel/kontekst der dataene finnes, og Work-relativ evidenskilde. Maksimalt 250 detaljposter gjengis i ett utkast, med totalantall.
- System/arkivperiode fra Arkade når opplysningene faktisk er dokumentert; disse merkes som *ikke bekreftet av arkivskaper*.
- Konkrete spørsmål om proveniens, arkivskaper, avgrensning, periode, dokumentfiler, avvik og betingede kontroller.
- Blank plass til arkivskapers kommentarer og referanse til senere tilbakemelding/journalpost. Det å fylle ut en utskrift registrerer **ingen** aksept i DWM.
- SHA-256 for kontrollprofil, kanonisk indeks, ekstern analyse og de valgte gyldige kildene.

Rapporten er merket **UTKAST** gjennomgående. Kildestatus, `ok` eller en utført kjøring er ikke automatisk faglig verifikasjon. Den inneholder **ingen automatisk arkivskaperaksept, depotgodkjenning eller bevaringsbeslutning**. Arkivskapers faktiske svar og depotets formelle beslutning krever egne etterfølgende prosesser.

## GUI

I `Rapport → Kanoniske resultatdata…` finnes knappen **KS-rapport til arkivskaper (utkast)…**. Ett bekreftelsestrinn oppretter eller erstatter den avledede HTML-filen i valgt Work. Status og lagringssted vises i samme vindu. Ingen ekstra filvelger. `Dekningsmatrise` og KS-visningen får mer plass nederst ved automatisk høydefordeling; midtdeleren kan fortsatt dras manuelt.

## Kontroller som ikke er ferdigstilt i a12

- DWM har fremdeles ingen faglig godkjent, komplett Noark 5-kontrollprofil; det følger kun `dwm.noark5.draft.v1`.
- Arkivskapers svar, verifisering av proveniens og dokumentasjon av avvikshåndtering kan ikke regnes som utført bare ved å generere et utkast.
- Det er ingen automatisk signatur, godkjenning, ekspedisjon, journalføring eller AIP-pakking.
- Deler av arkivinnholdet må fremdeles dokumenteres fra uttrekkets øvrige analyser for en fullstendig kvalitetssikringsrapport; a12 bruker kun kildeverifiserte opplysninger i den kanoniske modellen og registrert ekstern analyse.
- Den rapporterte Arkade-statusen `error` tilsvarer eksternt kontrollfunn, ikke en egen DWM-godkjenningsbeslutning.

## Lokal test og videre arbeid

Sju målrettede tester kontrollerer sporbarhet, avviksdetaljer, sikker HTML-escaping, jobbsamsvar, arkivskaper-/depotaksept som `None`, skrivegrenser og at originalfiler ikke endres. Seks a11-regresjonstester er også grønne. Full `test.bat` og Windows-GUI/utskriftskontroll må kjøres av bruker.

Neste utvikling: faglig håndtert avvikslogg og registrering av arkivskapers tilbakemeldinger før egen ferdigstillings-/godkjenningsrapport, deretter dokumentert bevaringspakking med inkludert evidens.
