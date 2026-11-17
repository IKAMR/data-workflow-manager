# DWM v0.2.2-a3 – utviklerkontroll

- Base GitHub: `b3ded0f7883cca55b376bb636fe2312ce0eebc8e` (v0.2.2-a2).
- Nytt/erstattet: `gui_qt/main_v020_a6.py`; `gui_qt/qa_workflow_v022_a3.py`; `noark5_workflow/reporting/qa_workflow_v022_a3.py`; `noark5_workflow/reporting/qa_export_v022_a3.py`; `tests/test_v022_a3_qa_workflow.py`; denne dokumentasjonen.
- Python `py_compile` av endrede `.py`: bestått.
- Isolerte a3-unit tester med lokale teststubber for eksisterende a12/a13-grensesnitt: **10 bestått** (opprettelse, kildebinding, uendret Source, integritet, kildeversjonsbytte, status, privat kommentar, historisk RAF, atomisk eksport og cleanup).
- Faktisk DWM-modulimport, komplette regresjonstester (`test.bat`), GUI-oppstart og Windows/PySide6: **ikke kjørt i utviklingsmiljøet** (full repo-/GUI-runtime ikke tilgjengelig). Utføres av brukeren før commit.
- Ingen applikasjonsversjon, `VERSION`, oppstartspolicy eller globale Qt-eventfiltre er endret.
