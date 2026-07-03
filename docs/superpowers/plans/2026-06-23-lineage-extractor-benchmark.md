# Lineage Extractor Benchmark Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a standalone, deterministic benchmark suite for `lineage/lineage_extractor.py` with small, medium, and large synthetic datasets.

**Architecture:** Add a focused `benchmarks/lineage_extractor` package. `dataset.py` generates deterministic DDL and task SQL into a temporary synthetic project, while `run.py` times schema build, cold extraction, warm-cache extraction, and output assembly using existing lineage extractor APIs. Functional tests stay outside `tests/lineage` and validate only structural generation behavior.

**Tech Stack:** Python 3.7 standard library, existing `sqlglot`, existing `lineage.lineage_extractor`, Makefile target using the configured `$(PYTHON)`.

---

### Task 1: Benchmark Dataset Generator

**Files:**
- Create: `benchmarks/__init__.py`
- Create: `benchmarks/lineage_extractor/__init__.py`
- Create: `benchmarks/lineage_extractor/dataset.py`
- Test: `tests/benchmarks/test_lineage_extractor_benchmark_dataset.py`

- [ ] **Step 1: Write failing profile and generation tests**

Create `tests/benchmarks/test_lineage_extractor_benchmark_dataset.py` with:

```python
from benchmarks.lineage_extractor.dataset import (
    PROFILES,
    generate_dataset,
)
from lineage.lineage_extractor import (
    build_schema_from_texts,
    extract_lineage_from_task_files,
)


def test_profiles_match_advertised_counts():
    assert set(PROFILES) == {"small", "medium", "large"}

    for profile in PROFILES.values():
        assert profile.table_count == (
            profile.ods_tables
            + profile.dwd_tables
            + profile.dws_tables
            + profile.ads_tables
        )
        assert profile.task_count == (
            profile.dwd_tables + profile.dws_tables + profile.ads_tables
        )


def test_small_dataset_generation_is_structurally_consistent(tmp_path):
    dataset = generate_dataset("small", tmp_path)

    assert dataset.profile.name == "small"
    assert dataset.table_count == 50
    assert dataset.task_count == 40
    assert len(dataset.ddl_files) == 50
    assert len(dataset.task_files) == 40
    assert 800 <= dataset.column_count <= 1200
    assert dataset.expected_min_edges >= dataset.task_count

    names = [path.name for path in dataset.task_files[:3]]
    assert names == [
        "dwd_fact_0000.sql",
        "dwd_fact_0001.sql",
        "dwd_fact_0002.sql",
    ]


def test_generated_task_can_build_lineage(tmp_path):
    dataset = generate_dataset("small", tmp_path)
    schema = build_schema_from_texts(
        [path.read_text(encoding="utf-8") for path in dataset.ddl_files],
        default_catalog=dataset.catalog,
        default_db=dataset.database,
    )

    result = extract_lineage_from_task_files(
        [dataset.task_files[0]],
        dataset.tasks_dir,
        schema,
        parallel=1,
        cache_project=dataset.project_name,
    )

    assert result["errors"] == []
    assert len(result["lineage"]) >= 8
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
make test PYTEST_ARGS='tests/benchmarks/test_lineage_extractor_benchmark_dataset.py -q'
```

Expected: FAIL because `benchmarks.lineage_extractor.dataset` does not exist.

- [ ] **Step 3: Implement deterministic dataset generation**

Create `benchmarks/__init__.py` as an empty package marker.

Create `benchmarks/lineage_extractor/__init__.py` as an empty package marker.

Create `benchmarks/lineage_extractor/dataset.py` with:

