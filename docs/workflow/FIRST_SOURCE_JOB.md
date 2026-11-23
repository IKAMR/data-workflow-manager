# a15.11 – Første jobb direkte fra Source

Når applikasjonen ikke har noen jobber i det hele tatt, kan første valg av
Source nå opprette `JOB-001` automatisk.

Dette fjerner behovet for:

`Jobber -> Ny jobbliste -> Ny jobb`

i det vanlige tilfellet der brukeren bare skal arbeide med ett uttrekk.

## Sikkerhetsregel

Implicit opprettelse er bare tillatt når jobb-listen faktisk er tom.

Når én eller flere jobber allerede finnes:

- Source-endring oppdaterer aktiv jobb, eller
- en eksisterende jobb med samme Source gjenbrukes,
- men en ny `JOB-xxx` opprettes aldri automatisk.

Dette bevarer den tidligere regresjonsregelen som hindrer at Source-endringer
lager tilfeldige ekstrajobber.

Den automatisk opprettede første jobben arver aktiv profil og gjeldende
brukeridentitet når dette er tilgjengelig.
