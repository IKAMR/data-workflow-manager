# DWM v0.2.2-a1.13 - Native Windows crash diagnostics

## Reported failure

Windows exits Python/Qt with -1073741819 (0xC0000005, access violation).
The previous start-debug.bat captured an empty stdout/stderr log. This is
consistent with a native crash rather than an ordinary Python exception.
Removing the a1.11 column hook in a1.12 did NOT resolve the observed crash.
Its root cause remains unknown.

## Changes

- Optional, flushed startup milestones in `gui_qt/__main__.py`, enabled only
  for a diagnostic start (`DWM_CRASH_DIAG=1`). The normal application has
  the same GUI feature path as a1.12.
- `start-debug.bat` enables `PYTHONFAULTHANDLER=1`, unbuffered output and
  stage recording to `%TEMP%\dwm-startup-debug.log`. A native Windows access
  violation may now print Python stack frames as well as the last milestone.
- `start-safe.bat` is a temporary isolation option: it skips the optional
  file-dialog arrow filter, popup positioning filter and basic auto-resizing
  during that one start. It does not reset settings or modify job files.
- Pure Python tests cover normal GUI startup wiring, safe-mode wiring and
  diagnostics logging. They do not prove that a Windows C++ crash is fixed.

## Test in order

1. Apply the delta over a1.12; no commit.
2. Run `start-debug.bat` from the DWM root.
3. If Windows still returns 0xC0000005, share the last 30-60 lines of
   `%TEMP%\dwm-startup-debug.log` (redact usernames/paths if desired).
4. Then try `start-safe.bat`. Report whether the window remains open.
5. If both crash with no Python frames, inspect Windows Event Viewer >
   Windows Logs > Application > Application Error (event 1000) and share
   the faulting module name and exception code.

## Safety

No changes to Source, Work, AIP, `.n5jobs`, execution engine or global
configuration. Existing three-job list can be opened after GUI recovery.
No changes committed or pushed.
