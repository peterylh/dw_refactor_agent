# Lineage Extractor Benchmark Design

## Goal

Provide a standard, repeatable performance benchmark suite for
`dw_refactor_agent.lineage.lineage_extractor`. The suite should exercise a realistic number
of tables, task files, columns, joins, filters, aggregations, CTEs, and layered
warehouse dependencies without polluting the existing `shop` or
`finance_analytics` assets.

The benchmark is a standalone performance tool, not part of the functional
test suite under `tests/lineage`.

## Non-Goals

- Do not add runtime-sensitive performance thresholds to the default test
  command.
- Do not require Doris, MySQL, network access, or external services.
- Do not write generated benchmark assets into `warehouses/shop/` or
  `warehouses/finance_analytics/`.
- Do not make `tests/lineage` responsible for performance measurement.

## Location

Add a dedicated benchmark package:

```text
benchmarks/
  lineage_extractor/
    README.md
    __init__.py
    dataset.py
    run.py
```

`dataset.py` owns deterministic SQL and DDL generation. `run.py` owns the CLI,
timing, extractor invocation, cache comparison, and report output.

## Dataset Sizes

Use three fixed scale profiles:

| Size | Tables | Tasks | Approx Columns | Purpose |
|------|-------:|------:|---------------:|---------|
| `small` | 50 | 40 | 800-1,200 | quick smoke benchmark |
| `medium` | 300 | 240 | 6,000-8,000 | default optimization comparison |
| `large` | 1,000 | 800 | 20,000-28,000 | stress benchmark |

Layer distribution:

| Size | ODS | DWD | DWS | ADS | Tasks |
|------|----:|----:|----:|----:|------:|
| `small` | 10 | 20 | 15 | 5 | 40 |
| `medium` | 60 | 120 | 80 | 40 | 240 |
| `large` | 200 | 400 | 260 | 140 | 800 |

Default CLI size is `medium`. `large` is opt-in because runtime depends heavily
on local CPU, Python version, process startup cost, and sqlglot behavior.

## Generated SQL Shape

The generator produces a temporary synthetic project under a caller-selected
output directory, defaulting to a temp directory. Each run uses stable table
names and SQL text for the same size profile.

DDL characteristics:

- Doris-style `CREATE TABLE` statements under a synthetic database.
- ODS and DWD tables contain 20-30 columns.
- DWS tables contain 18-24 columns.
- ADS tables contain 12-20 columns.
- Common data types include `BIGINT`, `INT`, `DATE`, `DATETIME`,
  `DECIMAL(18,2)`, and `VARCHAR`.

Task characteristics:

- ODS to DWD tasks with direct field mapping, casts, `CASE WHEN`, and
  constants.
- DWD to DWS tasks with `JOIN`, `WHERE`, `GROUP BY`, `SUM`, `COUNT`, `AVG`,
  and derived metric expressions.
- DWS to ADS tasks joining multiple upstream summaries.
- A controlled subset of tasks uses CTEs.
- Every generated task references existing generated DDL so missing-schema
  diagnostics indicate a benchmark bug.

The generator must also return expected structural counts, including table
count, task count, and a minimum expected lineage edge count. The benchmark
runner verifies these before writing a successful report.

## Command Model

Primary command:

```bash
python benchmarks/lineage_extractor/run.py --size medium
```

Useful options:

```bash
python benchmarks/lineage_extractor/run.py --size small
python benchmarks/lineage_extractor/run.py --size large --parallel 4
python benchmarks/lineage_extractor/run.py --size medium --repeat 3
python benchmarks/lineage_extractor/run.py --size medium --keep-assets
python benchmarks/lineage_extractor/run.py --size medium --output benchmark.json
```

Add a Makefile target:

```bash
make benchmark-lineage
```

The target should run the medium profile with the project Python interpreter:

```make
PYTHONPATH= $(PYTHON) benchmarks/lineage_extractor/run.py --size medium
```

## Timing Model

Each benchmark run measures these phases separately:

- dataset generation;
- schema build from generated DDL text;
- cold extraction with no task cache;
- warm extraction using the task cache produced by the cold run;
- lineage output assembly with `build_lineage_output`.

For `--repeat N`, the runner records each repetition and reports min, max, and
average elapsed seconds for the cold and warm extraction phases. It should not
hide individual run values because they are useful for spotting noisy local
measurements.

## Report

The runner prints a compact text summary and can write a JSON report.

JSON fields:

```json
{
  "benchmark": "lineage_extractor",
  "size": "medium",
  "parallel": 1,
  "repeat": 1,
  "python_version": "3.7.x",
  "sqlglot_version": "26.9.0",
  "dataset": {
    "tables": 300,
    "tasks": 240,
    "columns": 7200
  },
  "results": [
    {
      "generation_seconds": 0.0,
      "schema_build_seconds": 0.0,
      "cold_extraction_seconds": 0.0,
      "warm_extraction_seconds": 0.0,
      "output_build_seconds": 0.0,
      "direct_edges": 0,
      "indirect_edges": 0,
      "warnings": 0,
      "errors": 0,
      "warm_cache_hits": 240
    }
  ]
}
```

The report is for comparison, not pass/fail gating. A run fails only when the
extractor reports fatal diagnostics, generated structural counts do not match
the selected profile, or lineage output is obviously incomplete.

## Cache Behavior

The cold pass calls `extract_lineage_from_task_files` without a previous cache.
The warm pass writes the cold task cache to a temporary file and passes it back
as `previous_cache_file`.

Expected warm behavior:

- every unchanged generated task should be a cache hit;
- warm extraction should still aggregate task results and rebuild final output;
- cache correctness is validated by comparing cold and warm edge counts.

## Functional Test Boundary

No benchmark should live under `tests/lineage`. Functional tests may cover only
small deterministic helpers if needed, such as:

- profile definitions sum to the advertised table and task counts;
- generated small-profile SQL can build a schema and produce lineage entries.

Those helper tests should not assert elapsed time and should not be named or
treated as performance tests.

## Error Handling

The runner exits non-zero when:

- an unknown size profile is requested;
- generated assets are internally inconsistent;
- lineage extraction reports fatal diagnostics;
- warm cache hits are fewer than generated task count;
- cold and warm output edge counts differ.

When `--keep-assets` is set, the runner prints the generated asset directory so
failed SQL can be inspected.

## Documentation

`benchmarks/lineage_extractor/README.md` explains:

- what the benchmark measures;
- why it is outside `tests/lineage`;
- how to run small, medium, and large profiles;
- how to compare two runs before and after optimization;
- why results should be compared on the same machine and Python environment.

## Implementation Notes

Use existing public extractor functions where possible:

- `build_schema_from_texts`;
- `extract_lineage_from_task_files`;
- `build_lineage_output`;
- `_fatal_diagnostics` only if no public diagnostic helper exists.

The benchmark should not require changes to production `lineage_extractor`
behavior. If implementation reveals a missing stable interface, add the narrow
helper needed by the benchmark and cover it with a functional unit test.
