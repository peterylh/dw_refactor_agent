# Model Design Assessment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the first implementation slice for model design assessment: dimension selection, `architecture` to `model_design` compatibility, layer boundary checks, and fact grain clarity checks.

**Architecture:** Add a new focused `assess.scoring.model_design` module that preserves existing architecture dependency behavior and extends it with SQL/model metadata checks. Keep `assess.scoring.architecture` as a compatibility wrapper. Update `assess_middle_layer` to run selected dimensions and expose `--model-design` while keeping `--architecture` as an alias.

**Tech Stack:** Python, pytest, sqlglot, existing `assess.result_model` check/issue helpers, existing asset catalog and model metadata loaders.

---

## File Structure

- Create `assess/scoring/model_design.py`: owns model design scoring, architecture dependency checks, layer boundary checks, and grain clarity checks.
- Modify `assess/scoring/architecture.py`: compatibility wrapper exporting `score_architecture_health` from the new module.
- Modify `assess/scoring/config.py`: add model design rule metadata and keep architecture rule aliases.
- Modify `assess/assess_middle_layer.py`: add dimension selection, `--model-design`, `--architecture` alias, and output key `model_design`.
- Modify `tests/assess/test_assess_middle_layer.py`: update architecture assertions, add dimension selection tests.
- Create `tests/assess/test_model_design.py`: focused tests for layer boundary and grain rules.

## Task 1: Add Model Design Module With Existing Architecture Behavior

**Files:**
- Create: `assess/scoring/model_design.py`
- Modify: `assess/scoring/architecture.py`
- Modify: `assess/scoring/config.py`
- Test: `tests/assess/test_model_design.py`

- [x] **Step 1: Write failing compatibility test**

Add this test to `tests/assess/test_model_design.py`:

```python
from assess.scoring.architecture import score_architecture_health
from assess.scoring.model_design import score_model_design_health


def _rule_ids(result):
    return {issue["rule_id"] for issue in result["issues"]}


def test_architecture_wrapper_uses_model_design_dimension():
    tables = [
        {"name": "ods_order", "layer": "ODS", "columns": []},
        {"name": "ads_sales", "layer": "ADS", "columns": []},
    ]
    edges = [{
        "source": "ods_order.order_id",
        "target": "ads_sales.order_id",
        "source_file": "ads_sales.sql",
    }]

    wrapped = score_architecture_health(tables, edges, [])
    direct = score_model_design_health(tables, edges, [])

    assert wrapped["score"] == direct["score"]
    assert _rule_ids(wrapped) == {"ARCH_SKIP_LAYER_DEPENDENCY"}
    assert _rule_ids(direct) == {"ARCH_SKIP_LAYER_DEPENDENCY"}
```

- [x] **Step 2: Run test and verify red**

Run:

```bash
pytest tests/assess/test_model_design.py::test_architecture_wrapper_uses_model_design_dimension -q
```

Expected: FAIL because `assess.scoring.model_design` does not exist.

- [x] **Step 3: Implement compatibility module**

Move the scoring implementation from `assess/scoring/architecture.py` into `assess/scoring/model_design.py` with the public name:

```python
def score_model_design_health(
    tables: list,
    edges: list,
    indirect_edges: list,
    llm_results: list = None,
    model_metadata: dict | None = None,
    business_domain_config=None,
    asset_catalog: dict | None = None,
) -> dict:
    ...
```

Keep existing rule ids for migrated dependency and LLM checks in this task.

Replace `assess/scoring/architecture.py` with:

```python
"""Compatibility wrapper for model design scoring."""

from assess.scoring.model_design import score_model_design_health


def score_architecture_health(*args, **kwargs) -> dict:
    return score_model_design_health(*args, **kwargs)
```

- [x] **Step 4: Run compatibility test and existing architecture tests**

Run:

```bash
pytest tests/assess/test_model_design.py::test_architecture_wrapper_uses_model_design_dimension -q
pytest tests/assess/test_assess_middle_layer.py -q
```

Expected: compatibility test passes. Existing tests may still fail later where they expect top-level `architecture`; those failures are addressed in Task 4.

## Task 2: Add SQL Fact Extraction For Layer Boundary And Grain Checks

**Files:**
- Modify: `assess/scoring/model_design.py`
- Test: `tests/assess/test_model_design.py`

- [x] **Step 1: Write failing tests for SQL facts**

Add tests:

```python
from assess.scoring.model_design import extract_model_design_sql_facts


def test_extract_model_design_sql_facts_detects_group_by_and_aggregates():
    sql = '''
    INSERT INTO shop_dm.dws_store_sales_daily
    SELECT store_id, order_date AS stat_date, SUM(subtotal) AS total_amount
    FROM shop_dm.dwd_order_detail
    GROUP BY store_id, order_date;
    '''

    facts = extract_model_design_sql_facts(sql)

    assert facts["has_group_by"] is True
    assert facts["has_aggregate"] is True
    assert facts["group_by_columns"] == ["order_date", "store_id"]
    assert "total_amount" in facts["aggregate_aliases"]


def test_extract_model_design_sql_facts_detects_plain_detail_select():
    sql = '''
    INSERT INTO shop_dm.dwd_order_detail
    SELECT order_item_id, order_id, subtotal
    FROM shop_dm.ods_order_item;
    '''

    facts = extract_model_design_sql_facts(sql)

    assert facts["has_group_by"] is False
    assert facts["has_aggregate"] is False
    assert facts["group_by_columns"] == []
    assert facts["aggregate_aliases"] == []
```

