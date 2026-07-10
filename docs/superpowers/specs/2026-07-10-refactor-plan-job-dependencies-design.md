# Refactor Plan Job Dependencies Design

## Goal

Make every newly generated refactor verification plan carry the exact job
dependency subgraph derived from that run's current lineage. Shadow-run must
schedule exclusively from the plan and must not depend on a mutable project
`job_dag.json` artifact.

## Source Of Truth

`run analyze` already builds run-local current lineage and passes it to
`build_verification_plan()`. The plan builder constructs one in-memory
`JobDAG` from that lineage and reuses it to:

- topologically order executable jobs;
- derive the induced dependency subgraph for those jobs.

The project-level `job_dag.json` remains available to normal ETL execution,
but is not an input to refactor plan generation or shadow-run.

## Plan Contract

`verification/plan.json` includes a required `job_dependencies` object. Keys
are every job name in `jobs_to_run`; values are sorted lists of upstream job
names that are also present in `jobs_to_run`.

```json
{
  "jobs_to_run": [
    {
      "job": "dwd_order_detail",
      "file": "warehouses/shop/mid/tasks/dwd_order_detail.sql",
      "layer": "DWD",
      "target": "dwd_order_detail"
    },
    {
      "job": "dws_product_sales_daily",
      "file": "warehouses/shop/mid/tasks/dws_product_sales_daily.sql",
      "layer": "DWS",
      "target": "dws_product_sales_daily"
    }
  ],
  "job_dependencies": {
    "dwd_order_detail": [],
    "dws_product_sales_daily": ["dwd_order_detail"]
  }
}
```

Empty and one-job plans still emit complete dependency objects: `{}` and
`{"job_name": []}` respectively.

## Shadow Validation

Shadow-run validates dependencies before dry-run planning or any database
operation. Validation rejects:

- a missing or non-object `job_dependencies` value;
- duplicate or invalid job names in `jobs_to_run`;
- missing or unknown dependency keys;
- non-list upstream values;
- unknown, duplicate, or self dependencies;
- dependency cycles.

After validation, Phase 3 reports `scheduler: "plan"` and uses the validated
in-degree and adjacency maps. Project DAG loading, serial fallback, and the
missing-artifact warning are removed.

## Error Handling

Invalid plans fail fast with `ValueError` before QA database reset. This is a
plan-generation or plan-integrity error, not a runtime job failure, and must
not silently change scheduling semantics.

## Verification

Automated tests cover plan generation, deterministic dependency output,
strict validation, dependency scheduling, failure propagation, and the
absence of project DAG fallback. Real shop validation regenerates current
lineage, builds a verification plan from shop tasks, confirms the project
`job_dag.json` is absent, and verifies that the plan dependency graph matches
the current lineage-induced subgraph and exposes parallel-ready layers.
