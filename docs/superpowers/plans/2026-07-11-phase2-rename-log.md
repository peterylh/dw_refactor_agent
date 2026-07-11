# Phase 2 RENAME Log Fix Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Phase 2 dry-run and execute logs show a Shop table rename as `old_name -> new_name` instead of `[RENAME] ?`.

**Architecture:** Add one pure display helper beside the existing DDL change helpers in `shadow_run.py`. Route both dry-run and successful execute logging through it without changing DDL execution or result JSON.

**Tech Stack:** Python 3.7, pytest 7, existing `dw_refactor_agent.refactor.shadow_run` CLI, Doris/MySQL protocol.

## Global Constraints

- Use the `dw-refactor-py37` conda environment through `make test`; do not run bare `pytest`.
- Preserve plan and result JSON schemas.
- Real validation may rebuild only `shop_dm_qa`; it must not write to `shop_dm`.
- Keep the change limited to Phase 2 DDL display behavior and its tests.

---

### Task 1: Lock the RENAME display contract with failing tests

**Files:**
- Modify: `tests/refact/test_shadow_run.py`
- Test: `tests/refact/test_shadow_run.py`

**Interfaces:**
- Consumes: `execute_shadow_plan(plan: dict) -> dict` and `run_shadow_plan(plan_path, output_path, dry_run=True) -> dict`.
- Produces: Regression assertions for the exact Shop RENAME display string.

- [ ] **Step 1: Add an execute-mode regression test**

Add a test that supplies this DDL change and mocks `run_sql` only at the database boundary:

```python
{
    "change_type": "RENAME",
    "sql": (
        "ALTER TABLE shop_dm.dwd_inventory "
        "RENAME M_SHOP_05_INV_DF;"
    ),
    "old_name": "shop_dm.dwd_inventory",
    "new_name": "shop_dm.M_SHOP_05_INV_DF",
}
```

After `execute_shadow_plan(plan)`, assert:

```python
assert (
    "[RENAME] shop_dm_qa.dwd_inventory -> "
    "shop_dm_qa.M_SHOP_05_INV_DF"
) in output
assert "[RENAME] ?" not in output
```

- [ ] **Step 2: Strengthen the existing dry-run test**

Replace its broad output read with exact assertions for the same rewritten old/new display and absence of `[RENAME] ?`.

- [ ] **Step 3: Run tests to verify RED**

Run:

```bash
make test PYTEST_ARGS='-q tests/refact/test_shadow_run.py -k "rename_display or dry_run_persists_phase_summary"'
```

Expected: the execute regression fails because output contains `[RENAME] ?`; the dry-run assertion fails because it currently shows only the old name.

---

### Task 2: Implement one shared DDL display helper

**Files:**
- Modify: `src/dw_refactor_agent/refactor/shadow_run.py`
- Test: `tests/refact/test_shadow_run.py`

**Interfaces:**
- Produces: `_ddl_change_display_name(change: dict) -> str`.
- Consumes: `change_type`, `table_name`, `old_name`, and `new_name` from a rewritten DDL change.

- [ ] **Step 1: Add the minimal helper**

Place the helper after `_qa_ddl_change`:

```python
def _ddl_change_display_name(change: dict) -> str:
    change_type = str(change.get("change_type") or "").upper()
    table_name = str(change.get("table_name") or "").strip()
    old_name = str(change.get("old_name") or "").strip()
    new_name = str(change.get("new_name") or "").strip()
    if change_type == "RENAME" and old_name and new_name:
        return f"{old_name} -> {new_name}"
    return table_name or old_name or new_name or "?"
```

- [ ] **Step 2: Use it in execute and dry-run logs**

Successful execution becomes:

```python
_log(
    f"  [{qa_change.get('change_type')}] "
    f"{_ddl_change_display_name(qa_change)}"
)
```

Dry-run becomes:

```python
print(
    f"  [{qa_change['change_type']}] "
    f"{_ddl_change_display_name(qa_change)}"
)
```

- [ ] **Step 3: Run focused tests to verify GREEN**

Run:

```bash
make test PYTEST_ARGS='-q tests/refact/test_shadow_run.py -k "rename_display or dry_run_persists_phase_summary"'
```

Expected: all selected tests pass and no `[RENAME] ?` assertion fails.

- [ ] **Step 4: Run the complete refactor shadow-run test file**

Run:

```bash
make test PYTEST_ARGS='-q tests/refact/test_shadow_run.py'
```

Expected: all tests pass.

---

### Task 3: Validate with the real Shop data mart

**Files:**
- Read: `warehouses/shop/mid/ddl/dwd_inventory.sql`
- Create temporarily outside the repository: `/tmp/shop_phase2_rename_log_validation.py`

**Interfaces:**
- Consumes: the real Shop `dwd_inventory` DDL and configured Doris connection.
- Produces: a QA-only shadow-run result and captured Phase 2 log.

- [ ] **Step 1: Build a minimal real Shop plan**

Create a temporary validation script that loads the managed `dwd_inventory` DDL into an in-memory plan. Its single DDL change renames `shop_dm.dwd_inventory` to `shop_dm.verify_phase2_rename_log`, and `jobs_to_run` and checks are empty. The temporary target must start with a letter to satisfy the Doris table-name rule.

- [ ] **Step 2: Execute the real shadow-run against Shop QA**

Run the CLI with `PYTHONPATH=src` and the project conda environment, capturing stdout. This is allowed to drop and recreate `shop_dm_qa`; it must not execute any write against `shop_dm`.

- [ ] **Step 3: Verify the captured evidence**

Assert all of the following:

```text
[RENAME] shop_dm_qa.dwd_inventory -> shop_dm_qa.verify_phase2_rename_log
```

is present, `[RENAME] ?` is absent, the command exits zero, and the result has `status=completed` with `failed_ddl_change_count=0`.

---

### Task 4: Full verification and code review

**Files:**
- Review: `src/dw_refactor_agent/refactor/shadow_run.py`
- Review: `tests/refact/test_shadow_run.py`
- Review: `docs/superpowers/specs/2026-07-11-phase2-rename-log-design.md`
- Review: `docs/superpowers/plans/2026-07-11-phase2-rename-log.md`

**Interfaces:**
- Consumes: the complete branch diff and verification outputs.
- Produces: a reviewed, regression-tested fix with no unresolved Critical or Important findings.

- [ ] **Step 1: Run the complete non-API suite**

Run:

```bash
make test
```

Expected: lint, formatting, and all non-API tests pass.

- [ ] **Step 2: Inspect the complete diff**

Run `git diff --check`, inspect `git diff` from the design commit, and review for behavior drift, Python 3.7 compatibility, schema changes, weak assertions, and accidental production writes.

- [ ] **Step 3: Resolve review findings and rerun affected tests**

Fix every Critical or Important finding. Rerun focused tests after any code change, then rerun `make test` before completion.

- [ ] **Step 4: Commit the implementation**

```bash
git add src/dw_refactor_agent/refactor/shadow_run.py tests/refact/test_shadow_run.py docs/superpowers/plans/2026-07-11-phase2-rename-log.md
git commit -m "fix(refactor): show Phase 2 rename targets"
```
