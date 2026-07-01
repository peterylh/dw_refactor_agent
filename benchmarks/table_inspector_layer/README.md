# Table Inspector Layer Validation

This benchmark validates direct model generation when table layer metadata is
missing.

It builds temporary copies of the demo projects, removes explicit layer hints
from table names and SQL comments, runs `run_direct_model_generation` with
table inspector layer fallback, and compares generated layers against the
original demo `models/*.yaml` metadata.

## Usage

```bash
export DEEPSEEK_API_KEY=...

python3 benchmarks/table_inspector_layer/run.py \
  --projects shop finance_analytics \
  --model deepseek-v4-pro \
  --base-url https://api.deepseek.com \
  --parallel 4 \
  --output /tmp/table_inspector_layer_validation.json
```

The benchmark writes only to a temporary project root and the requested output
file. It does not modify the source demo projects.
