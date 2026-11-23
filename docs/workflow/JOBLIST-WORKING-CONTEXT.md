# Jobbliste som arbeidskontekst

Status: v0.1.6-a27.1

## Beslutning

Data Workflow Manager arbeider alltid i en **jobblistekontekst**.

En jobbliste kan inneholde én eller mange jobber. En bruker som bare arbeider
med ett uttrekk bruker derfor samme modell som en bruker som behandler 6, 28
eller flere uttrekk; forskjellen ligger i brukergrensesnitt og arbeidsmåte,
ikke i en separat enkeltjobbmodell.

Arbeidskonteksten består av:

- gjeldende jobbliste
- aktiv jobb i jobblista
- eventuell lagret filsti for jobblista
- jobbens posisjon i gjeldende jobbliste

En jobbliste er fortsatt en gyldig arbeidskontekst når den ennå ikke er lagret
på fil.

## Autoritativ tilstand

a27.1 lager **ikke** en ny parallell, muterbar jobbliste.

Eksisterende runtime-tilstand er fortsatt autoritativ:

- `self.jobs`
- `self.current_job`
- `self.job_list_path`

`JobListContext` er en skrivebeskyttet projeksjon av disse verdiene. Dette
hindrer at senere hovedvindu-, batch-, CLI- eller serverfunksjoner begynner å
holde hver sin kopi av hva som er aktiv jobbliste eller aktiv jobb.

## Invarianter

Ved grenser som krever en komplett arbeidskontekst gjelder:

1. jobblista må inneholde minst én jobb
2. det må finnes en aktiv jobb
3. aktiv jobb må være en jobb i gjeldende jobbliste

Eksisterende DWM-flyt som oppretter en første blank jobb i en ny jobbliste
beholdes. a27.1 endrer ikke opprettelse, lagring, lasting eller kjøring av
jobber.

## Videre bruk

Denne kontrakten er grunnlaget for senere a27-steg:

- jobbkontekst og navigasjon i hovedvinduet
- samme handlinger for aktiv jobb og valgte jobber
- batchredigering av workflows
- felles begreper for aktiv, valgt, klar og alle jobber
- senere serverbasert kjøring av én eller flere jobblister

Serverstøtte implementeres ikke i a27.1; modellen skal bare unngå å låse
klientkoden til en egen «single-job mode».
