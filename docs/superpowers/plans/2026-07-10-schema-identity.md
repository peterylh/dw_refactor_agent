# Managed DDL Schema Identity Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make persistent table and column UUIDs authoritative for managed DDL changes, provide safe authoring/validation commands, and migrate `shop` and `finance_analytics`.

**Architecture:** Keep schema identity authoring and validation in a focused `schema_ids.py` module. Extend the existing DDL parser and deriver to consume exact IDs while preserving an explicit legacy mode, then make project verification strict and migrate assets with the new command.

**Tech Stack:** Python 3.7, `sqlglot==26.9.0`, standard-library `uuid`/`argparse`/`pathlib`, pytest through the project Makefile.

## Global Constraints

- Use UUID4 values stored in `-- table_id:` and `-- column_id:` comments.
- Identity generation occurs only in authoring commands; derivation and analysis are read-only.
- Managed project workflows fail closed on missing, malformed, orphan, or duplicate IDs.
- Existing IDs are immutable and never overwritten by generation commands.
- Preserve DDL text except for inserted identity comment lines.
- Keep Python 3.7 compatibility and add no dependency.
- Use `make test` or targeted Make-compatible commands; do not run bare `pytest`.

---

### Task 1: Parse Stable Column IDs

**Files:**
- Modify: `src/dw_refactor_agent/ddl_deriver/ddl_deriver.py`
- Modify: `tests/ddl_deriver/test_ddl_deriver.py`

**Interfaces:**
- Produces: `ColumnDef.column_id: str`
- Produces: `extract_column_id(col_node: exp.ColumnDef) -> str`
- Consumes: sqlglot identifier comments attached to `col_node.this.comments`

- [ ] **Step 1: Add a failing parser test**

Add a DDL fixture with two preceding `column_id` comments and assert:

```python
table = parse_create_table(ddl)
assert table is not None
assert [column.column_id for column in table.columns] == [first_id, second_id]
```

- [ ] **Step 2: Verify RED**

Run: `make test PYTEST_ARGS='tests/ddl_deriver/test_ddl_deriver.py -k column_id -q'`

Expected: FAIL because `ColumnDef` has no `column_id` attribute.

- [ ] **Step 3: Implement minimal parsing**

Add `column_id: str = ""` after existing optional fields so positional callers remain compatible. Extract exactly one matching UUID marker from identifier comments; return an empty string when absent so validation owns malformed/multiple-marker errors.

- [ ] **Step 4: Verify GREEN**

Run the same focused command and expect PASS.

### Task 2: Add Schema Identity Authoring and Validation

**Files:**
- Create: `src/dw_refactor_agent/ddl_deriver/schema_ids.py`
- Create: `tests/ddl_deriver/test_schema_ids.py`

**Interfaces:**
- Produces: `managed_ddl_files(project: str) -> list[Path]`
- Produces: `init_file(path: Path) -> list[IdentityAssignment]`
- Produces: `assign_column(path: Path, column_name: str) -> IdentityAssignment`
- Produces: `init_project(project: str) -> list[IdentityAssignment]`
- Produces: `validate_project(project: str) -> list[IdentityIssue]`
- Produces CLI subcommands: `init-project`, `init-file`, `assign-column`, `validate`

- [ ] **Step 1: Add failing generation tests**

Cover one multiline DDL file and assert that `init_file` inserts one table ID,
one ID per parsed column, preserves SQL tokens/comments, and makes a second run
return no assignments. Add a focused `assign_column` test that inserts only the
named missing ID and refuses an already identified column.

- [ ] **Step 2: Verify generation tests are RED**

Run: `make test PYTEST_ARGS='tests/ddl_deriver/test_schema_ids.py -k "init_file or assign_column" -q'`

Expected: collection/import failure because `schema_ids` does not exist.

- [ ] **Step 3: Implement authoring primitives**

Use `uuid.uuid4()` and reverse-order source insertions. Locate the CREATE body,
map parsed columns to their source definition lines, insert a comment with the
column line's indentation, and write only after every requested insertion has
been validated. Reuse the existing table ID header insertion convention.

- [ ] **Step 4: Verify authoring tests are GREEN**

Run the focused generation test command and expect PASS.

- [ ] **Step 5: Add failing validation tests**

Create temporary configured projects covering missing table ID, missing column
ID, malformed UUID4, duplicate table ID, duplicate column ID across files,
orphan marker, and unparseable DDL. Assert issue codes and paths rather than
full prose messages.

- [ ] **Step 6: Verify validation tests are RED**

Run: `make test PYTEST_ARGS='tests/ddl_deriver/test_schema_ids.py -k validate -q'`

Expected: FAIL because validation is not implemented.

- [ ] **Step 7: Implement validation and CLI**

Represent issues and assignments as dataclasses. Validate requested-project
completeness and scan IDs already present in every configured project for
global duplicates. Return exit code 1 with all issues for `validate`; return 0
and stable assignment summaries for successful authoring commands.

- [ ] **Step 8: Verify the schema identity test module**

Run: `make test PYTEST_ARGS='tests/ddl_deriver/test_schema_ids.py -q'`

Expected: PASS.

### Task 3: Make IDs Authoritative in DDL Derivation

**Files:**
- Modify: `src/dw_refactor_agent/ddl_deriver/ddl_deriver.py`
- Modify: `tests/ddl_deriver/test_ddl_deriver.py`
- Modify: `tests/ddl_deriver/test_git_mode.py`

**Interfaces:**
- Changes: `derive_ddl_changes(old_tables: dict, new_tables: dict, *, legacy_identity: bool = True)`
- Changes: `derive_from_git(ddl_dir_rel=None, repo=None, base_branch="main", project="shop", *, legacy_identity=True)`
- Produces: exact table/column ID matches before legacy heuristics

