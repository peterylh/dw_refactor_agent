# Shadow Run Minimal Recompute Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prevent unchanged upstream jobs from entering shadow-run while preserving broad assessment scope, downstream recomputation, anchor-aligned execution values, and manifest production read-through.

**Architecture:** Keep `change_analysis.affected_scope` broad and unchanged. Build `jobs_to_run` only from direct and downstream executable tables, move final anchors from plan `scope` to `verification.anchor_tables`, and derive baseline DDL from actual QA materialization needs. Existing shadow manifest routes remain authoritative.

**Tech Stack:** Python 3.7-compatible code, pytest through `make test`, sqlglot-based shadow routing, Doris-backed shop validation.

## Global Constraints

- Do not retain fallback support for old verification plans.
- Do not add `execution_scope`, candidate routing fields, or aggregate manifest-summary classifications.
- Run tests through `make test`; do not run bare `pytest`.
- Preserve the existing broad `affected_scope` structure.

---

### Task 1: Select Only Direct And Downstream Jobs

**Files:**
- Modify: `tests/refact/test_verification_plan.py`
- Modify: `src/dw_refactor_agent/refactor/verification_plan.py`

**Interfaces:**
- Consumes: `change_analysis.changed_assets`, `change_analysis.affected_scope`
- Produces: `build_verification_plan(...)["jobs_to_run"]`

- [ ] Add a regression test where unchanged `dwd_order_detail` appears only in
  `assessment_tables`/`assessment_tasks` due to a changed edge, while changed
  DWS and downstream ADS tables are direct/downstream.
- [ ] Run the focused test with
  `make test PYTEST_ARGS="tests/refact/test_verification_plan.py -k unchanged_upstream"`
  and confirm it fails because DWD is selected.
- [ ] Add a strict helper that forms job candidates from
  `direct_tables | downstream_tables`; remove the assessment-task fallback.
- [ ] Re-run the focused test and the existing lineage-window tests and confirm
  changed daily jobs still receive monthly daily values.

### Task 2: Remove Plan Scope And Move Final Anchors

**Files:**
- Modify: `tests/refact/test_verification_plan.py`
- Modify: `tests/refact/test_shadow_run.py`
- Modify: `tests/refact/test_run_cli.py`
- Modify: `src/dw_refactor_agent/refactor/verification_plan.py`
- Modify: `src/dw_refactor_agent/refactor/shadow_run.py`
- Modify: `src/dw_refactor_agent/refactor/run.py`

**Interfaces:**
- Produces: `plan["verification"]["anchor_tables"]`
- Removes: `plan["scope"]` and all plan-scope compatibility readers

- [ ] Add failing tests that require final anchors under `verification` and
  reject/use no top-level plan scope.
- [ ] Move final anchor serialization into `_verification_metadata` and update
  shadow-run anchor readers to require `verification.anchor_tables`.
- [ ] Make assessment result marking read `change_analysis.affected_scope`
  directly; remove plan scope fallbacks and scope-based no-work detection.
- [ ] Run focused verification-plan, shadow-run, and run-CLI tests.

### Task 3: Restrict Baseline DDL To QA Needs

**Files:**
- Modify: `tests/refact/test_verification_plan.py`
- Modify: `src/dw_refactor_agent/refactor/verification_plan.py`

**Interfaces:**
- Consumes: final anchors, DDL changes, `jobs_to_run`
- Produces: `plan["baseline_ddl"]`

- [ ] Add failing tests for both baseline-ref and current-DDL paths proving an
  unchanged production-read upstream is excluded from `baseline_ddl`.
- [ ] Reuse one needed-table computation for both paths; current-DDL loading
  must filter by that exact set rather than assessment tables.
- [ ] Run focused baseline-DDL and manifest route tests.

### Task 4: Update Documentation And Full Automated Verification

**Files:**
- Modify: `AGENTS.md`
- Modify: `docs/refactor_guides/common.md`
- Modify: affected refactor tests and fixtures that still emit plan `scope`

**Interfaces:**
- Documents: new verification plan schema and required rerun of `analyze`

- [ ] Update plan schema documentation and examples.
- [ ] Remove old-plan compatibility assertions and update all fixtures.
- [ ] Run `make test PYTEST_ARGS="tests/refact"`.
- [ ] Run `make test`.

### Task 5: Code Review And Real Shop Validation

**Files:**
- Review: all changed source, tests, and docs
- Runtime artifact: `/tmp/shop_shadow_minimal_recompute_validation/`

**Interfaces:**
- Validates: actual shop lineage, task SQL, Doris production reads, QA writes,
  invocation count, and production-vs-QA results

- [ ] Review the final diff for correctness, regressions, schema consistency,
  and missing tests; fix findings with failing tests first.
- [ ] Build a shop-derived validation plan representing changed DWS plus
  downstream monthly ADS while leaving `dwd_order_detail` unchanged.
- [ ] Assert generated `jobs_to_run` and `baseline_ddl` exclude
  `dwd_order_detail`, and manifest routes its read to `shop_dm`.
- [ ] Execute real shadow-run against `shop_dm_qa`, record per-invocation timing,
  and confirm there are no DWD job invocations.
- [ ] Run count and row comparison for final anchors and require matching
  results.
