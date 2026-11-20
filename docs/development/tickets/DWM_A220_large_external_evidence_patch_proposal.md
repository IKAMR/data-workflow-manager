# Developer ticket: A220 fails on large external Arkade/Siegfried evidence

**Target:** Data Workflow Manager v0.2.2  
**Priority:** High — blocks Noark 5 workflow  
**Area:** `Koble Arkade/Siegfried-evidens [A220]`  
**Type:** Bug fix + capacity/diagnostics improvement

## Reproduction and observed error

Workflow fails at A220 after reporting raw result storage:

```text
START: Koble Arkade/Siegfried-evidens [A220]
Koble Arkade/Siegfried-evidens [A220]: Ekstern kildefil overstiger stoerrelsesgrense
FEIL: Koble Arkade/Siegfried-evidens [A220]
Workflow stoppet med feil
```

A separate Qt warning, `fromIccProfile: failed tag offset + size sanity`, is **not** the cause of this failure; handle separately if required.

## Confirmed source-level cause

`noark5_workflow/analysis/canonical_external_import_v0115_a10.py` defines `MAX_FILE = 30_000_000`. `_inside()` rejects a selected external evidence file larger than this and emits the **exact** error above. `analyze_external_results()` calls `_inside()` on each selected file. A220 reaches it through `noark5_workflow/operations/canonical_evidence_v022_a7.py::analyze_external()`.

Other related limits exist and should be reviewed *by purpose*, not blindly unified:

- `canonical_external_import_v0115_a10.py`: `MAX_FILE` (30 MB), including selected source, canonical-result reference, selection recall.
- `canonical_evidence_v022_a7.py`: `MAX_JSON = 100_000_000` for `_read()`.
- `canonical_external_v0115_a5.py`: Siegfried JSON interpreter `MAX_RECORDS = 100000`, `MAX_MATCHES = 1000000`.
- `canonical_matrix_v0115_a11.py`: imports `MAX_FILE` for the *generated analysis output*.
- `canonical_external_import_v0115_a10.py`: `MAX_ITEMS`, `MAX_TOTAL_ITEMS`, `MAX_FILES` guard against excessive result counts.

**Important:** There is no evidence from the log of which specific file exceeds 30 MB. Include its path and size in diagnostics. Do not assume the file is native Siegfried JSON; A220 can process Arkade-normalized inputs too.

## Requested implementation

### 1. Immediate correctness and diagnostics (small patch)

1. Replace the generic `Ekstern kildefil overstiger stoerrelsesgrense` message in `_inside()` with an actionable error containing the Work-relative path, actual bytes/MiB, and configured threshold. Do not reveal sensitive absolute paths in external-facing reports unless the UI is trusted to show them.
2. Distinguish limits for **original external source**, **canonical-results.json**, and **generated canonical-external-analysis.json**. Do not reuse one `MAX_FILE` constant for all three categories.
3. Document a conservative interim upper bound for source JSONs. Raising the existing threshold as a temporary workaround is acceptable only after memory usage is tested with representative evidence. Preserve a finite upper bound. Avoid merely changing `30_000_000` to a very large number and calling the issue fixed.
4. Verify how A220 handles a source exceeding the interim limit: a clear, attributable error, no silent truncation, no partially published output, and clean failure status.
5. Preserve existing Work-relative path containment, symlink rejection, immutable source data, SHA-256 provenance, and atomic output publishing.

### 2. Durable large-file support (preferred fix)

1. For large Siegfried JSON, introduce a streaming/event-driven reader (e.g. a carefully reviewed streaming JSON parser dependency) to accumulate only counts and per-format aggregates. Do not materialize the `files` array or all `matches` in memory.
2. Avoid repeated full-file parsing: `inspect_selected_external()` currently loads `_json(path)` and then calls `inspect_external(path)`, which re-reads/re-parses the file. In A220, normalized Siegfried statistics may be read again using `_read()` after analysis. Arrange format dispatch so each source is parsed only as needed; for already-normalized statistics, use the bounded summary parser directly.
3. For Arkade normalized JSON, retain exact source statuses and the existing interpretation semantics. If a single file cannot be safely processed in full due to per-record or output limits, return an explicit `not_parsed`/capacity explanation or a clear actionable error rather than silently discarding records. Do not accidentally promote partial results to authoritative outcomes.
4. Define limits separately for source bytes, parsed element counts, accumulated output size, and memory. Keep `MAX_ITEMS`, `MAX_TOTAL_ITEMS`, `MAX_RECORDS`, `MAX_MATCHES` protections unless replaced by equivalent safeguards, with meaningful errors.
5. Maintain the existing output contract (`noark5.external-analysis.v1`) unless an intentional, tested schema/version migration is necessary. Preserve original source hash and byte count.
6. On failures, write a useful diagnostic identifying which of the selected evidence sources caused the issue, the category/limit, and the intended remediation. Do not log full source contents.

### 3. Tests / acceptance criteria

- **Regression:** Run A220 against a valid Work with external evidence larger than 30,000,000 bytes; it should no longer fail *solely because of the former arbitrary 30 MB limit*, provided it fits the new documented resource safeguards.
- Test both large native Siegfried JSON and large normalized Arkade/PRONOM JSON in representative shapes.
- Test exact boundary behavior (limit - 1, limit, limit + 1), including error context.
- Test malformed JSON, oversized individual records, excess match/record counts, duplicate selections, paths outside Work, symlinks, and mutated evidence/hash mismatch.
- Verify SHA-256 and byte count are calculated from original unchanged source bytes; do not rewrite source evidence.
- Verify unchanged semantics: Siegfried is **format identification only**, Arkade status is source text, technical validation is unverified, and depot approval remains null.
- Verify no output is published on error; successful publication remains atomic.
- Record peak memory for representative large sources; ensure streaming path has bounded memory relative to file count.
- Verify downstream `load_external_status()`/control matrix can load the produced analysis (including its own output-size cap) and does not mark it stale purely due to an old hardcoded threshold.
- Add focused automated tests to existing `tests/test_v0115_a10_external_import.py` and `tests/test_v022_a7_evidence.py`; add streaming/parser tests as appropriate.

## Suggested implementation order

1. Improve error messages and distinguish size-limit categories; add regression tests.
2. Implement streaming for native Siegfried and eliminate duplicate parsing.
3. Define practical caps for normalized Arkade and generated summary outputs, then test A220 end-to-end and downstream consumers.
4. Document the configured resource limits and operational behavior for large archival datasets.

## Non-goals

- Do not alter Noark 5 requirements, source standards, XPath logic or canonical test outcomes.
- Do not change original Arkade/Siegfried evidence or silently accept incomplete input.
- Do not treat external identification or source-reported statuses as verified pass/fail or depot approval.

## Proposed Git commit message

`Forbedret A220 med skalerbar behandling og presis feilhåndtering for store eksterne evidensfiler v0.2.3`

Adjust the version suffix to the actual version being released; the developer should not commit or push unless explicitly requested by the repository owner.
