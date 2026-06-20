# Refact Run Session Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the `refact/run.py` workflow for refactor sessions with baseline/current artifacts, comparable assess issues, scoped change analysis, incremental lineage cache reuse, and shadow-run/compare commands.

**Architecture:** Keep `refact/run.py` as a thin subcommand entrypoint and move behavior into focused modules. Reuse the existing lineage extractor, assess runner, and verify execution/checking logic rather than duplicating SQL parsing or Doris execution code. Make generated files deterministic so tests can assert exact manifests, fingerprints, issue diffs, and cache behavior.

**Tech Stack:** Python 3.7, stdlib `argparse/json/hashlib/datetime/pathlib/subprocess`, existing `lineage.lineage_extractor`, existing `assess.assess_middle_layer`, existing `refact.verify_run` and `refact.verify_check`, `pytest`, `make test`.

---

## File Structure

- Modify `assess/result_model.py`: add stable issue fingerprints to `issues`.
- Modify `assess/assess_middle_layer.py`: allow callers to pass explicit lineage data and output-scoping metadata.
- Create `refact/session.py`: create/load run directories and manifests.
- Create `refact/issue_diff.py`: compare baseline/current `assess_result.json` by issue fingerprint.
- Create `refact/incremental_lineage.py`: build full lineage and task cache artifacts under a run directory.
- Create `refact/change_analysis.py`: compute changed files/assets, affected scope, and lineage edge diff.
- Create `refact/verification_plan.py`: build `verification/plan.json` from change analysis and current project state.
- Create `refact/run.py`: expose `start`, `check`, `shadow-run`, and `compare`.
- Modify `refact/verify_run.py`: expose a function that accepts a metadata dict and writes a result file.
- Modify `refact/verify_check.py`: expose a function that accepts a metadata dict and writes a result file.
- Add tests under `tests/assess/` and `tests/refact/`.

## Task 1: Comparable Assess Issues

**Files:**
- Modify: `assess/result_model.py`
- Test: `tests/assess/test_result_model.py`

- [ ] **Step 1: Write failing tests**

Add `tests/assess/test_result_model.py`:

```python
from assess.result_model import finalize_dimension, make_check


def test_finalize_dimension_adds_stable_issue_fingerprint():
    checks = [
        make_check(
            rule_id="MODEL_DWS_GRAIN_PRESENT",
            target_type="table",
            target="dws_product_sales_daily",
            passed=False,
            expected="grain present",
            actual="missing",
        )
    ]

    result = finalize_dimension(
        dimension="model_design",
        score=0.0,
        checks=checks,
        rules={"MODEL_DWS_GRAIN_PRESENT": {"name": "grain", "severity": "中"}},
    )

    assert result["issues"][0]["fingerprint"] == (
        "model_design|MODEL_DWS_GRAIN_PRESENT|table|dws_product_sales_daily"
    )


def test_make_check_accepts_fingerprint_discriminator():
    checks = [
        make_check(
            rule_id="NAMING_COLUMN_NAME",
            target_type="table",
            target="dwd_order_detail",
            passed=False,
            expected="column naming",
            actual="bad_col",
            fingerprint_discriminator="column:bad_col",
        )
    ]

    result = finalize_dimension(
        dimension="naming",
        score=0.0,
        checks=checks,
        rules={"NAMING_COLUMN_NAME": {"name": "column", "severity": "低"}},
    )

    assert result["issues"][0]["fingerprint"] == (
        "naming|NAMING_COLUMN_NAME|table|dwd_order_detail|column:bad_col"
    )
```

- [ ] **Step 2: Run failing tests**

Run: `make test PYTEST_ARGS="tests/assess/test_result_model.py -q"`

Expected: fail because `fingerprint` and `fingerprint_discriminator` are not implemented.

- [ ] **Step 3: Implement fingerprints**

In `assess/result_model.py`, add `fingerprint_discriminator: str = ""` to
`make_check(...)`. Store it as an internal `_fingerprint_discriminator` key when provided.
Add a helper:

```python
def issue_fingerprint(dimension: str, check: dict[str, Any]) -> str:
    target = check.get("target") or {}
    parts = [
        dimension,
        str(check.get("rule_id") or ""),
        str(target.get("type") or ""),
        str(target.get("name") or ""),
    ]
    discriminator = str(check.get("_fingerprint_discriminator") or "").strip()
    if discriminator:
        parts.append(discriminator)
    return "|".join(parts)
```

In `issues_from_checks(...)`, add `"fingerprint": issue_fingerprint(dimension, check)`.

- [ ] **Step 4: Run tests**

Run: `make test PYTEST_ARGS="tests/assess/test_result_model.py -q"`

Expected: pass.

## Task 2: Issue Diff

**Files:**
- Create: `refact/issue_diff.py`
- Test: `tests/refact/test_issue_diff.py`

