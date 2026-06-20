# Project Artifact Paths Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move default project-specific generated lineage and assessment artifacts under each data mart project directory.

**Architecture:** Add central artifact path helpers in `config.py`, then update tools to use those helpers for default reads and writes. Explicit override options keep their documented behavior, but default code paths do not read or write historical tool-directory artifacts.

**Tech Stack:** Python 3.7, pathlib, pytest, existing `make test` workflow.

---

### Task 1: Centralize Project Artifact Paths

**Files:**
- Modify: `config.py`
- Test: `tests/test_project_artifact_paths.py`

- [ ] Write tests for `{project}/lineage/lineage_data.json`, `{project}/lineage/job_dag.json`, and `{project}/assess/cache/inspect.json` path helpers.
- [ ] Run `make test PYTEST_ARGS='tests/test_project_artifact_paths.py -q -m "not api"'` and confirm the new tests fail before implementation.
- [ ] Add `project_artifact_dir(project, *parts)` and specific helpers for lineage data, job DAG, lineage HTML, assessment output, metadata output, and assessment cache files.
- [ ] Run the focused test and confirm it passes.

### Task 2: Move Lineage Defaults

**Files:**
- Modify: `lineage/table_graph.py`
- Modify: `lineage/store.py`
- Modify: `lineage/lineage_extractor.py`
- Modify: `lineage/import_lineage.py`
- Modify: `lineage/refresh_lineage_html.py`
- Modify: `lineage/lineage_cli.py`
- Test: `tests/lineage/test_refresh_lineage_html.py`
- Test: `tests/lineage/test_lineage_cli.py`

- [ ] Write failing tests showing default lineage data and HTML paths resolve under `{project}/lineage/`.
- [ ] Run focused lineage tests and confirm they fail for old tool-directory defaults.
- [ ] Update default lineage reads and writes to use project artifact helpers.
- [ ] Preserve explicit `--lineage-dir` behavior for `lineage_cli.py`.
- [ ] Run focused lineage tests and confirm they pass.

### Task 3: Move DAG And Assessment Defaults

**Files:**
- Modify: `exec/task_run.py`
- Modify: `assess/assess_middle_layer.py`
- Modify: `assess/llm/model_metadata_writer.py`
- Test: `tests/test_task_run.py`
- Test: `tests/assess/test_assess_middle_layer.py`
- Test: `tests/assess/test_model_metadata_writer.py`

- [ ] Write failing tests showing DAG and assessment output defaults under `{project}/lineage/` and `{project}/assess/`.
- [ ] Run focused tests and confirm they fail for old defaults.
- [ ] Update DAG generation/loading, assessment report output, metadata report output, and LLM inspection cache paths.
- [ ] Ensure new parent directories are created before writing.
- [ ] Run focused tests and confirm they pass.

### Task 4: Documentation And Ignore Rules

**Files:**
- Modify: `.gitignore`
- Modify: `AGENTS.md`
- Modify: `docs/assess_metadata_initialization.md`
- Modify: `docs/refactor_guides/common.md`

- [ ] Update docs to describe `{project}/lineage/` and `{project}/assess/` generated artifacts.
- [ ] Update `.gitignore` to ignore generated artifacts under project directories.
- [ ] Run `make test`.
