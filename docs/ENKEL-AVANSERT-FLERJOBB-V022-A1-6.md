# v0.2.2-a1.6 – Velg uttrekk først i Enkel modus

**Delta over a1.5.** Programversjonen er fortsatt `0.2.2-a1`. Filformatet `.n5jobs`, DWM-API-et og kjøremotoren endres ikke. Ingen gamle resultater, Source- eller Work-filer flyttes, slettes eller overskrives av GUI-endringen.

## Hva brukeren ser

- **Tom kontroll:** Åpnes direkte på **1. Velg uttrekk**. Ingen tom «Velg uttrekk»-liste eller knapp for å lagre en ikke-eksisterende jobb vises over Source. Den etablerte knappen **Finn uttrekk…** er ett tydelig førstevalg.
- **Navigasjon:** Eksisterende steg presenteres som **1. Velg uttrekk → 2. Arbeidsmappe → 3. Kontroller / kjør → Oversikt**. «Forrige» og «Neste» følger samme rekkefølge. Oversikt er et frivillig sammendrag, ikke et steg som må fullføres først.
- **Ett registrert uttrekk:** En kort, lesbar rad viser aktivt uttrekk i stedet for en meningsløs nedtrekksliste med ett alternativ.
- **To eller flere uttrekk:** Nedtrekkslisten **Bytt uttrekk** vises. Hvert uttrekk beholder egen Source, Work og kontrollvalg. Nytt utkast er et eget valg mens det klargjøres.
- **Legg til uttrekk:** Lager et nytt utkast i den samme kontrollen. Den eksisterende jobblisten og de tidligere uttrekkene beholdes.
- **Ny kontroll:** Starter en ny tom arbeidsflate etter eksisterende sikkerhetsbekreftelse og eventuell lagring. Lagrede kontroller og rapporter beholdes.
- **Lagre:** Brukes for å lagre kontrollen, første gang med filvalg. **Lagre som…** finnes fortsatt under Kjøring/Oversikt og i Avansert modus, men vises ikke dobbelt i den øverste raden.

Det er fortsatt **én felles jobbmodell** for Enkel og Avansert modus. Automatisk registrering ved godkjent Source og Work og automatisk lagring til en eksisterende `.n5jobs` videreføres fra a1.2–a1.5. Et Work-område per jobb, Work-godkjenning, resultatstatus og mulighet for samlet kjøring i Avansert modus er uendret.

## Installasjon

1. Pakk ut `v0.2.2-a1.6.zip` over **a1.5**.
2. Kjør `test.bat` fra repoets rotmappe.
3. Start DWM på nytt.

Ingen ekstra installasjons-, rettelses- eller versjonsskript.

## Praktisk Windows-test

1. Åpne **Enkel modus** og klikk **Ny kontroll**. Bekreft. Du skal stå på **1. Velg uttrekk**, uten øverste uttrekksvelger.
2. Klikk **Finn uttrekk…**, velg et faktisk Noark 5-uttrekk. Gå til **2. Arbeidsmappe** og velg/godkjenn en egen Work-mappe.
3. Kontroller at første uttrekk registreres uten at kontrollene kjøres. Øverst vises **Aktivt uttrekk: JOB-001**. Klikk **Lagre** og gi kontrollen et filnavn.
4. Klikk **Legg til uttrekk**, og registrer to forskjellige uttrekk med hver sin Work-mappe. Nå skal **Bytt uttrekk** vise JOB-001, JOB-002 og JOB-003. Velg hver jobb og kontroller at Source og Work er riktig.
5. Bytt til **Avansert modus** og kontroller at alle tre er synlige i samme jobbliste. Gjenåpne `.n5jobs` og gjenta kontrollen. Det er ikke nødvendig å starte en tung testkjøring.
6. Trykk **Ny kontroll** og verifiser at gammelt arbeid kan åpnes igjen; ingen Work-resultater skal være endret.
7. Prøv **Forrige / Neste**, særlig **1. Velg uttrekk → 2. Arbeidsmappe → 3. Kontroller / kjør**.

## Testgrunnlag og avgrensninger

45 målrettede tester er kjørt i isolert Python-miljø etter påføring av a1.2–a1.6 over testgrunnlaget. Dette omfatter registrering og gjenåpning av tre jobber, sikker nullstilling, oppstartspreferanser, navigasjonsrekkefølge og tilstandsbasert visning av null/én/flere jobber. En kopi av den allerede committede `app/settings_portable.py` ble brukt **kun for den isolerte testen**, og følger ikke med deltaen.

Full `test.bat` og visuell PySide6-kontroll på Windows må fremdeles utføres før commit. Ingen Git-operasjoner er utført.