- [ ] **Step 1: Write failing tests**

Create `tests/refact/test_issue_diff.py`:

```python
from refact.issue_diff import diff_assess_results


def _issue(fp, title):
    return {"fingerprint": fp, "title": title, "target": {"type": "table", "name": title}}


def test_diff_assess_results_classifies_fixed_remaining_and_new():
    baseline = {
        "overall_score": 50.0,
        "dimensions": {
            "naming": {"score": 50.0, "issues": [_issue("a", "old-a"), _issue("b", "old-b")]}
        },
    }
    current = {
        "overall_score": 90.0,
        "dimensions": {
            "naming": {"score": 90.0, "issues": [_issue("b", "new-b"), _issue("c", "new-c")]}
        },
    }

    result = diff_assess_results(baseline, current)

    assert result["summary"] == {
        "baseline_issue_count": 2,
        "current_issue_count": 2,
        "fixed_count": 1,
        "remaining_count": 1,
        "new_count": 1,
    }
    assert [issue["fingerprint"] for issue in result["fixed_issues"]] == ["a"]
    assert [issue["fingerprint"] for issue in result["remaining_issues"]] == ["b"]
    assert [issue["fingerprint"] for issue in result["new_issues"]] == ["c"]
    assert result["scope_score"]["overall_score"] == 90.0
```

- [ ] **Step 2: Run failing test**

Run: `make test PYTEST_ARGS="tests/refact/test_issue_diff.py -q"`

Expected: fail because `refact.issue_diff` does not exist.

- [ ] **Step 3: Implement diff**

Create `refact/issue_diff.py` with:

```python
from __future__ import annotations


def _issues_by_fingerprint(assess_result: dict) -> dict:
    issues = {}
    for dimension in (assess_result.get("dimensions") or {}).values():
        for issue in dimension.get("issues") or []:
            fingerprint = str(issue.get("fingerprint") or "").strip()
            if fingerprint:
                issues[fingerprint] = issue
    return issues


def _score_summary(assess_result: dict) -> dict:
    return {
        "overall_score": assess_result.get("overall_score"),
        "dimensions": {
            name: {"score": value.get("score")}
            for name, value in (assess_result.get("dimensions") or {}).items()
        },
    }


def diff_assess_results(baseline: dict, current: dict) -> dict:
    baseline_issues = _issues_by_fingerprint(baseline)
    current_issues = _issues_by_fingerprint(current)
    baseline_keys = set(baseline_issues)
    current_keys = set(current_issues)

    fixed = sorted(baseline_keys - current_keys)
    remaining = sorted(baseline_keys & current_keys)
    new = sorted(current_keys - baseline_keys)

    return {
        "summary": {
            "baseline_issue_count": len(baseline_issues),
            "current_issue_count": len(current_issues),
            "fixed_count": len(fixed),
            "remaining_count": len(remaining),
            "new_count": len(new),
        },
        "fixed_issues": [baseline_issues[key] for key in fixed],
        "remaining_issues": [current_issues[key] for key in remaining],
        "new_issues": [current_issues[key] for key in new],
        "scope_score": _score_summary(current),
    }
```

- [ ] **Step 4: Run tests**

Run: `make test PYTEST_ARGS="tests/refact/test_issue_diff.py -q"`

Expected: pass.

## Task 3: Session Manifest

**Files:**
- Create: `refact/session.py`
- Test: `tests/refact/test_session.py`

- [ ] **Step 1: Write failing tests**

Create tests that call `create_run_manifest(root, project, now=...)`, assert the
directory layout and manifest artifact paths, and call `load_manifest(path)`.

- [ ] **Step 2: Implement session helpers**

Implement:

```python
def create_run_manifest(root: Path, project: str, now=None) -> dict
def write_manifest(manifest: dict, path: Path) -> None
def load_manifest(path: Path) -> dict
def run_root_from_manifest_path(path: Path) -> Path
def artifact_path(manifest_path: Path, artifact_key: str) -> Path
```

`create_run_manifest` must create `baseline`, `current`, `analysis`, and
`verification` directories under `refact/runs/<run_id>`.

- [ ] **Step 3: Run tests**

Run: `make test PYTEST_ARGS="tests/refact/test_session.py -q"`

Expected: pass.

## Task 4: Incremental Lineage Cache

**Files:**
- Create: `refact/incremental_lineage.py`
- Test: `tests/refact/test_incremental_lineage.py`

- [ ] **Step 1: Write failing tests**

Use a temp project with one DDL and one task. Assert that the first build writes
a cache entry, the second build reuses it, and changing DDL invalidates the task
by changing the schema slice hash.

- [ ] **Step 2: Implement lineage builder**

Implement:

```python
def build_lineage_artifacts(project: str, output_path: Path, cache_path: Path, previous_cache_path: Path | None = None) -> dict
```

Internally reuse:

