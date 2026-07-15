# Cross-Job Process Table Scenarios Design

Date: 2026-07-15

## Purpose

Add one real cross-Job process-table handoff to both `shop` and
`retail_banking`, then verify that lineage v2, Job DAG v2, field paths, and
strict readers resolve the handoff without guessing or same-name
contamination.

The scenarios must use existing production Jobs rather than standalone demo
Jobs. They must exercise the implementation already added for Job-scoped
process datasets; they must not introduce a second producer resolver, graph,
identifier normalizer, or validation path.

## Selected approach

The process table is the real handoff between an existing producer Job and an
existing consumer Job:

1. The producer drops and recreates a normal table with CTAS.
2. The producer leaves that table present when the Job ends, making it an
   eligible persistent process output.
3. The producer also materializes the existing managed DWS table from the
   process table, preserving the warehouse's managed-layer output.
4. The consumer reads the process table directly.

This is stronger than a side-copy test because the process dataset is the
actual dependency evidence. If producer resolution fails, the consumer loses
its real upstream Job edge instead of being protected by an unrelated managed
table dependency.

The process tables do not receive managed DDL files, model YAML, table IDs, or
column IDs. Their lifecycle and schema are owned by the producer SQL, so the
lineage extractor must classify them as `dataset_type=process`.

## Shop scenario

### Data flow

```text
shop_dm.dwd_order_detail
    -- Job: dws_store_sales_daily -->
shop_dm.stage_store_sales_daily (process)
    -- Job: dim_store_metric_snapshot -->
shop_dm.dim_store_metric_snapshot
```

### Producer

Modify `warehouses/shop/mid/tasks/dws_store_sales_daily.sql`:

- drop `shop_dm.stage_store_sales_daily` at the start of the stage build;
- recreate it with CTAS from `shop_dm.dwd_order_detail` for the current ETL
  slice;
- apply the existing null and invalid-row cleanup to the stage table;
- insert the cleaned stage rows into the existing managed
  `shop_dm.dws_store_sales_daily` table using an explicit column list.

The final create is not followed by a drop. The stage table is therefore a
persistent cross-Job output, even though the Job begins with a defensive drop.

### Consumer

Modify `warehouses/shop/mid/tasks/dim_store_metric_snapshot.sql` so its sales
metrics come from `shop_dm.stage_store_sales_daily` instead of the managed DWS
table. Its store attributes continue to come from `shop_dm.dwd_store`.

The shop Jobs do not have companion full-refresh SQL files, so the existing
`@full_refresh` predicates in their base SQL continue to cover both modes.

## Retail banking scenario

### Data flow

```text
retail_banking_dm.dwd_client_transaction
    -- Job: dws_client_transaction_daily -->
retail_banking_dm.stage_client_transaction_daily (process)
    -- Job: ads_customer_transaction_kpi_daily -->
retail_banking_dm.ads_customer_transaction_kpi_daily
```

### Incremental producer and consumer

Modify `warehouses/retail_banking/mid/tasks/dws_client_transaction_daily.sql`:

- drop and CTAS `retail_banking_dm.stage_client_transaction_daily` for
  `@etl_date`;
- retain the existing grain and reversed-transaction filtering;
- insert the stage rows into the existing managed
  `dws_client_transaction_daily` table.

Modify
`warehouses/retail_banking/ads/tasks/ads_customer_transaction_kpi_daily.sql`
so it reads the stage table for the same ETL date. The ADS calculation and
managed target schema remain unchanged.

### Full-refresh companions

Apply the same handoff to:

- `mid/tasks/full_refresh/dws_client_transaction_daily_full_refresh.sql`;
- `ads/tasks/full_refresh/ads_customer_transaction_kpi_daily_full_refresh.sql`.

The producer companion recreates the process table for the configured
`@etl_start_date`/`@etl_end_date` window, materializes the managed DWS table
from it, and leaves it present. The consumer companion reads that same process
table. This keeps base and companion Job I/O equivalent and avoids a DAG that
is correct only in incremental mode.

## Lineage and DAG expectations

For each project, no new core lineage algorithm is required. Existing
components remain authoritative:

- `sql_task_facts` records reads, writes, creates, drops, and lifecycle facts;
- `build_job_records` produces explicit Job inputs and outputs;
- `resolve_job_dependencies` selects the unique eligible producer;
- `job_dag_from_lineage` serializes evidence-backed Job dependencies;
- the strict lineage and DAG validators reject malformed references;
- `LineageView` and the existing asset graph compose cross-Job field paths.

Expected public facts:

- the stage table has `dataset_type=process`;
- the producer Job lists the stage table in `outputs`;
- the consumer Job lists the stage table in `inputs`;
- `data_dependencies` contains the producer/consumer pair with the stage table
  in `datasets`;
- no `UNRESOLVED_DATASET_PRODUCER` diagnostic is emitted for the stage table;
- no Edge contains `source_file`;
- the field path includes a producer Edge into the stage column and a consumer
  Edge out of that stage column.

## Testing and validation

Add a hermetic, parameterized acceptance test for the two checked-in scenarios.
The test should call existing extraction, strict validation, dependency, and
view/query interfaces. It must not depend on ignored generated artifacts and
must not reimplement identifier matching or graph traversal.

The acceptance assertions cover:

1. process dataset classification;
2. explicit producer output and consumer input;
3. unique Job dependency with process-table evidence;
4. absence of unresolved-producer diagnostics;
5. direct field Edges on both sides of the Job boundary;
6. an end-to-end upstream field path through the process table;
7. base/full-refresh I/O equivalence for the retail banking pair.

Production verification then runs, for both projects:

1. no-cache lineage extraction;
2. public Job DAG generation through `task_run --refresh-dag --validate-only`;
3. `lineage_cli validate`;
4. a focused process-table evidence/path audit;
5. the complete non-API `make test` gate.

Generated JSON and HTML remain ignored local artifacts and are not force-added.

## Error and operational behavior

- A missing or ambiguous process producer remains fail closed: no guessed
  dependency or composed field path is allowed.
- A stale lineage snapshot missing a runnable Job remains blocked by the
  existing runnable-Job validation.
- The process table is rebuilt before each producer execution and intentionally
  remains after the Job, so the downstream Job can read it.
- The scheduler dependency must serialize producer before consumer; parallel
  execution is safe only after this edge exists.
- Because the tables are process assets rather than managed schema assets, the
  schema-ID initialization workflow does not apply to them.

## Code Review requirements

After implementation and verification, perform another whole-change Code
Review with special attention to placement and redundancy:

- no duplicated producer-selection or canonical-identifier logic in tests or
  warehouse helpers;
- no project-specific branching added to core lineage modules when checked-in
  SQL assets and existing interfaces are sufficient;
- no redundant graph traversal or strict validation implementation;
- scenario assertions use public or existing internal interfaces at their
  intended ownership boundary;
- SQL changes preserve existing managed targets, grains, slice predicates, and
  full-refresh behavior;
- process tables are not incorrectly promoted to managed DDL/model assets.

Confirmed correctness findings require regression tests and fixes before the
work is considered ready.
