# Noark 5-standardverdier

Maskinlesbare standardverdier ligger i `config/noark5/standards/noark5_standard_values.json`. Kilden er Riksarkivets/Arkivverkets metadatakataloger for Noark 5 v3.1, v4.0 og v5.0.

Første a23-trinn dekker M050 arkivstatus, M051 arkivdelstatus, M052 saksstatus, M053 journalstatus, M054 dokumentstatus, M082 journalposttype, M217 tilknyttetRegistreringSom, M300 dokumentmedium og M700 variantformat.

Journalstatus er et konkret eksempel på hvorfor versjonsmodellen er nødvendig: v3.1/v4.0 har seks oppførte obligatoriske verdier, mens v5.0 har fire.

Standardverdier og generisk observerte verdier er komplementære. Registeret skal ikke brukes til å filtrere bort observerte verdier. `additional_observed_values` er evidens for vurdering, ikke automatisk testfeil.

## Status for observerte verdier

Standardverdilaget skiller mellom tre tilstander:

- `no_observed_values` – feltet har ingen observerte verdier i uttrekket
- `all_observed_values_standard` – det finnes observerte verdier, og alle finnes i standardsettet for den aktuelle versjonen
- `additional_observed_values` – det finnes én eller flere observerte verdier som ikke finnes i standardsettet

`no_observed_values` er ikke det samme som at alle observerte verdier er standardverdier. Fravær av verdi skal derfor kunne vurderes separat senere.

Statusen er observasjon/evidens og er ikke i seg selv en endelig faglig feilklassifisering.


## a23 – videre kildeverifiserte standardsett

a23 utvider registeret med standardverdier som er verifisert mot den offisielle
metadatakatalogen for Noark 5 v5.0, blant annet korrespondanseparttype,
slettingstype, kassasjonsvedtak, tilgangsrestriksjon, skjermingsmetadata,
skjerming av dokument og gradering.

Viktig: disse nye settene registreres foreløpig bare for v5.0. a23 antar ikke
at samme ordlyd eller rolle gjelder i v3.1/v4.0 uten egen kildeverifikasjon.
Dette er et bevisst prinsipp for å unngå at kunnskap fra én Noark-versjon
kopieres bakover som om den var normativ.

For M500 tilgangsrestriksjon skiller registeret mellom obligatorisk verdi og
valgfrie verdier. Sammenligningsmotoren rapporterer fortsatt observerte verdier;
den gjør ikke valgfrie eller lokale verdier til automatisk feil.

## Profilforankring

Standardverdiregisteret er del av Noark 5-profilen og skal oppdages via `config/noark5/profile.json`. Kildegrunnlaget registreres i `config/noark5/standards/sources.json`.

## Relation to metadata registry

Each registered standard-value set is linked to its Noark metadata identifier. a23 also exposes these verified relationships through the version-specific metadata registry under `config/noark5/standards/metadata/`.

The metadata registry is intentionally partial. It does not claim datatype, occurrence or structural placement until those properties have been verified against the official specification.