- `lineage.lineage_extractor.configure_project`
- `project_asset_dirs`
- `build_schema_from_ddl`
- `extract_lineage_from_task_files`
- `build_lineage_output`

Cache entries store `cache_key`, `source_file`, `entries`, `transient_tables`,
`missing_ddl_tables`, `errors`, and `stats`.

- [ ] **Step 3: Run tests**

Run: `make test PYTEST_ARGS="tests/refact/test_incremental_lineage.py -q"`

Expected: pass.

## Task 5: Change Analysis and Verification Plan

**Files:**
- Create: `refact/change_analysis.py`
- Create: `refact/verification_plan.py`
- Test: `tests/refact/test_change_analysis.py`
- Test: `tests/refact/test_verification_plan.py`

- [ ] **Step 1: Write failing tests**

Test file classification for `ddl`, `tasks`, `models`, and config files.
Test affected downstream scope using small baseline/current lineage dicts.
Test `build_verification_plan` returns project DB names, jobs to run, and checks
from anchors.

- [ ] **Step 2: Implement analysis helpers**

Implement:

```python
def changed_files_since_head(repo: Path, head: str, project_dir: str) -> list[str]
def classify_changed_assets(files: list[str], project_dir: str) -> dict
def build_change_analysis(project: str, baseline_lineage: dict, current_lineage: dict, changed_files: list[str]) -> dict
```

Use `asset_job_dag_from_lineage` for downstream traversal.

- [ ] **Step 3: Implement plan builder**

Implement:

```python
def build_verification_plan(project: str, change_analysis: dict) -> dict
```

Use `PROJECT_CONFIG` for `project_db` and `qa_db`. Use changed task jobs and
anchor/downstream tables for `jobs_to_run` and simple count/row_compare checks.

- [ ] **Step 4: Run tests**

Run: `make test PYTEST_ARGS="tests/refact/test_change_analysis.py tests/refact/test_verification_plan.py -q"`

Expected: pass.

## Task 6: Run CLI

**Files:**
- Create: `refact/run.py`
- Test: `tests/refact/test_run_cli.py`

- [ ] **Step 1: Write failing tests**

Use monkeypatches for lineage/assess builders. Assert:

- `start --project demo --root <tmp>` writes manifest and baseline artifacts.
- `check --manifest <path>` writes current artifacts, change analysis, issue diff, and verification plan.
- `shadow-run --manifest <path>` delegates to shadow execution with `verification/plan.json`.
- `compare --manifest <path>` delegates to comparison with `verification/plan.json`.

- [ ] **Step 2: Implement CLI**

Add subcommands:

```python
start
check
shadow-run
compare
```

`start` calls session creation, baseline lineage build, and baseline assess.
`check` loads the manifest, builds current lineage, runs current assess, writes
issue diff, writes change analysis, and writes verification plan.

- [ ] **Step 3: Run tests**

Run: `make test PYTEST_ARGS="tests/refact/test_run_cli.py -q"`

Expected: pass.

## Task 7: Shadow Run and Compare Wrappers

**Files:**
- Modify: `refact/verify_run.py`
- Modify: `refact/verify_check.py`
- Create: `refact/shadow_run.py`
- Create: `refact/compare.py`
- Test: `tests/refact/test_shadow_compare_wrappers.py`

- [ ] **Step 1: Write failing tests**

Monkeypatch the existing `verify_run` and `verify_check` internals so wrappers
can be tested without Doris. Assert result files are written under
`verification/shadow_run_result.json` and `verification/compare_result.json`.

- [ ] **Step 2: Implement wrappers**

Create:

```python
def run_shadow_plan(plan_path: Path, output_path: Path, dry_run: bool = False) -> dict
def compare_shadow_results(plan_path: Path, output_path: Path, method: str = "all") -> dict
```

Wrappers load `verification/plan.json`, call reusable functions exposed from the
old scripts, and write compact result metadata.

- [ ] **Step 3: Run tests**

Run: `make test PYTEST_ARGS="tests/refact/test_shadow_compare_wrappers.py -q"`

Expected: pass.

## Task 8: Full Verification

**Files:**
- All changed files

- [ ] **Step 1: Run targeted tests**

Run:

```bash
make test PYTEST_ARGS="tests/assess/test_result_model.py tests/refact/test_issue_diff.py tests/refact/test_session.py tests/refact/test_incremental_lineage.py tests/refact/test_change_analysis.py tests/refact/test_verification_plan.py tests/refact/test_run_cli.py tests/refact/test_shadow_compare_wrappers.py -q"
```

Expected: pass.

- [ ] **Step 2: Run non-API suite**

Run: `make test`

Expected: `539+` tests pass and API tests remain deselected.

- [ ] **Step 3: Inspect git diff**

Run: `git status --short --branch`

Expected: only the new refact run workflow, assess fingerprint support, tests,
and plan/design docs are changed.