- [x] **Step 2: Run tests and verify red**

Run:

```bash
pytest tests/assess/test_model_design.py::test_extract_model_design_sql_facts_detects_group_by_and_aggregates tests/assess/test_model_design.py::test_extract_model_design_sql_facts_detects_plain_detail_select -q
```

Expected: FAIL because `extract_model_design_sql_facts` is not defined.

- [x] **Step 3: Implement SQL facts helper**

Implement `extract_model_design_sql_facts(sql_text: str) -> dict` in `assess/scoring/model_design.py` using `sqlglot.parse(..., dialect="doris")` first and regex fallback second. Return:

```python
{
    "has_group_by": bool,
    "has_aggregate": bool,
    "group_by_columns": list[str],
    "aggregate_aliases": list[str],
}
```

Treat `SUM`, `COUNT`, `AVG`, `MIN`, and `MAX` as aggregate functions. Normalize group-by names by stripping table qualifiers and aliases.

- [x] **Step 4: Run SQL facts tests**

Run:

```bash
pytest tests/assess/test_model_design.py::test_extract_model_design_sql_facts_detects_group_by_and_aggregates tests/assess/test_model_design.py::test_extract_model_design_sql_facts_detects_plain_detail_select -q
```

Expected: PASS.

## Task 3: Add Layer Boundary And Grain Clarity Rules

**Files:**
- Modify: `assess/scoring/config.py`
- Modify: `assess/scoring/model_design.py`
- Test: `tests/assess/test_model_design.py`

- [x] **Step 1: Write failing tests for model design checks**

Add tests:

```python
def test_model_design_flags_dwd_fact_with_group_by():
    asset_catalog = {
        "tables": {
            "dwd_order_summary": {
                "tasks": [{
                    "source_file": "dwd_order_summary.sql",
                    "sql": '''
                    INSERT INTO shop_dm.dwd_order_summary
                    SELECT order_id, SUM(subtotal) AS subtotal
                    FROM shop_dm.ods_order_item
                    GROUP BY order_id;
                    ''',
                }],
            },
        },
    }
    tables = [{
        "name": "dwd_order_summary",
        "layer": "DWD",
        "columns": [
            {"name": "order_id", "type": "BIGINT"},
            {"name": "subtotal", "type": "DECIMAL(12,2)"},
        ],
    }]
    model_metadata = {"dwd_order_summary": {"table_type": "fact"}}

    result = score_model_design_health(
        tables, [], [], model_metadata=model_metadata, asset_catalog=asset_catalog)

    assert _rule_ids(result) == {"MODEL_DWD_FACT_NO_AGGREGATION"}


def test_model_design_flags_dws_grain_mismatch_with_group_by():
    asset_catalog = {
        "tables": {
            "dws_store_sales_daily": {
                "tasks": [{
                    "source_file": "dws_store_sales_daily.sql",
                    "sql": '''
                    INSERT INTO shop_dm.dws_store_sales_daily
                    SELECT store_id, order_date AS stat_date, SUM(subtotal) AS total_amount
                    FROM shop_dm.dwd_order_detail
                    GROUP BY store_id, order_date;
                    ''',
                }],
            },
        },
    }
    tables = [{"name": "dws_store_sales_daily", "layer": "DWS", "columns": []}]
    model_metadata = {
        "dws_store_sales_daily": {
            "table_type": "fact",
            "grain": {"entities": ["CUSTOMER"], "time_column": "stat_date"},
            "entities": [{"code": "CUSTOMER", "type": "foreign", "key_columns": ["customer_id"]}],
        }
    }

    result = score_model_design_health(
        tables, [], [], model_metadata=model_metadata, asset_catalog=asset_catalog)

    assert "MODEL_DWS_GRAIN_MATCHES_GROUP_BY" in _rule_ids(result)
```

- [x] **Step 2: Run tests and verify red**

Run:

```bash
pytest tests/assess/test_model_design.py::test_model_design_flags_dwd_fact_with_group_by tests/assess/test_model_design.py::test_model_design_flags_dws_grain_mismatch_with_group_by -q
```

Expected: FAIL because the rule ids do not exist.

- [x] **Step 3: Add rule metadata**

Add to `assess/scoring/config.py`:

```python
MODEL_DESIGN_RULES = {
    **ARCHITECTURE_RULES,
    "MODEL_DWD_FACT_NO_AGGREGATION": rule_meta(...),
    "MODEL_DWS_GRAIN_PRESENT": rule_meta(...),
    "MODEL_DWS_GRAIN_MATCHES_GROUP_BY": rule_meta(...),
    "MODEL_DWD_FACT_HAS_EVENT_KEY": rule_meta(...),
}
```

