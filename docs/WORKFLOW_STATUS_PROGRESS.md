# a15.9 – workflow status and progress

## Status icons

The current runtime explicitly connects `WorkflowPanel.status_provider` to the
authoritative per-operation status function.

The active workflow is refreshed at runner state boundaries and again after a
job completes. This makes the existing icon vocabulary visible in normal use:

- green check: completed/current result
- blue running icon: operation currently running
- orange stale icon: result invalidated by newer upstream result
- red error icon: failed operation
- grey dash: not run/no current result
- the remaining existing review/skip/partial states are preserved

## Progress

The bottom status line now adds workflow context to the operation's own
progress message:

`JOB-003 | Operasjon 4/6 | Test 34/57 - F08 / N5.42 - Skjerminger`

The inner operation message remains authoritative. The new operation counter
does not pretend that all operations take equal time.
