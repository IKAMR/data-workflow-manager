# External CLI runner

## Status

Introduced in `v0.1.6-a26` as the generic execution boundary for external command-line tools.

The runner is deliberately tool-neutral. Arkade 5, Siegfried and later external tools are expected to be adapters above this layer rather than implementing their own process-launching code.

## Contract

`noark5_workflow.external_tools.cli_runner` provides:

- `ExternalCliRequest`
- `ExternalCliRunResult`
- `run_external_cli()`

The request describes:

- executable
- argv arguments
- optional working directory
- optional environment overrides
- optional timeout
- optional text encoding
- optional stdout/stderr destinations
- optional JSON run-manifest destination
- generic tool / operation / job / run identities
- generic metadata

The runner:

1. executes an argv sequence with `shell=False`
2. captures stdout and stderr separately
3. records exit code, start/end time and duration
4. represents timeout and launch failure as structured results
5. can write stdout and stderr as separate UTF-8 log files
6. can write an atomic JSON execution manifest

## Manifest boundaries

The manifest intentionally does not embed environment values or complete stdout/stderr text. It records:

- command argv
- working directory
- tool/operation/job/run identity
- timestamps and duration
- exit code
- timeout/launch state
- stdout/stderr paths, character counts and SHA-256 values
- caller-supplied metadata

This avoids conflating process output with the execution record and reduces accidental persistence of secrets contained in environment variables.

## Relationship to workflow operations

The external CLI runner is below tool adapters and workflow operations:

```text
DWM job / operation
        |
        v
tool adapter (Arkade 5, Siegfried, ...)
        |
        v
ExternalCliRequest
        |
        v
run_external_cli()
        |
        +--> stdout log
        +--> stderr log
        +--> JSON run manifest
        +--> tool-produced artifacts
```

The runner does not decide where Arkade 5 reports, PRONOM data or other tool-specific outputs belong. That is the responsibility of the adapter/operation using the job's Source / Work / Storage contract.

## Next planned layer

The next Arkade-specific step should define the configured Arkade 5 executable and its detected version, then build Arkade-specific requests on top of this generic runner.
