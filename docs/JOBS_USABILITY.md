# Jobber usability – a15.6

a15.6 improves the Jobber overview without changing the job model.

## Stable batch display

When the job identity and order are unchanged, `JobsWindow.refresh()` updates
existing labels and buttons in place. It no longer destroys and rebuilds every
job row for each progress event. Structural changes such as discovery, delete
or reordering still rebuild the list.

The run log remains free to update continuously.

## Mapper directly from Jobber

Each job row has a `Mapper` action. It opens the existing per-job storage-role
dialog without first making the job active or closing the Jobber overview.

## Standard setup for one job

Each job row has a `Standard` action. It uses the currently selected:

- storage layout profile
- Noark 5 discovery workflow

The action previews the change and requires confirmation before replacing
different existing role/workflow values. Existing result files on disk are not
deleted.