```python
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class BenchmarkProfile:
    name: str
    ods_tables: int
    dwd_tables: int
    dws_tables: int
    ads_tables: int

    @property
    def table_count(self):
        return (
            self.ods_tables
            + self.dwd_tables
            + self.dws_tables
            + self.ads_tables
        )

    @property
    def task_count(self):
        return self.dwd_tables + self.dws_tables + self.ads_tables


@dataclass(frozen=True)
class BenchmarkDataset:
    profile: BenchmarkProfile
    root_dir: Path
    ddl_dir: Path
    tasks_dir: Path
    ddl_files: tuple
    task_files: tuple
    table_count: int
    task_count: int
    column_count: int
    expected_min_edges: int
    project_name: str = "lineage_benchmark"
    catalog: str = "internal"
    database: str = "lineage_benchmark_dm"


PROFILES = {
    "small": BenchmarkProfile("small", 10, 20, 15, 5),
    "medium": BenchmarkProfile("medium", 60, 120, 80, 40),
    "large": BenchmarkProfile("large", 200, 400, 260, 140),
}


def generate_dataset(size, root_dir):
    profile = _profile(size)
    root = Path(root_dir)
    ddl_dir = root / "ddl"
    tasks_dir = root / "tasks"
    ddl_dir.mkdir(parents=True, exist_ok=True)
    tasks_dir.mkdir(parents=True, exist_ok=True)

    ddl_files = []
    task_files = []
    column_count = 0

    for index in range(profile.ods_tables):
        columns = _ods_columns()
        ddl_files.append(
            _write_table_ddl(
                ddl_dir,
                "ods_event_{:04d}".format(index),
                columns,
                "DUPLICATE KEY(id)",
            )
        )
        column_count += len(columns)

    for index in range(profile.dwd_tables):
        columns = _dwd_columns()
        table_name = "dwd_fact_{:04d}".format(index)
        ddl_files.append(
            _write_table_ddl(
                ddl_dir,
                table_name,
                columns,
                "UNIQUE KEY(id)",
            )
        )
        task_files.append(_write_task(tasks_dir, table_name, _dwd_task_sql(index, profile)))
        column_count += len(columns)

    for index in range(profile.dws_tables):
        columns = _dws_columns()
        table_name = "dws_summary_{:04d}".format(index)
        ddl_files.append(
            _write_table_ddl(
                ddl_dir,
                table_name,
                columns,
                "DUPLICATE KEY(stat_date, customer_id, product_id)",
            )
        )
        task_files.append(_write_task(tasks_dir, table_name, _dws_task_sql(index, profile)))
        column_count += len(columns)

    for index in range(profile.ads_tables):
        columns = _ads_columns()
        table_name = "ads_report_{:04d}".format(index)
        ddl_files.append(
            _write_table_ddl(
                ddl_dir,
                table_name,
                columns,
                "DUPLICATE KEY(report_date, customer_id, product_id)",
            )
        )
        task_files.append(_write_task(tasks_dir, table_name, _ads_task_sql(index, profile)))
        column_count += len(columns)

    return BenchmarkDataset(
        profile=profile,
        root_dir=root,
        ddl_dir=ddl_dir,
        tasks_dir=tasks_dir,
        ddl_files=tuple(sorted(ddl_files)),
        task_files=tuple(sorted(task_files)),
        table_count=profile.table_count,
        task_count=profile.task_count,
        column_count=column_count,
        expected_min_edges=profile.task_count * 8,
    )
```

The final implementation may split helper bodies below the dataclasses, but it must provide `_ods_columns`, `_dwd_columns`, `_dws_columns`, `_ads_columns`, `_write_table_ddl`, `_write_task`, `_dwd_task_sql`, `_dws_task_sql`, `_ads_task_sql`, and `_profile`. Generated SQL must use the fixed database `lineage_benchmark_dm`.

- [ ] **Step 4: Run tests and fix generation details**

Run:

```bash
make test PYTEST_ARGS='tests/benchmarks/test_lineage_extractor_benchmark_dataset.py -q'
```

Expected: PASS.

### Task 2: Benchmark Runner CLI

**Files:**
- Create: `benchmarks/lineage_extractor/run.py`
- Modify: `tests/benchmarks/test_lineage_extractor_benchmark_dataset.py`

- [ ] **Step 1: Add runner tests**

Append to `tests/benchmarks/test_lineage_extractor_benchmark_dataset.py`:

```python
import json

from benchmarks.lineage_extractor.run import run_benchmark


def test_run_benchmark_writes_json_report(tmp_path):
    report_path = tmp_path / "report.json"

    report = run_benchmark(
        size="small",
        parallel=1,
        repeat=1,
        output_path=report_path,
        asset_dir=tmp_path / "assets",
        keep_assets=True,
    )

    assert report["benchmark"] == "lineage_extractor"
    assert report["size"] == "small"
    assert report["dataset"]["tables"] == 50
    assert report["dataset"]["tasks"] == 40
    assert len(report["results"]) == 1
    assert report["results"][0]["warm_cache_hits"] == 40
    assert report["results"][0]["errors"] == 0
    assert report_path.exists()
    assert json.loads(report_path.read_text(encoding="utf-8")) == report
```

- [ ] **Step 2: Run runner test to verify it fails**

Run:

```bash
make test PYTEST_ARGS='tests/benchmarks/test_lineage_extractor_benchmark_dataset.py::test_run_benchmark_writes_json_report -q'
```

Expected: FAIL because `benchmarks.lineage_extractor.run` does not exist.

- [ ] **Step 3: Implement the runner**

