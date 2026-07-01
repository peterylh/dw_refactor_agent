# Table Inspector Layer Benchmark

This benchmark validates `TableInspector` layer inference when table layer
metadata is missing.

It builds temporary copies of the demo projects, removes explicit layer hints
from table names and SQL comments, runs `TableInspector`, and compares inferred
layers against the original demo `models/*.yaml` metadata.

## Usage

```bash
export DEEPSEEK_API_KEY=...

python3 lineage/lineage_extractor.py --project shop --parallel 4
python3 lineage/lineage_extractor.py --project finance_analytics --parallel 4

python3 benchmarks/direct_layer_llm/run.py \
  --projects shop finance_analytics \
  --runner table-inspector \
  --model deepseek-v4-pro \
  --base-url https://api.deepseek.com \
  --parallel 4 \
  --request-timeout 180 \
  --output /tmp/table_inspector_layer_validation.json
```

`--runner` can be:

- `table-inspector`: benchmark full `TableInspector` layer inference on the
  no-layer temporary project (default).
- `direct`: benchmark the lightweight direct-model layer fallback added for
  `run_direct_model_generation`, when that helper exists on the current branch.
- `both`: run both benchmarks and write comparable results into one output
  file.

The benchmark writes only to a temporary project root and the requested output
file. It does not modify the source demo projects, except for the optional
lineage extraction commands above, which write `lineage/lineage_data.json` under
each source project.

If source lineage files are missing, the benchmark can still build a temporary
project, but it falls back to table-only lineage data with no edges. Run lineage
extraction first when comparing layer accuracy.
