# DWM v0.2.5-a1 – A170 og visningsbytte under kjøring

Utviklingsgrunnlag: `main` etter publisert v0.2.4 og etterfølgende
anonymisering av releasebeskrivelsene. Dette er en **alpha**, ikke en
oppdatering av taggen eller GitHub-releasen v0.2.4.

## A170 – Noark 5-analyse: arkiv og arkivdel

**Feil:** `definition_engine.py` brukte ordinær `tree.xpath()` på brede
`//*[local-name()='...']`-utvalg og `node.xpath('count(.//*[local-name()=...])')`.
For store `arkivstruktur.xml` kan libxml2 bygge svært store mellomliggende
nodemengder og feile med blant annet `growing nodeset hit limit`.
Den separate A130-motorens forbedringer gjaldt ikke denne A170-koden.

**Rettelse:** A170s dokumenterte XPath-deluttrykk for arkiv, arkivdel og
arkivskaper og descendant-opptelling bruker `lxml`-elementiteratorer. Det
bevarer rekkefølge, navneromssamsvar, avgrensning til hver arkivdel,
arkivskapers kildekontekst og eksisterende resultatformat. Andre XPath-
uttrykk og feltuttrykk går fortsatt gjennom den opprinnelige `lxml`-motoren.

Analysedefinisjonen i `config/noark5/analysis/u1_u2_core_arkiv_arkivdel.json`
endres ikke. `noark5_tests/native/noark5-analysis-arkiv-arkivdel.json`
har samme grunnmodell og nøkkelnavn. Feil i andre XPath-uttrykk blir ikke
omgjort til «0 funn» eller «OK», men gir et eksplisitt analyseavvik.

**Avgrensning:** XML-dokumentet leses fortsatt inn med `lxml` som ett tre.
Rettelsen unngår store XPath-node-sett, men er *ikke* full streaming fra disk
for XML-filer som er større enn tilgjengelig minne. Test på det faktiske store
uttrekket kreves før vi kan fastslå at akkurat den produksjonsfeilen er løst.

## Enkel og Avansert modus mens jobb kjører

**Feil:** `_leave_basic()` i flerjobblaget forsøkte å registrere og lagre
valgt jobb selv ved et rent bytte til Avansert modus. Registreringskontrakten
nekter endringer mens en jobb kjører. Dette kunne dermed sperre selve
navigasjonen.

**Rettelse:** Under aktiv kjøring bruker GUI den opprinnelige, rene
Qt-visningsovergangen uten registrering, lagring, endring av jobb-ID,
ny worker eller nye Work-områder. Når ingen jobb kjører, gjelder alle
tidligere kontroller av utkast, endringer og lagring uendret. Ved retur
til Enkel modus vises jobben som faktisk kjører, også når neste jobb i
flerjobbkjøringen er startet i Avansert modus. Stopphandlingen og loggen
gjenbruker eksisterende felles kjører.

`gui_qt/__main__.py` viderefører dessuten v0.2.4-a5 sin asynkrone
Arkade 5-/Siegfried-kontroll; denne må ikke forsvinne ved GUI-bytte.

## Test

Kjør fra repoets rot på utviklingsgrenen:

```bash
py -m unittest discover -s tests -p "test_v025_a1*.py" -v
MSYS_NO_PATHCONV=1 cmd.exe /c test.bat
```

Kjente, obligatoriske manuelle kontroller i Windows/Qt:

1. Start en eksisterende flerjobbliste fra Enkel modus. Bytt til Avansert
   og tilbake flere ganger mens en deljobb arbeider. Kontroller at fremdrift,
   aktiv jobb, Kjøredetaljer, logg og Stop følger samme kjøring.
2. La neste jobb starte mens Avansert modus vises. Gå til Enkel og kontroller
   at neste kjørende jobb er vist uten at `.n5jobs`/Work er skrevet om.
3. Gjenta når jobben kjører A170 på et stort, reelt Noark 5-uttrekk.
   Kontroller `noark5_tests/native` og opptelling per arkivdel, og sammenlign
   med uavhengige kontroller. Ikke bland teknisk fullført og faglig godkjent.
4. Kontroller at «Lagre», jobbvalg og endring av Source/Work fortsatt er
   sperret under kjøring. Kjør også et normalt visningsbytte uten aktiv jobb.
5. Kontroller at GUI fortsatt finner/viser installert Arkade 5 og Siegfried
   i Setup, og at SAFE MODE starter.

Automatiserte tester er utført isolert på Linux med syntetisk XML og Qt-fri
simulering. Det verifiserer *ikke* reell Windows-/PySide6-navigasjon eller
fullt Windows-`test.bat`. Ingen release eller Git-tag er opprettet av deltaet.
