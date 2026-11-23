# v0.2.2-a1.10 - Kontrast i filvelgerens opp-knapp

**Rettelsesdelta over v0.2.2-a1.9.** Programmet viser fortsatt `v0.2.2-a1`; dette er ikke en ny release.

## Bakgrunn og beslutning om plassering

- En kontroll som består av **ett Noark 5-uttrekk** skal fortsatt få forslag om å lagre `.n5jobs` i den etablerte `jobblister`-undermappen under det uttrekkets DWM-Work-område.
- En kontroll som samler **flere uttrekk** kan lagres på et felles nivå når brukeren selv velger det i «Lagre som». DWM skal **ikke** flytte eller endre et tidligere valgt lagringssted automatisk.
- Ingen endringer er gjort i `app/basic_joblist_suggestion_v0113_a3.py`, `app/basic_multijob_v022_a1_2.py`, Work-oppsettet eller lagrings-API-et.

## Rettet feil

Qt sin ikke-native lagredialog tegnet «Opp ett nivå»-knappen med et mørkt standardikon på mørk knappebakgrunn. Det ga for dårlig kontrast, særlig med mørk/grønn fargepalett.

Ny modul: `gui_qt/file_dialog_contrast_v022_a1_10.py`

- Et applikasjonsfilter fanger når en **ikke-native Qt `QFileDialog`** vises.
- Knappen med Qt-navnet `toParentButton` får et tydelig, høy-kontrast opp-pil-ikon, kontrasterende ramme, hover/fokus-markering og norsk verktøytips.
- Ikonfarge velges ut fra den **gjeldende knappepaletten**. Kontrastberegningen bruker svart/hvitt, med minst 4,5:1 mot bakgrunnen.
- Andre knapper, mapper, stier, filnavn, jobblister og brukerens lagringsvalg endres ikke.
- Native systemdialoger blir ikke endret.

## Installasjon

1. Ha alle tidligere deltaer til og med `v0.2.2-a1.9` installert.
2. Pakk ut `v0.2.2-a1.10.zip` over **reporoten**, med overskriving av eksisterende `gui_qt/__main__.py`.
3. Kjør `test.bat`, og start DWM på nytt.
4. Klikk «Lagre» for et nytt uttrekk. Kontrollér at **Opp ett nivå** er tydelig i den mørke Qt-dialogen, og at den går én mappe opp.
5. Kontrollér at standardforslaget fortsatt er i den aktuelle jobbens `dwm`/`jobblister`, og velg bare en annen mappe dersom kontrollen skal samles for flere uttrekk.

**Hurtigtast:** I Qt-dialogen kan `Ctrl+Pil opp` også brukes for å navigere til overordnet mappe.

## Verifisering

- Seks nye målrettede tester for palettkontrast, knappestil, event-filter og oppstartskobling er bestått.
- Tidligere 75 målrettede a1.2–a1.9-tester er kjørt sammen med de nye og består (81 av 81).
- Python-syntaks og ZIP-innhold er verifisert.
- **Visuell Windows/PySide6-test og hele `test.bat` gjenstår hos brukeren.**

Brukeren utfører fortsatt all commit/push selv.
