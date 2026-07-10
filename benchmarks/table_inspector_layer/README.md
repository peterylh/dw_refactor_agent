# Generate LLM Cold-Start Benchmark

This benchmark evaluates the real cold-start `generate --llm` metadata flow.
It copies the bundled warehouse projects into a temporary repo root, removes
explicit layer hints from table names, DDL, and task SQL, runs
`run_generate_model_metadata(..., api_key=..., update_catalog=True)`, then
compares the generated metadata against the source project model YAML files.

The source projects are never modified. Temporary assets are created under:

```text
<tmp_root>/warehouses/{source_project}_generate_llm_benchmark
```

By default the temporary root is kept and reported in JSON so generated YAML can
be inspected after the run. Pass `--cleanup` to delete only the managed
temporary root after the benchmark. `--asset-dir` is never deleted.

## Usage

```bash
export DEEPSEEK_API_KEY=...
PYTHONPATH=src python3 benchmarks/table_inspector_layer/run.py \
  --projects shop finance_analytics \
  --model deepseek-v4-pro \
  --base-url https://api.deepseek.com \
  --parallel 4 \
  --max-retries 1 \
  --request-timeout 240 \
  --output /tmp/generate_llm_cold_start_benchmark.json
```

From `make`:

```bash
make benchmark-generate-llm
```

Override make variables such as `BENCHMARK_GENERATE_LLM_OUTPUT`,
`BENCHMARK_GENERATE_LLM_MODEL`, `BENCHMARK_GENERATE_LLM_BASE_URL`,
`BENCHMARK_GENERATE_LLM_PARALLEL`, and `BENCHMARK_GENERATE_LLM_PROJECTS` as
needed.

## What It Builds

For each source project, the benchmark creates a temporary project with:

- `warehouse.yaml` pointing to the benchmark project and ODS database.
- `naming_config.yaml` copied from the source project.
- `business_taxonomy.yaml` copied only for artificial taxonomy inputs:
  `data_domains` and `business_areas`. Source `project_context` is omitted so
  project-specific layer decisions cannot enter the LLM prompt.
- Empty `business_processes.yaml` and `semantic_subjects.yaml`, so process and
  subject discovery can be measured rather than seeded.
- Rewritten ODS, MID, and ADS DDL.
- Rewritten MID and ADS task SQL, including `full_refresh` companions.
- An `artifacts/lineage/lineage_data.json` snapshot extracted from the rewritten
  DDL and task SQL, using the same lineage extractor as normal projects.
- Layer labels for the target, upstream, and downstream tables are hidden from
  the LLM; the prompt keeps only prefixless names and unlabeled lineage.

Table prefixes `ods_`, `dwd_`, `dws_`, `ads_`, and `dim_` are removed. SQL line
comments, DDL `COMMENT` clauses, and direct layer words such as ODS/DWD/DWS/ADS
and their Chinese equivalents are removed. Business function words are kept.
Prefix matching and SQL identifier rewriting are case-insensitive. When two
tables collapse to the same prefixless name, every colliding table receives an
opaque HMAC suffix keyed by a fresh in-memory salt for that benchmark run. The
salt is not written to assets or reports, and generated assets/prompts do not
contain the source-to-target mapping. For post-run scoring and audit, mismatch
entries in the JSON report include both the source name and its opaque target
alias.

## Metrics

Top-level report fields include:

- `combined_llm_middle_accuracy`: raw LLM `inferred_layer` accuracy over only
  expected DWD/DWS/DIM tables, before resolver or model-write corrections.
- `total_catalog_change_count`: process/subject catalog additions or updates.
- `total_business_process_count` and `total_semantic_subject_count`: generated
  catalog entry counts.

Each project summary includes table counts, generated model counts, warning and
blocked counts, LLM middle-layer accuracy, expected-layer breakdowns, confusion
data, final layer distribution for sanity checking, metric/entity/grain counts,
middle-layer mismatches, and `catalog_summary`.

`catalog_summary` compares generated business process and semantic subject
codes against the original source catalog, reporting expected codes, generated
codes, overlap codes, and overlap counts.

## Interpreting Results

ODS and ADS are asset-boundary layers in the current metadata writer. They are
not sent to table_inspector, so they are not included in the benchmark accuracy
score. Their generated layer counts are reported only as a boundary sanity
check.

DWD, DWS, and DIM tables are the LLM candidate set. Their LLM decision quality
is reported as `llm_middle_accuracy`.

Use mismatches as the main review queue for middle-layer decisions. The
temporary project path in `tmp_root` contains the generated model YAML and split
catalog files for manual inspection.
