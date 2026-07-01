# Table Inspector Layer Validation

This benchmark validates cold-start direct model generation when table layer
metadata is missing.

It builds temporary copies of the demo projects, removes explicit layer hints
from table names and SQL comments, runs `run_direct_model_generation` with
`table_inspector` enabled, and compares generated layers against the original
demo `models/*.yaml` metadata.

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

- Cold-start mode: `ignore_existing_models=True` and `write_scope=all`.
- All tables are sent to `table_inspector` when layer inference is enabled.
- Table prefixes such as `ods_`, `dwd_`, `dws_`, `ads_`, and `dim_` are removed
  in the temporary project.
- SQL line comments, SQL `COMMENT` clauses, and direct layer words are stripped
  from the temporary DDL/tasks.
- Final layer accuracy is compared with the source project model metadata.
- Metric/entity/grain counts are reported, including whether final ADS tables
  received metrics.
- Generated YAML payloads are written to the temporary project for content
  review.

## Latest Local Validation

The latest validation was run on 2026-07-01 with `mimo-v2.5-pro`,
`parallel=4`, and `request_timeout=240`.

| Project | Final Layer Accuracy | Table Inspector Accuracy | ADS | ODS | DWD | DWS | Metrics |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `shop` | 26/29 (89.7%) | 20/29 changed | 7/8 | 8/8 | 3/3 | 5/6 | 25 |
| `finance_analytics` | 55/59 (93.2%) | 51/59 (86.4%) | 4/4 | 17/17 | 15/18 | 3/3 | 99 |

Key checks from this run:

- No read timeouts with `request_timeout=240`.
- ODS/source tables stayed final `ODS` in both projects.
- Final ADS tables did not receive metric groups.
- ADS recognition improved substantially after adding application-output
  signals such as `topn`, `roi`, `rfm`, `alert`, `performance`, `by_*`, and
  non-periodic `summary`.

Known residual risks:

- Strong ADS signals can still over-correct event-grain DWD tables, especially
  names containing `alert` or ROI-like derived fields without `GROUP BY`.
- Some DWS periodic aggregate tables can still be pulled toward ADS if the LLM
  treats zero downstream usage as application output.
- Empty or weak `business_semantics.yaml` catalogs reduce business process and
  semantic subject assignment quality.
