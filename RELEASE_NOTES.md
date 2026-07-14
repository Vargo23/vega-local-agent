# VEGA v2.11.0 Release Notes

VEGA v2.11.0, **Runtime Diagnostics Evolution**, adds a unified local observer
for runtime health and bounded execution-trace inspection. It does not add a new
tool execution path, new permissions, remote telemetry, autonomous execution, or
automatic publishing.

## Highlights

* Immutable, manually serialized runtime diagnostics reports.
* `/doctor`, `/doctor help`, `/doctor trace status`, `/doctor trace latest`,
  `/doctor trace summary`, and explicit `/doctor export`.
* Atomic UTF-8 JSON export to a fixed project-relative report directory.
* Validated bounded retention for reports and execution trace backups.
* Bounded active-plus-backup scanning and deterministic trace aggregates.
* Backward-compatible reading of valid v2.10 JSONL trace records.

## Runtime report

The report contains only allowlisted machine fields: VEGA identity, UTC creation
time, fixed status/error codes, production snapshot counts, safe model state,
document/chunk counts, memory-entry count, terminal-policy command count, bounded
trace state and aggregates, and release-file booleans.

It never contains prompts, raw user text, history, evidence, file or patch
contents, tool arguments/results, stdout/stderr, query-bearing URLs, absolute
user paths, environment dumps, tokens, credentials, confirmation/session data,
raw exceptions, tracebacks, callables, handlers, or callbacks.

## Explicit local export

`/doctor export` is the only operation that creates a report. It writes a bounded
UTF-8 JSON document using a same-directory temporary file, flush, `fsync`, and
atomic replacement. Filenames are UTC-based and CLI output includes only the
relative path. Users cannot supply an alternate export path.

Retention touches only exact `doctor-YYYYMMDDTHHMMSSffffffZ.json` filenames.
Unknown files are preserved, scanning is capped, and a retention failure does not
invalidate a successfully completed new report.

## Trace retention and summary

Tracing remains disabled by default and is enabled only through the existing
`VEGA_EXECUTION_TRACE` opt-in. The active trace limit remains 5 MiB. The default
policy retains `.1`, `.2`, and `.3` backups and caps scanned files and records.
Corrupt and oversized records are skipped with fixed diagnostic codes.

`/doctor trace latest` remains compatible with v2.10. `/doctor trace summary`
reports only terminal status counts, safe error-code counts, safe request-type
counts, and corrupt-record totals.

## Security boundaries

Diagnostics are observers only. They do not invoke tools, plans, handlers,
confirmation callbacks, models, network services, or shell commands; they do not
change permissions, routing, synthesis, or request results. Configuration,
serialization, scan, rotation, and export failures fail closed and expose only a
small fixed error vocabulary.

All policy paths are relative, normalized, confined to the project root, checked
against blocked directories and symlink escape, and bounded by non-configurable
hard caps. Generated traces and reports are ignored by Git.

## Migration impact

No data migration is required. Existing valid v2.10 traces remain readable. The
new tracked `config/diagnostics_policy.json` supplies defaults; generated files
remain local. Integrations using `append_trace`, `load_latest_trace`,
`serialize_trace`, `format_trace_summary`, `/doctor`, or `/doctor trace latest`
continue to work.

## Validation

The release is validated by focused runtime diagnostics, trace, doctor, release
tool, command, and consistency tests followed by the complete pytest suite,
`compileall`, identity, production policy consistency, smoke test, Release
Manager, and `git diff --check`.

## Known limitations

* Trace persistence is opt-in.
* Reports are local-only; remote telemetry is absent.
* Trace locking is process-local and is not interprocess locking.
* Model installation is not probed by launching a model from the report builder.
* Automatic publishing is absent and all publishing policy flags remain false.
