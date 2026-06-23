# Lineage Benchmark Profiling Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add optional profiling output to the lineage extractor benchmark so users can identify whether bottlenecks are in schema build, cold extraction, warm extraction, output assembly, or specific hot functions.

**Architecture:** Keep profiling disabled by default. When `--profile cprofile` is selected, wrap benchmark phases with `cProfile`, summarize phase percentages, cache impact, and top cumulative-time functions into the report, and optionally write that profile section to a standalone JSON file.

**Tech Stack:** Python 3.7 standard library `cProfile` and `pstats`, existing benchmark runner, existing benchmark tests.

---

### Task 1: Tests

**Files:**
- Modify: `tests/benchmarks/test_lineage_extractor_benchmark_dataset.py`

- [ ] **Step 1: Add a failing report test**

Add a test that calls `run_benchmark(size="small", complexity="normal", profile="cprofile", profile_output_path=tmp_path / "profile.json", profile_limit=5)` and asserts:

- report contains `profile.mode == "cprofile"`;
- profile output file exists and equals `report["profile"]`;
- `phase_percentages` includes `cold_extraction`;
- `cache_impact.warm_cache_hits == 40`;
- `top_functions` length is at most 5 and contains cumulative seconds.

- [ ] **Step 2: Verify the test fails**

Run:

```bash
make test PYTEST_ARGS='tests/benchmarks/test_lineage_extractor_benchmark_dataset.py::test_run_benchmark_writes_cprofile_report -q'
```

Expected: fail because `run_benchmark` does not accept profiling arguments.

### Task 2: Runner Implementation

**Files:**
- Modify: `benchmarks/lineage_extractor/run.py`

- [ ] **Step 1: Add profiling arguments**

Extend `run_benchmark`, `_run_once`, and CLI with:

- `profile="none"` with choices `none|cprofile`;
- `profile_output_path=None`;
- `profile_limit=20`.

- [ ] **Step 2: Implement cProfile capture**

When enabled, use one `cProfile.Profile()` per benchmark repetition and run each measured phase through a helper. Summarize top functions with `pstats.Stats`.

- [ ] **Step 3: Add profile summary fields**

Add `profile` to the report:

```json
{
  "mode": "cprofile",
  "phase_percentages": {},
  "cache_impact": {},
  "top_functions": []
}
```

Write the standalone profile JSON when `profile_output_path` is set.

### Task 3: Docs and Verification

**Files:**
- Modify: `benchmarks/lineage_extractor/README.md`

- [ ] **Step 1: Document profiling**

Add example commands for `--profile cprofile` and `--profile-output`.

- [ ] **Step 2: Verify**

Run:

```bash
make test PYTEST_ARGS='tests/benchmarks/test_lineage_extractor_benchmark_dataset.py -q'
PYTHONPATH= conda run -n dw-refactor-py37 python benchmarks/lineage_extractor/run.py --size small --complexity stress --profile cprofile --profile-output /tmp/lineage_profile_small_stress.json --output /tmp/lineage_benchmark_small_stress_profiled.json
make test
```
