# Table Inspector Layer Validation

This benchmark validates cold-start direct model generation when table layer
metadata is missing.

It builds temporary copies of the demo projects, removes explicit layer hints
from table names and SQL comments, separates source/application/middle-layer
assets, runs `run_direct_model_generation` with `table_inspector` enabled for
the middle-layer tables only, and compares generated layers against the
original demo `models/*.yaml` metadata.

## Usage

```bash
export DEEPSEEK_API_KEY=...

python3 benchmarks/table_inspector_layer/run.py \
  --projects shop finance_analytics \
  --model mimo-v2.5-pro \
  --base-url https://token-plan-cn.xiaomimimo.com/v1 \
  --parallel 4 \
  --max-retries 1 \
  --request-timeout 240 \
  --output /tmp/table_inspector_layer_validation.json
```

The benchmark writes only to a temporary project root and the requested output
file. It does not modify the source demo projects. Generated model YAML files
are written under the temporary project root reported as `tmp_dir`, so the
layer result and YAML payload can both be reviewed.

## What It Checks

- Cold-start-like mode: only ODS/ADS seed metadata is retained so those two
  boundary layers are deterministic; DWD/DWS/DIM tables have no layer seed.
- Temporary assets are split into ODS, ADS, and middle-layer directories. ODS
  uses the normal `ods/ddl/internal/benchmark` placement, ADS gets minimal
  seed model metadata, and middle-layer tables are the only LLM candidates.
- Table prefixes such as `ods_`, `dwd_`, `dws_`, `ads_`, and `dim_` are removed
  in the temporary project.
- The benchmark does not append synthetic layer-equivalent suffixes such as
  `_profile`, `_summary`, `_detail`, `_report`, or `_source`; any remaining
  words are inherited from the original functional table name.
- SQL line comments, SQL `COMMENT` clauses, and direct layer words are stripped
  from the temporary DDL/tasks.
- Table inspector layer accuracy is measured over DWD/DWS/DIM only. Final
  layer accuracy is still compared across all tables.
- Metric/entity/grain counts are reported, including whether final ADS tables
  received metrics.
- Generated YAML payloads are written to the temporary project for content
  review.

## Interpreting Results

The result is a project-specific regression signal for the two bundled demo
warehouses. It should not be read as a general cold-start accuracy guarantee:
the demo projects still carry their own functional naming vocabulary, and the
deterministic rules intentionally use common English data-warehouse tokens when
the project has no stronger metadata.

Use the JSON report for three separate checks:

- `table_inspector_accuracy`: DWD/DWS/DIM layer decisions made by the LLM.
- `final_accuracy`: full generated layer after deterministic ODS/ADS signals,
  table inspector output, and fallback rules are combined.
- The generated YAML files under `tmp_dir`: semantic quality of entities,
  grain, metrics, and business assignments.

Known residual risks:

- Strong ADS signals can still over-correct event-grain DWD tables if a project
  uses application-output words in detail table names.
- English naming tokens improve deterministic cold-start behavior for these
  demos, but Chinese or highly local naming vocabularies rely more heavily on
  the LLM and business catalog.
- Empty or weak `business_semantics.yaml` catalogs reduce business process and
  semantic subject assignment quality.
