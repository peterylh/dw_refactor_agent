# Lineage CLI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a command-line lineage viewer that can show local table-level lineage, required-column column lineage, project statistics, and local HTML exports from existing lineage snapshots.

**Architecture:** Add a query layer that turns `LineageView` snapshots into bounded subgraphs and column paths, then add formatters for human text, JSON, DOT, and standalone HTML. The CLI remains thin: parse arguments, open a snapshot, call query/format functions, write output, and return clear exit codes.

**Tech Stack:** Python standard library, existing `lineage.model`, `lineage.view`, `lineage.store`, and pytest.

---

### Task 1: Table Subgraph Query

**Files:**
- Create: `lineage/query.py`
- Test: `tests/lineage/test_lineage_query.py`

- [ ] **Step 1: Write failing tests**

Add tests that build a small `LineageView` with `ods_order -> dwd_order_detail -> dws_product_sales_daily -> ads_sales_dashboard`, then assert:
- upstream depth 2 from `ads_sales_dashboard` includes the ADS, DWS, and DWD tables, but hides the ODS boundary;
- edge records include `source`, `target`, `hops`, and `source_files`;
- layer counts are stable.

- [ ] **Step 2: Run the focused test**

Run: `pytest tests/lineage/test_lineage_query.py -q`
Expected: FAIL because `lineage.query` does not exist.

- [ ] **Step 3: Implement minimal query model**

Create dataclasses for table edges, table subgraphs, and summary stats. Implement `build_table_subgraph(view, table_name, direction, depth)` using `view.asset_table_graph()` and `view.table_edge_source_files()`.

- [ ] **Step 4: Verify focused test passes**

Run: `pytest tests/lineage/test_lineage_query.py -q`
Expected: PASS.

### Task 2: Text/JSON/DOT Formatters

**Files:**
- Create: `lineage/formatters.py`
- Test: `tests/lineage/test_lineage_formatters.py`

- [ ] **Step 1: Write failing formatter tests**

Assert table text includes `Summary`, `Graph`, `Edges`, layer counts, hidden boundary text, and source file names. Assert JSON and DOT outputs contain only the selected local subgraph.

- [ ] **Step 2: Run focused formatter tests**

Run: `pytest tests/lineage/test_lineage_formatters.py -q`
Expected: FAIL because `lineage.formatters` does not exist.

- [ ] **Step 3: Implement minimal formatters**

Add `format_table_text`, `format_table_json`, and `format_table_dot`. Keep terminal output plain ASCII and deterministic.

- [ ] **Step 4: Verify formatter tests pass**

Run: `pytest tests/lineage/test_lineage_formatters.py -q`
Expected: PASS.

### Task 3: Column Lineage Query

**Files:**
- Modify: `lineage/query.py`
- Modify: `lineage/formatters.py`
- Test: `tests/lineage/test_lineage_query.py`
- Test: `tests/lineage/test_lineage_formatters.py`

- [ ] **Step 1: Write failing column tests**

Add tests for `build_column_lineage(view, table_name, column_name, direction, depth)`:
- upstream paths require a specific table and column;
- one-hop expressions and source files are preserved;
- recursive upstream paths can cross two tables when depth is 2.

- [ ] **Step 2: Run focused tests**

Run: `pytest tests/lineage/test_lineage_query.py tests/lineage/test_lineage_formatters.py -q`
Expected: FAIL because column query and formatting are missing.

- [ ] **Step 3: Implement column paths and text formatter**

Use `view.column_lineage_for_table(table)` for upstream records, recurse from each source column until depth is reached, and add a text output headed by `Column Lineage`.

- [ ] **Step 4: Verify focused tests pass**

Run: `pytest tests/lineage/test_lineage_query.py tests/lineage/test_lineage_formatters.py -q`
Expected: PASS.

### Task 4: CLI and HTML Export

**Files:**
- Create: `lineage/lineage_cli.py`
- Modify: `lineage/formatters.py`
- Test: `tests/lineage/test_lineage_cli.py`

- [ ] **Step 1: Write failing CLI tests**

Use a temp `lineage_data_demo.json` and invoke `main(argv)`. Assert:
- `show` prints table lineage;
- `column` requires `--column` and prints column lineage;
- `stats` prints project counts;
- `export-html` writes a standalone HTML file containing only the selected local subgraph.

- [ ] **Step 2: Run CLI tests**

Run: `pytest tests/lineage/test_lineage_cli.py -q`
Expected: FAIL because `lineage.lineage_cli` does not exist.

- [ ] **Step 3: Implement CLI**

Add subcommands:
- `stats --project PROJECT [--lineage-dir DIR] [--format text|json]`
- `show --project PROJECT --table TABLE [--direction upstream|downstream|both] [--depth N] [--format text|json|dot] [--lineage-dir DIR]`
- `column --project PROJECT --table TABLE --column COLUMN [--direction upstream|downstream|both] [--depth N] [--format text|json] [--lineage-dir DIR]`
- `export-html --project PROJECT --table TABLE [--direction upstream|downstream|both] [--depth N] --output PATH [--lineage-dir DIR]`

- [ ] **Step 4: Verify CLI tests pass**

Run: `pytest tests/lineage/test_lineage_cli.py -q`
Expected: PASS.

### Task 5: Final Verification

**Files:**
- All files touched above.

- [ ] **Step 1: Run lineage tests**

Run: `pytest tests/lineage/test_lineage_query.py tests/lineage/test_lineage_formatters.py tests/lineage/test_lineage_cli.py -q`
Expected: PASS.

- [ ] **Step 2: Run non-API suite**

Run: `pytest -q -m "not api"`
Expected: PASS.

- [ ] **Step 3: Inspect git diff**

Run: `git diff --stat`
Expected: only lineage CLI/query/formatter tests, new implementation files, and this plan are changed.
