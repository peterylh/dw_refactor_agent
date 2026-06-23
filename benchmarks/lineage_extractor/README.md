# Lineage Extractor Benchmark

## Purpose

This benchmark measures `lineage/lineage_extractor.py` on deterministic
synthetic warehouse assets. It is intended for local performance comparison
before and after extractor changes, especially changes involving SQL parsing,
schema lookup, field-level lineage extraction, task parallelism, or task cache
behavior.

It does not require Doris, MySQL, network access, or existing project data.

## Dataset Sizes

| Size | Tables | Tasks | Approx Columns | Use |
|------|-------:|------:|---------------:|-----|
| `small` | 50 | 40 | 800-1,200 | quick smoke benchmark |
| `medium` | 300 | 240 | 6,000-8,000 | default optimization comparison |
| `large` | 1,000 | 800 | 20,000-28,000 | stress benchmark |

The generated SQL covers ODS to DWD mappings, DWD to DWS aggregations, DWS to
ADS joins, filters, grouping, derived expressions, and a controlled subset of
CTEs.

## Task Complexity

Size controls how many tables and tasks are generated. Complexity controls how
much work each generated task contains.

| Complexity | Behavior | Use |
|------------|----------|-----|
| `normal` | one target write per task, with joins, filters, CTEs, and aggregations | stable default baseline |
| `high` | deterministic subsets of tasks create one temporary table before the final insert | transient table overhead |
| `stress` | deterministic subsets of tasks create two-step temporary table chains before the final insert | transient lineage stress |

Temporary table profiles use `CREATE TEMPORARY TABLE ... AS SELECT ...` inside
the task file. The final target insert reads from the generated temporary
table, so the extractor must parse multi-statement tasks, preserve transient
table metadata, and rebuild final output from task-level lineage entries.

## Running

Use the project Python environment. The default Make target runs the medium
profile:

```bash
make benchmark-lineage
```

Run specific profiles directly:

```bash
PYTHONPATH= conda run -n dw-refactor-py37 python benchmarks/lineage_extractor/run.py --size small
PYTHONPATH= conda run -n dw-refactor-py37 python benchmarks/lineage_extractor/run.py --size medium --complexity high
PYTHONPATH= conda run -n dw-refactor-py37 python benchmarks/lineage_extractor/run.py --size medium --repeat 3 --output benchmark.json
PYTHONPATH= conda run -n dw-refactor-py37 python benchmarks/lineage_extractor/run.py --size large --complexity stress --parallel 4 --keep-assets
```

Use `--keep-assets` when debugging generated SQL. The runner prints the asset
directory when assets are retained.

## Comparing Runs

Run the same command before and after an extractor change on the same machine,
Python environment, and `sqlglot` version. Prefer `--repeat 3` for medium or
large comparisons so local noise is visible.

The JSON report records individual run timings. Compare cold extraction,
warm-cache extraction, output build time, edge counts, and cache hits.

## Interpreting Results

The benchmark fails only for correctness problems such as fatal diagnostics,
incomplete lineage output, cold/warm edge-count mismatches, or missing warm
cache hits. It does not enforce a universal elapsed-time threshold because
runtime varies by CPU, process startup overhead, Python version, and local
system load.

Warm extraction should report one cache hit per generated task. Cold and warm
edge counts should match.

## Why This Is Outside tests/lineage

`tests/lineage` is for deterministic functional coverage. Performance
measurement is intentionally separate because benchmark runtime and timing
results are environment-sensitive. The default test suite only checks small,
fast helper behavior for the benchmark generator and runner.
