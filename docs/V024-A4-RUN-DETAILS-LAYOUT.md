# DWM v0.2.4-a4 - Kjoeredetaljer: layout and persistence

## Scope

GUI and application-local QSettings only. No changes to Noark 5 XPath,
Siegfried/PRONOM, Arkade 5 CLI, operations, execution order, job files,
Work data, result formats, or depot decisions.

## The independent run-details window

The existing a1 `qt/v024/basic_details_vertical_splitter` preference remains
the authority for manually adjusted **plan / lower panels** proportions.
When no preference exists, the default upper height is calculated from the
actual operation row count and row height (17 rows in the full Noark flow),
not from a fixed 53 percent of the available window height. Both panels retain
minimum space and their scroll bars on small screens.

The lower `history_tree` now uses content-aware initial widths with all five
sections set to `QHeaderView.Interactive`, including the operation description
column. The operation description uses spare horizontal space initially, but
can be resized manually like the other columns. The following QSettings keys
apply across all jobs, not separately to JOB-001/002/003:

- `qt/v024_a4/run_history_column_widths`: JSON list of five manually saved widths.
- `qt/v024_a4/run_history_log_splitter`: Qt splitter state for history/events.
- `qt/v024/basic_details_vertical_splitter`: existing a1 outer splitter state.
- `qt/a9_independent_run_geometry`: existing independent window geometry.

Invalid/stale saved column widths fall back to defaults. Legacy a1 outer
splitter state takes precedence over the new content-aware default. Manual
changes are stored immediately and are synced when the window is redocked,
including by the ordinary window close button. The existing run history,
selection and event messages remain owned by their original widgets.

## Safety and testing

No new application-wide Qt event filters or recurring timers. Only the
existing viewer's QSplitter and QHeaderView are observed; geometry settings
are local to the operator and never written to `.n5jobs` or Work. The actual
Qt viewer is not instantiated during headless program startup tests.

1. Run `py -m unittest tests.test_v024_a4_run_details_layout -v` and then
   the complete `test.bat`.
2. Launch DWM on Windows and reopen the already completed a2 job list.
3. Open Kjoeredetaljer for JOB-001. With no saved a1 outer divider preference,
   17 rows should fit without a large unused blank upper region. All history
   columns should be readable; horizontal scrolling is allowed on small windows.
4. Resize all columns manually and drag both vertical dividers. Close the
   viewer using X; open JOB-002 and verify exactly the same layout. Repeat
   with JOB-003 and after restarting DWM.
5. Move the history/log divider in Advanced's independent run viewer and
   verify the setting is shared when opened again from Basic.
6. Confirm status 17/17, stored results, tests and logs are unchanged. Do
   not rerun archives merely to validate a GUI layout preference.

Headless tests verify layout calculations, saved settings, viewer lifecycle and
source-level restrictions. Actual DPI behavior and native Qt sizing require a
Windows GUI check.