Use high severity for DWD aggregation, medium for grain mismatch and missing grain, low for missing event key.

- [x] **Step 4: Implement checks**

In `score_model_design_health`, after existing dependency/LLM checks, add:

- DWD fact with `has_group_by` or `has_aggregate` fails `MODEL_DWD_FACT_NO_AGGREGATION`.
- DWS fact without grain fails `MODEL_DWS_GRAIN_PRESENT`.
- DWS fact grain key columns plus time column should be a subset-compatible match with SQL group-by columns. Mismatch fails `MODEL_DWS_GRAIN_MATCHES_GROUP_BY`.
- DWD fact without likely event key among columns or model entities fails `MODEL_DWD_FACT_HAS_EVENT_KEY`.

Likely event key names end with `_id`, `_no`, or `_key` and include event tokens such as `order`, `item`, `transaction`, `payment`, `event`, `detail`, `log`, `alert`, `application`, or `assessment`.

- [x] **Step 5: Run model design tests**

Run:

```bash
pytest tests/assess/test_model_design.py -q
```

Expected: PASS.

## Task 4: Wire `model_design` Into Assessment And CLI Dimension Selection

**Files:**
- Modify: `assess/assess_middle_layer.py`
- Modify: `tests/assess/test_assess_middle_layer.py`

- [x] **Step 1: Write failing tests for output key and selected dimensions**

Add or update tests:

```python
def test_assess_outputs_model_design_dimension(monkeypatch, sample_lineage_data):
    monkeypatch.setattr(
        "assess.assess_middle_layer.load_lineage_data",
        lambda project: sample_lineage_data,
    )

    result = assess("shop")

    assert "model_design" in result["dimensions"]
    assert "architecture" not in result["dimensions"]


def test_assess_can_run_selected_model_design_only(monkeypatch, sample_lineage_data):
    monkeypatch.setattr(
        "assess.assess_middle_layer.load_lineage_data",
        lambda project: sample_lineage_data,
    )

    result = assess("shop", selected_dimensions={"model_design"})

    assert set(result["dimensions"]) == {"model_design"}
```

- [x] **Step 2: Run tests and verify red**

Run:

```bash
pytest tests/assess/test_assess_middle_layer.py::test_assess_outputs_model_design_dimension tests/assess/test_assess_middle_layer.py::test_assess_can_run_selected_model_design_only -q
```

Expected: FAIL because `assess` does not accept `selected_dimensions` and still outputs `architecture`.

- [x] **Step 3: Update assessment wiring**

In `assess/assess_middle_layer.py`:

- import `score_model_design_health`.
- build `asset_catalog` before scoring model design.
- replace `architecture_score` with `model_design_score`.
- output `dimensions["model_design"]`.
- support optional `selected_dimensions: set[str] | None`.
- compute `overall_score` using only selected dimensions when selection is provided, otherwise default dimensions.

- [x] **Step 4: Add CLI flags**

Add flags:

```python
parser.add_argument("--model-design", action="store_true", help="只运行模型设计评分")
parser.add_argument("--architecture", action="store_true", help="兼容别名: 同 --model-design")
parser.add_argument("--metadata-health", action="store_true", help="只运行元数据健康度评分")
parser.add_argument("--asset-completeness", action="store_true", help="只运行资产完整性评分")
parser.add_argument("--code-quality", action="store_true", help="只运行代码质量评分")
parser.add_argument("--reuse", action="store_true", help="只运行复用度评分")
parser.add_argument("--depth", action="store_true", help="只运行链路深度评分")
parser.add_argument("--naming", action="store_true", help="只运行命名规范评分")
```

Construct `selected_dimensions` from flags. Map `--architecture` to `model_design`.

- [x] **Step 5: Run assessment tests**

Run:

```bash
pytest tests/assess/test_assess_middle_layer.py -q
```

Expected: PASS.

## Task 5: Full Verification And Commit

**Files:**
- All changed implementation and test files.

- [x] **Step 1: Run focused tests**

Run:

```bash
pytest tests/assess/test_model_design.py tests/assess/test_assess_middle_layer.py -q
```

Expected: PASS.

- [x] **Step 2: Run non-API test suite**

Run:

```bash
pytest -q -m "not api"
```

Expected: PASS.

- [x] **Step 3: Inspect diff**

Run:

```bash
git diff --stat
git status --short --branch
```

Expected: Changed files are limited to scoring, assessment CLI, tests, and plan docs. Existing unrelated `assess/model_metadata_result_finance_analytics.json` remains unstaged unless the user asks otherwise.

- [x] **Step 4: Commit implementation**

Run:

```bash
git add assess/scoring/model_design.py assess/scoring/architecture.py assess/scoring/config.py assess/assess_middle_layer.py tests/assess/test_model_design.py tests/assess/test_assess_middle_layer.py docs/superpowers/plans/2026-06-12-model-design-assessment.md
git commit -m "feat(assess): add model design assessment checks"
```

Expected: Commit succeeds.

