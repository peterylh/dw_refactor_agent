# Lineage Benchmark Complexity Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `--complexity normal|high|stress` to the lineage extractor benchmark, with high/stress profiles generating more complex task SQL that includes transient table chains.

**Architecture:** Keep size and complexity as independent benchmark dimensions. `dataset.py` owns complexity-specific SQL generation while preserving the current `normal` output by default; `run.py` passes the selected complexity through, records it in text/JSON reports, and keeps cache validation unchanged.

**Tech Stack:** Python 3.7 standard library, existing `lineage.lineage_extractor`, existing benchmark package and tests.

---

### Task 1: Dataset Complexity Dimension

**Files:**
- Modify: `benchmarks/lineage_extractor/dataset.py`
- Modify: `tests/benchmarks/test_lineage_extractor_benchmark_dataset.py`

- [ ] **Step 1: Write failing tests**

Add tests that call `generate_dataset("small", tmp_path, complexity="high")` and `generate_dataset("small", tmp_path, complexity="stress")`. The high test should assert that at least one generated task contains `CREATE TEMPORARY TABLE` and that extraction returns transient tables. The stress test should assert that a task contains at least two `CREATE TEMPORARY TABLE` statements and extraction succeeds.

- [ ] **Step 2: Verify tests fail**

Run:

```bash
make test PYTEST_ARGS='tests/benchmarks/test_lineage_extractor_benchmark_dataset.py -q'
```

Expected: fails because `generate_dataset` does not accept `complexity`.

- [ ] **Step 3: Implement complexity-aware generation**

Add `COMPLEXITIES = {"normal", "high", "stress"}` and pass complexity through `generate_dataset`, `_dwd_task_sql`, `_dws_task_sql`, and `_ads_task_sql`. Preserve current SQL for `normal`. For `high`, generate transient table SQL for a deterministic subset of DWD/DWS tasks. For `stress`, generate a two-step transient table chain for a deterministic subset of DWD/DWS/ADS tasks.

- [ ] **Step 4: Verify dataset tests pass**

Run:

```bash
make test PYTEST_ARGS='tests/benchmarks/test_lineage_extractor_benchmark_dataset.py -q'
```

Expected: PASS.

### Task 2: Runner and Documentation

**Files:**
- Modify: `benchmarks/lineage_extractor/run.py`
- Modify: `benchmarks/lineage_extractor/README.md`

- [ ] **Step 1: Write failing runner assertions**

Extend the report test so `run_benchmark(..., complexity="high")` returns JSON with `"complexity": "high"` and still reports full warm cache hits.

- [ ] **Step 2: Verify runner test fails**

Run:

```bash
make test PYTEST_ARGS='tests/benchmarks/test_lineage_extractor_benchmark_dataset.py::test_run_benchmark_writes_json_report -q'
```

Expected: fails because `run_benchmark` does not accept `complexity`.

- [ ] **Step 3: Implement runner support**

Add `complexity="normal"` to `run_benchmark`, `_run_once`, and CLI parsing. Include `complexity` in JSON report and text summary. Pass it to `generate_dataset`.

- [ ] **Step 4: Update README**

Document `--complexity normal|high|stress`, explain transient table behavior, and add one command that runs `--complexity high`.

### Task 3: Verification

**Files:**
- All modified files.

- [ ] **Step 1: Run focused tests**

Run:

```bash
make test PYTEST_ARGS='tests/benchmarks/test_lineage_extractor_benchmark_dataset.py -q'
```

- [ ] **Step 2: Run high complexity small benchmark**

Run:

```bash
PYTHONPATH= conda run -n dw-refactor-py37 python benchmarks/lineage_extractor/run.py --size small --complexity high --output /tmp/lineage_benchmark_small_high.json
```

- [ ] **Step 3: Run stress complexity small benchmark**

Run:

```bash
PYTHONPATH= conda run -n dw-refactor-py37 python benchmarks/lineage_extractor/run.py --size small --complexity stress --output /tmp/lineage_benchmark_small_stress.json
```

- [ ] **Step 4: Run default tests and lint**

Run:

```bash
make test
```
