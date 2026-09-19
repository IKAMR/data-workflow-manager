# a15.8 – Start klare

The Jobber window now exposes `Start klare`.

It runs only jobs that:

- have at least one workflow operation, and
- are `Klar` or `Venter`.

Completed jobs are not rerun. `Venter` keeps the existing checkpoint/continue
semantics. Jobs with no workflow are not silently treated as runnable.

The Jobber summary also shows `Kjørbare nå: N`.

`Start alle` is deliberately unchanged and remains the explicit path for batch
reruns that can include previously completed jobs.