Create `benchmarks/lineage_extractor/run.py` with:

```python
#!/usr/bin/env python3
import argparse
import json
import platform
import shutil
import sys
import tempfile
import time
from pathlib import Path

import sqlglot

from benchmarks.lineage_extractor.dataset import PROFILES, generate_dataset
import dw_refactor_agent.config as config
import dw_refactor_agent.lineage.lineage_extractor as lineage_extractor


def run_benchmark(
    size="medium",
    parallel=1,
    repeat=1,
    output_path=None,
    asset_dir=None,
    keep_assets=False,
):
    # The implementation creates or reuses the asset directory, generates the
    # selected dataset for each repetition, times each extractor phase, validates
    # cold/warm consistency, writes JSON when requested, and returns the report.
    return report
```

The completed implementation must:

- validate `size` against `PROFILES`;
- create a temp directory when `asset_dir` is not provided;
- register a temporary `config.PROJECT_CONFIG["lineage_benchmark"]` with
  `catalog="internal"` and `db="lineage_benchmark_dm"`;
- call `lineage_extractor.configure_project("lineage_benchmark")`;
- build schema with `build_schema_from_texts`;
- run cold extraction with an empty cache path so a task cache is produced;
- write the cold task cache to disk;
- run warm extraction from that cache;
- build cold and warm lineage outputs and compare edge counts;
- require warm cache hits to equal `dataset.task_count`;
- count direct and indirect edges from cold output;
- write the JSON report when `output_path` is set;
- remove temp assets unless `keep_assets=True`;
- restore the original extractor project globals and temporary project config.

- [ ] **Step 4: Run runner test and small CLI**

Run:

```bash
make test PYTEST_ARGS='tests/benchmarks/test_lineage_extractor_benchmark_dataset.py::test_run_benchmark_writes_json_report -q'
PYTHONPATH= conda run -n dw-refactor-py37 python benchmarks/lineage_extractor/run.py --size small --output /tmp/lineage_benchmark_small.json
```

Expected: both commands exit 0, and the CLI prints a compact summary containing `lineage_extractor benchmark`, `size: small`, `cold`, and `warm`.

### Task 3: Makefile and README

**Files:**
- Modify: `Makefile`
- Create: `benchmarks/lineage_extractor/README.md`

- [ ] **Step 1: Add the Makefile target**

Modify `Makefile`:

```make
.PHONY: install-hooks env-create env-update doctor lint test test-cov benchmark-lineage

benchmark-lineage: doctor
	PYTHONPATH= $(PYTHON) benchmarks/lineage_extractor/run.py --size medium
```

- [ ] **Step 2: Add benchmark documentation**

Create `benchmarks/lineage_extractor/README.md` with sections for:

```markdown
# Lineage Extractor Benchmark

## Purpose

## Dataset Sizes

## Running

## Comparing Runs

## Interpreting Results

## Why This Is Outside tests/lineage
```

The README must include these commands:

```bash
make benchmark-lineage
PYTHONPATH= conda run -n dw-refactor-py37 python benchmarks/lineage_extractor/run.py --size small
PYTHONPATH= conda run -n dw-refactor-py37 python benchmarks/lineage_extractor/run.py --size medium --repeat 3 --output benchmark.json
PYTHONPATH= conda run -n dw-refactor-py37 python benchmarks/lineage_extractor/run.py --size large --parallel 4 --keep-assets
```

- [ ] **Step 3: Validate docs and target wiring**

Run:

```bash
make doctor
make test PYTEST_ARGS='tests/benchmarks/test_lineage_extractor_benchmark_dataset.py -q'
```

Expected: both commands exit 0.

### Task 4: Full Verification

**Files:**
- All files touched above.

- [ ] **Step 1: Run focused functional tests**

Run:

```bash
make test PYTEST_ARGS='tests/benchmarks/test_lineage_extractor_benchmark_dataset.py -q'
```

Expected: PASS.

- [ ] **Step 2: Run small benchmark**

Run:

```bash
PYTHONPATH= conda run -n dw-refactor-py37 python benchmarks/lineage_extractor/run.py --size small --output /tmp/lineage_benchmark_small.json
```

Expected: exits 0, writes `/tmp/lineage_benchmark_small.json`, reports 50 tables, 40 tasks, 40 warm cache hits, and zero fatal errors.

- [ ] **Step 3: Run lint and formatting checks**

Run:

```bash
make lint
```

Expected: PASS.

- [ ] **Step 4: Inspect git diff**

Run:

```bash
git status --short --branch
git diff --stat
```

Expected: only benchmark package, benchmark tests, Makefile, README, and this plan are changed.
