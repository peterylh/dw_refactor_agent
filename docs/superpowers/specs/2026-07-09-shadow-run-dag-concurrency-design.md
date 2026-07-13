# Shadow Run DAG Concurrency Design

## Goal

Enable refactor shadow-run Phase 3 to run jobs with no outstanding DAG dependencies concurrently, while keeping `--parallel` as the single concurrency knob.

## Scope

Phase 0 through Phase 2 stay serial:

- Reset QA database.
- Create baseline tables.
- Apply DDL changes.

Only Phase 3 job execution changes.

## Behavior

`--parallel 1` keeps the current serial behavior.

When `--parallel > 1`, shadow-run schedules ready jobs from the `jobs_to_run` subgraph:

- Jobs with zero in-degree are ready immediately.
- A downstream job becomes ready only after all upstream jobs in the plan succeed.
- Failed jobs stop new submissions. Already running work is allowed to finish before returning a failed result.
- Result JSON remains compatible with existing consumers.

`--parallel` is a global mysql session cap. A running unit is one mysql invocation batch, not `job_parallel * slice_parallel`. With `--parallel 4 --batch-size 2`, at most four mysql sessions execute at the same time across all jobs, and each session may replay up to two slice invocations.

## Dependency Source

The scheduler uses dependencies between entries already present in `jobs_to_run`. The dependency source should match the verification plan's lineage-derived ordering:

- Prefer a dependency map embedded in the plan if present in the future.
- For this implementation, derive dependencies from the existing lineage DAG artifact for the project.
- If dependencies cannot be loaded, fall back to serial `jobs_to_run` order and emit a warning in the run result.

## Result Shape

Existing job result fields stay unchanged:

- `job`
- `file`
- `layer`
- `target`
- `status`
- `error`
- `execution_values`
- `invocation_count`
- `batch_count`
- `parallelism`
- `batch_size`
- `invocations`

The `run_jobs` phase may include optional scheduler metadata:

- `parallelism`
- `scheduler`
- `warnings`

## Testing

Add regression tests for:

- Independent jobs run concurrently when `--parallel > 1`.
- Dependent jobs wait for upstream completion.
- Failed jobs prevent downstream submission.
- Existing sliced job batch concurrency behavior remains intact.

## Performance Check

Use the shop project to compare dry-run scheduling overhead and, where a valid manifest/database is available, real shadow-run elapsed time with `--parallel 1` versus a higher value.
