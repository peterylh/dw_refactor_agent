# Model Design Assessment

## Summary

Add model design assessment capabilities to `assess` while preserving the existing score/check/issue report model. The work introduces a project-level business semantics catalog, full `models/*.yaml` initialization and refresh flows, and a renamed `model_design` assessment dimension that first focuses on fact grain clarity and layer boundary problems.

The implementation should remain Git-native. Tools write deterministic, reviewable file changes to the working tree, and users review with `git diff` / `git add -p`. No separate proposal or accept workflow is needed for the first version.

## Goals

- Initialize a business semantics catalog for a project from DDL, task SQL, lineage, comments, and optional existing metadata.
- Initialize missing `models/*.yaml` as completely as possible, including layer, table type, business metadata, entities, grain, and metrics.
- Refresh existing models from the accepted catalog and optional LLM classification.
- Replace the assessment concept of `architecture` with `model_design`, with a compatibility alias for the old CLI name.
- Implement first-phase model design checks for layer boundaries and fact table grain clarity.
- Keep reports compatible with existing `score`, `rule_summary`, `checks`, and `issues` structures.

## Non-Goals

- Do not add a separate proposal/accept storage workflow.
- Do not require users to hand-author a full business dictionary before first use.
- Do not let LLM calls freely invent stable business codes during normal model refresh.
- Do not rewrite DDL, task SQL, table names, or file names as part of this feature.

## Business Semantics Catalog

Introduce a project-level catalog as the single source of truth for business semantics:

`business_taxonomy.yaml` is the only source for human-maintained data
domains and business areas:

```yaml
version: 1
project: shop
data_domains:
  - id: "04"
    code: ORDR
    name: 订单域
business_areas:
  - id: SHOP
    code: SHOP
    name: 零售业务
```

`business_processes.yaml` and `semantic_subjects.yaml` hold LLM-discovered
processes and subjects. Their `data_domain` / `business_area` values are only
used when the same codes are confirmed by `business_taxonomy.yaml`.

Default paths:

```text
{project_dir}/business_taxonomy.yaml
{project_dir}/business_processes.yaml
{project_dir}/semantic_subjects.yaml
```

Examples:

```text
warehouses/shop/business_taxonomy.yaml
warehouses/shop/business_processes.yaml
warehouses/shop/semantic_subjects.yaml
warehouses/finance_analytics/business_taxonomy.yaml
warehouses/finance_analytics/business_processes.yaml
warehouses/finance_analytics/semantic_subjects.yaml
```

The catalog belongs with the warehouse project assets so it can be maintained
next to `ddl/`, `tasks/`, and `models/`. Shared helpers may still live under
`src/dw_refactor_agent/assessment/project_facts`, but generated project catalogs should not default to
the `assess` package directory.

The catalog is initialized by
`python -m dw_refactor_agent.assessment.business_semantics_catalog --llm` or
`python -m dw_refactor_agent.assessment.llm.model_metadata_writer --catalog-from-llm` using table-level
inspection contexts rather than raw full-project prompt dumps. Each context
summarizes table name, layer hints, DDL columns and comments, keys, task SQL
features, lineage, upstream/downstream tables, and any existing model/LLM
metadata.

The discoverer may use LLM clustering to identify candidate business processes,
semantic subjects, and their table assignments. Data domains and business
areas are governed anchors from `business_taxonomy.yaml`; naming configuration
does not define or backfill those master data values. The output is written
directly to the working tree only when requested; review is done with Git.

## Models Initialization

Current model writing can create YAML files from the accepted catalog, so an
empty or incomplete `models` directory can be bootstrapped without a separate
proposal/accept workflow.

Command shape:

```bash
PYTHONPATH=src python -m dw_refactor_agent.assessment.llm.model_metadata_writer --project shop --from-catalog --write-scope business --dry-run
PYTHONPATH=src python -m dw_refactor_agent.assessment.llm.model_metadata_writer --project shop --from-catalog --write-scope business
```

Initialization writes stable base metadata and catalog-backed business
semantics. Further LLM model inspection can then add entities, grain and metric
groups:

```yaml
version: 2
name: dwd_order_detail
layer: DWD
table_type: fact
data_domain: SALE
business_area: ORDER
description: 订单明细事实表
config:
  materialized: incremental
entities:
  - code: ORDER_ITEM
    type: natural
    key_columns: [order_item_id]
  - code: ORDER
    type: foreign
    key_columns: [order_id]
atomic_metrics:
  - name: sale_amount
    business_process: order_sale
derived_metrics: []
calculated_metrics: []
```

Rules for writing model YAML:

- Preserve unknown existing keys.
- Keep stable key ordering to minimize Git diff noise.
- Respect `--write-scope`.
- Avoid wholesale reformatting when only a subset of fields changes.
- Emit a result JSON containing changed files, skipped tables, confidence, and validation warnings.

## Models Refresh

After the catalog changes, refresh table-level metadata from the catalog:

```bash
PYTHONPATH=src python -m dw_refactor_agent.assessment.llm.model_metadata_writer --project shop --from-catalog --write-scope business --dry-run
PYTHONPATH=src python -m dw_refactor_agent.assessment.llm.model_metadata_writer --project shop --from-catalog --write-scope business
```

`--from-catalog` means the accepted catalog is the governed code dictionary.
This path does not call LLM; table assignment is owned by `models/*.yaml`, and
the catalog enriches existing `business_process` / `semantic_subject`
references with domain and area metadata.