- [ ] **Step 1: Add failing exact-identity tests**

Cover:

```python
# Same ID, renamed and modified.
assert change.renames == [("unit_price", "price_unit")]
assert [(old.name, new.name) for old, new in change.modifies] == [
    ("unit_price", "price_unit")
]

# Different IDs with identical structure.
assert change.renames == []
assert [column.name for column in change.drops] == ["old_name"]
assert [column.name for column in change.adds] == ["new_name"]
```

Also assert generated SQL orders rename before modify and uses the final name.

- [ ] **Step 2: Verify RED**

Run: `make test PYTEST_ARGS='tests/ddl_deriver/test_ddl_deriver.py -k "column_id or rename_and_modify" -q'`

Expected: FAIL because matching ignores column IDs and rename attribute deltas.

- [ ] **Step 3: Implement exact table and column matching**

Build ID maps, reject duplicate in-memory IDs, match same IDs regardless of
mutable attributes, remove matched items from add/drop, and compare every
matched pair for type/nullability/default/comment changes. Run legacy table
and column heuristics only when `legacy_identity=True` and neither side has an
ID for the candidate.

- [ ] **Step 4: Remove derivation-time table ID generation**

Delete the `generate_table_id()`/`inject_table_id()` mutation from the CREATE
path. Replace the old auto-UUID test with an assertion that derivation leaves
an unidentified `TableDef` unchanged in legacy mode.

- [ ] **Step 5: Verify deriver tests**

Run: `make test PYTEST_ARGS='tests/ddl_deriver/test_ddl_deriver.py tests/ddl_deriver/test_git_mode.py -q -m "not api"'`

Expected: PASS.

### Task 4: Enforce Strict Identity in Project Refactor Workflows

**Files:**
- Modify: `src/dw_refactor_agent/refactor/verification_plan.py`
- Modify: `tests/refact/test_verification_plan.py`

**Interfaces:**
- Consumes: `validate_project(project)` and `derive_ddl_changes(old_tables, new_tables, legacy_identity=False)`
- Produces: `SchemaIdentityError` with actionable issue summaries

- [ ] **Step 1: Add a failing strict-project test**

Construct a configured temporary project whose DDL lacks IDs and assert
`derive_project_ddl_changes()` raises `SchemaIdentityError`. Add a passing
fixture with stable IDs and a column rename.

- [ ] **Step 2: Verify RED**

Run: `make test PYTEST_ARGS='tests/refact/test_verification_plan.py -k identity -q'`

Expected: FAIL because project derivation does not validate identities.

- [ ] **Step 3: Implement strict integration**

Validate the working tree before loading changes, validate parsed baseline
tables for required IDs/duplicates, then call the deriver with
`legacy_identity=False`. Keep direct library/git-directory APIs legacy-compatible
unless callers explicitly disable legacy identity.

- [ ] **Step 4: Verify refactor tests**

Run: `make test PYTEST_ARGS='tests/refact/test_verification_plan.py tests/refact/test_run_cli.py -q -m "not api"'`

Expected: PASS.

### Task 5: Document Authoring Rules and Migrate Both Projects

**Files:**
- Modify: `docs/development/sql_dev_standards.md`
- Modify: `docs/refactor_guides/common.md`
- Modify: `docs/refactor_guides/field_rename.md`
- Modify: `AGENTS.md`
- Modify: all managed DDL under `warehouses/shop/{ods,mid,ads}/ddl/`
- Modify: all managed DDL under `warehouses/finance_analytics/{ods,mid,ads}/ddl/`

**Interfaces:**
- Consumes: `schema_ids init-project` and `schema_ids validate`
- Produces: complete, globally unique identity metadata for both projects

- [ ] **Step 1: Update authoring documentation**

Document `init-file`, `assign-column`, and `validate`; state that rename keeps
IDs, copied/replacement fields receive new IDs, and refactor baselines must be
restarted after the migration.

- [ ] **Step 2: Run project migration**

Run:

```bash
PYTHONPATH=src conda run -n dw-refactor-py37 python -m dw_refactor_agent.ddl_deriver.schema_ids init-project --project shop --replace-invalid-table-ids
PYTHONPATH=src conda run -n dw-refactor-py37 python -m dw_refactor_agent.ddl_deriver.schema_ids init-project --project finance_analytics
```

Expected: every missing table/column identity receives one UUID4; existing
valid table IDs are preserved.

- [ ] **Step 3: Validate migrated projects**

Run both `validate --project` commands and expect exit code 0 with zero issues.

- [ ] **Step 4: Audit migration-only changes**

Inspect `git diff -- warehouses/shop warehouses/finance_analytics` and confirm
all added lines match identity comments and no SQL definition text changed.

### Task 6: Verification and Code Review

**Files:**
- Review all modified source, tests, docs, and migrated DDL.

**Interfaces:**
- Consumes: all previous tasks
- Produces: passing checks and severity-ordered review findings

- [ ] **Step 1: Run focused tests**

Run:

```bash
make test PYTEST_ARGS='tests/ddl_deriver tests/refact/test_verification_plan.py tests/refact/test_run_cli.py -q -m "not api"'
```

- [ ] **Step 2: Run the full non-API suite**

Run: `make test`

- [ ] **Step 3: Run static migration checks**

Validate both projects, scan UUID4 uniqueness, run `git diff --check`, and
confirm the number of parsed columns equals the number of column ID markers.

- [ ] **Step 4: Perform Code Review**

Review for parser/comment association, accidental ID regeneration, global
uniqueness, strict/legacy boundaries, rename-plus-modify SQL ordering,
backward-compatible JSON, project-scope coverage, and migration-only diffs.
Report findings by severity with file/line references; if there are no
findings, state that explicitly and list residual risks.
