# Shadow Run Minimal Recompute Design

## Problem

`change_analysis.affected_scope.assessment_tasks` is intentionally broad. It
contains directly changed tables, downstream tables, verification anchors, and
both endpoints of changed lineage edges. `verification_plan` currently converts
that broad set directly into `jobs_to_run`.

When a changed DWS task changes an edge from an unchanged daily DWD table, the
DWD table enters `assessment_tasks`. A monthly ADS anchor then propagates a
monthly window through lineage and assigns 30 daily `execution_values` to that
already-selected DWD job. Shadow-run consequently creates a QA DWD table and
recomputes the unchanged upstream for the whole month, even though manifest
routing can read it from production.

## Responsibilities

- `changed_assets` records which DDL, task SQL, model, and configuration files
  changed.
- `affected_scope` remains the broad impact and assessment scope. Its name and
  structure remain unchanged.
- `jobs_to_run` is the only persisted execution selection.
- `verification` owns final anchors, comparison ranges, checks, warnings, and
  anchor readiness status.
- The compiled shadow manifest owns final SQL relation routing, readiness, and
  prefill actions.

The verification plan no longer persists a top-level `scope`. It does not add
`execution_scope`, read-through candidates, QA-materialization candidates, or
derived aggregate routing classifications.

## Job Selection

The planner selects executable jobs from:

```text
job_candidates = affected_scope.direct_tables
               union affected_scope.downstream_tables
jobs_to_run = topological_order(job_candidates with task SQL)
```

`assessment_tasks` and `lineage_diff.changed_tables` never independently select
jobs. A changed model remains a conservative direct change: if its table has a
task, that task and executable downstream tasks run.

DDL-only tables without task SQL do not become jobs. Their QA structure and any
required production prefill remain manifest responsibilities.

## Anchors And Execution Values

`affected_scope.anchor_tables` remains the change-analysis anchor candidate set.
The verification planner writes its final selected set to
`verification.anchor_tables`, including any SQL-only self-anchor fallback.
`verification.compare_anchors` stores the resolved time column, period, and
anchor value per final anchor.

Execution-window propagation remains lineage-aware. It may traverse unchanged
relations, but it assigns `execution_values` only to entries already present in
`jobs_to_run`.

## Baseline DDL

Both baseline-ref and current-DDL code paths use one required-table set:

```text
verification anchors
union non-Phase-2-CREATE job targets
union ALTER targets
union RENAME old tables
```

Unchanged production-read upstream relations do not enter `baseline_ddl` and
therefore are not selected as QA relations by the compiled manifest.

## Shadow Manifest

Manifest compilation remains the first shadow-run preparation phase and must
finish before resetting the QA database. Existing per-job `data_read`,
`schema_read`, and `write` routes remain authoritative:

- unselected project inputs read production;
- selected producer outputs read QA with readiness dependencies;
- DDL-only QA relations use manifest-generated prefill when required.

No `read_through_prod` or `qa_materialized_only` aggregate is added to the plan,
runtime manifest, or manifest summary. Existing routes, producers, relations,
and prefill actions already expose the facts.

## Compatibility

No old-plan fallback is retained. Consumers stop reading `plan.scope` and
`plan.affected_scope`. Existing refactor runs must rerun `analyze` before
shadow-run or compare.

## Acceptance Criteria

1. An unchanged lineage-edge upstream may remain in `assessment_tables` and
   `assessment_tasks`, but is absent from `jobs_to_run` and `baseline_ddl`.
2. Changed direct jobs and executable downstream jobs remain selected.
3. A changed daily DWD upstream of a monthly anchor still receives all daily
   execution values.
4. An unchanged DWD upstream of the same anchor receives no job entry or
   execution values, and downstream SQL routes its data read to production.
5. DDL-only rename and alter flows continue to materialize and prefill QA
   relations correctly.
6. Shadow-run and dry-run read final anchors from
   `verification.anchor_tables`.
7. Unit tests, the complete non-API suite, and a real shop shadow-run/compare
   validation pass.