LLM classification is needed before or after this deterministic refresh when:

- A table or metric lacks a business process.
- Existing free-text process values need mapping to catalog codes.
- Catalog changes split or merge previous processes.
- Program evidence has multiple plausible process candidates.

Use `--catalog-from-llm` or
`python -m dw_refactor_agent.assessment.business_semantics_catalog --llm` for
that discovery step, then review the catalog with Git before refreshing models.

Suggested write scopes:

```text
table      layer/table_type/description/config
business   data_domain/business_area/business_process
metrics    atomic_metrics/derived_metrics/calculated_metrics
grain      entities/grain
all        all writable metadata
```

## Git Review Flow

Use Git as the review and accept mechanism:

```bash
PYTHONPATH=src python -m dw_refactor_agent.assessment.business_semantics_catalog --project shop --llm --overwrite
PYTHONPATH=src python -m dw_refactor_agent.assessment.llm.model_metadata_writer --project shop --from-catalog --write-scope business
git diff
git add -p
```

The tools should:

- Check for a dirty working tree before broad writes and warn clearly.
- Support `--dry-run` for reports without writes.
- Print changed file summaries after writes.
- Avoid preview/proposal directories in the first version.

## Assessment Dimension

Rename the top-level assessment dimension from `architecture` to `model_design`.

Compatibility:

- `--model-design` is the preferred CLI flag.
- `--architecture` remains as a temporary alias.
- Existing report structures remain unchanged inside each dimension.
- Existing architecture dependency rules move under `model_design` rule categories.

CLI dimension selection should be generalized. If no dimension flags are provided, run the default full assessment for compatibility. If one or more dimension flags are provided, only run those dimensions:

```bash
PYTHONPATH=src python -m dw_refactor_agent.assessment.assess_middle_layer --project shop --model-design
PYTHONPATH=src python -m dw_refactor_agent.assessment.assess_middle_layer --project shop --model-design --metadata-health
PYTHONPATH=src python -m dw_refactor_agent.assessment.assess_middle_layer --project shop
```

`model_design` rule categories:

```text
dependency_boundary  reverse, same-layer, skip-layer dependencies
layer_boundary       DWD/DWS/DIM/FCT responsibility mismatches
grain_design         fact table grain and DWS grain alignment
metric_design        metric additivity and DWD non-atomic metric risks
dimension_design     dimension/fact responsibility mixing
```

## First-Phase Checks

### Layer Boundary

Implement checks that identify:

- DWD fact tables with `GROUP BY` or aggregate expressions.
- DWS fact tables without aggregation or without clear grain metadata.
- DIM tables with measure-like fields or metric groups.
- DWD fact tables containing derived or calculated metrics.
- LLM-inferred layer/table type conflicts with declared model metadata.

These checks belong under `model_design.layer_boundary` or `model_design.metric_design`.

### Fact Grain Clarity

Implement checks that identify:

- DWS `grain.entities` / `grain.time_column` inconsistent with SQL `GROUP BY`.
- DWS select-list fields that are neither aggregated nor grouped.
- DWS missing grain metadata.
- DWD fact tables with aggregation.
- DWD fact tables missing event-key or transaction-key candidates.
- DWD fact tables carrying metrics from multiple business processes.

The mixed business process check should use the catalog. Multiple dimension foreign keys do not mean mixed process. A risk is raised when multiple process codes are supported by event-key, metric, or fact-like upstream evidence.

Evidence should include:

```json
{
  "detected_processes": ["order_sale", "refund"],
  "process_evidence": {
    "order_sale": ["order_item_id", "sale_amount"],
    "refund": ["refund_id", "refund_amount"]
  },
  "fact_like_upstreams": ["ods_order_item", "ods_refund"]
}
```

## LLM Boundaries

Program rules should provide the first pass and evidence. LLM calls should be reserved for semantic tasks:

- Discovering and clustering the initial catalog.
- Classifying a table or metric into existing catalog codes.
- Resolving conflicts or ambiguous process candidates.
- Explaining low-confidence model design issues.

LLM results should be validated against DDL columns, catalog codes, model schema, and lineage facts before writing.

## Validation

Add validation for the catalog:

- Each business process maps to an existing business area.
- Each business area maps to an existing data domain.
- Model references to process, area, and domain codes exist in the catalog.
- Model process mappings are consistent with declared area/domain mappings.

Add model write validation:

- Entity key columns exist in DDL.
- Grain entities exist in `entities`.
- Grain time column exists in DDL.
- Metric columns exist in DDL.
- `business_process` values exist in the catalog unless marked `unknown` or `new_candidate`.

## Testing

Add unit tests for:

- Catalog loading and validation.
- Empty-model initialization from DDL/task/lineage facts.
- Catalog-constrained model refresh with and without LLM.
- CLI dimension selection.
- `architecture` alias behavior.
- Layer boundary checks.
- DWS grain versus `GROUP BY` checks.
- DWD mixed-business-process risk checks.

Keep API-dependent tests marked separately and avoid requiring DeepSeek for default non-API test runs.

## Rollout

1. Add catalog data model, loader, and validator.
2. Add model initialization and catalog-constrained refresh support.
3. Rename assessment dimension to `model_design` with `architecture` compatibility alias.
4. Implement first-phase layer boundary checks.
5. Implement first-phase fact grain clarity checks.
6. Add mixed business process detection using catalog evidence.
7. Add CLI dimension selection and focused tests.
