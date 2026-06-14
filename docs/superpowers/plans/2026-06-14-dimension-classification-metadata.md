# Dimension Classification Metadata Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add DIM role/content classification metadata and use it to validate DIM naming accuracy.

**Architecture:** Extend the existing LLM table inspection result with two DIM-only enum fields, persist them through the model metadata writer, and add a naming scorer check that aligns model values with the DIM table-name segments. Keep the change inside the current assess/naming stack.

**Tech Stack:** Python, PyYAML, pytest, existing `NamingConfig` parser and assess scoring helpers.

---

### Task 1: Add Red Tests

**Files:**
- Modify: `tests/assess/test_table_inspector.py`
- Modify: `tests/assess/test_model_metadata_writer.py`
- Modify: `tests/assess/test_assess_middle_layer.py`
- Modify: `tests/test_naming_config.py`

- [x] Add tests asserting prompt, parser, cache/report, model writer, config parser, and naming scorer behavior for `dimension_role` and `dimension_content_type`.
- [x] Run:

```bash
pytest tests/assess/test_table_inspector.py \
  tests/assess/test_model_metadata_writer.py \
  tests/assess/test_assess_middle_layer.py \
  tests/test_naming_config.py -q
```

Expected: failures mention missing prompt strings, missing result attributes, old DIM segment names, or missing naming rule output.

### Task 2: Implement LLM Result Metadata

**Files:**
- Modify: `assess/llm/table_inspector.py`

- [x] Add enum constants for valid DIM roles and content types.
- [x] Add `dimension_role` and `dimension_content_type` to `TableInspectResult`.
- [x] Add prompt rules and JSON schema fields.
- [x] Normalize values in `parse_response` and `dict_to_result`.
- [x] Include fields in `result_to_dict` and `result_to_cache_dict`.

### Task 3: Implement Model Writer Persistence

**Files:**
- Modify: `assess/llm/model_metadata_writer.py`

- [x] Write DIM classification fields when table metadata is written for a DIM result.
- [x] Remove stale DIM classification fields when the applied layer is not DIM.
- [x] Report previous/current values and metadata change status.

### Task 4: Rename DIM Naming Segments

**Files:**
- Modify: `naming_config.yaml`
- Modify: `shop/naming_config.yaml`
- Modify: `finance_analytics/naming_config.yaml`
- Modify: `tests/test_naming_config.py`

- [x] Rename `DIM_SCOPE` to `DIM_ROLE`.
- [x] Rename `DIM_TYPE` to `DIM_CONTENT_TYPE`.
- [x] Update DIM table template expressions and tests.

### Task 5: Implement Naming Alignment Check

**Files:**
- Modify: `assess/scoring/config.py`
- Modify: `assess/scoring/naming.py`

- [x] Add `NAMING_DIM_CLASSIFICATION_ALIGNMENT` rule metadata.
- [x] Parse `DIM_ROLE` and `DIM_CONTENT_TYPE` from DIM names.
- [x] Compare parsed values to `models.dimension_role` and `models.dimension_content_type`.
- [x] Include the check in table score and detailed check output.

### Task 6: Verify

**Files:**
- No code changes.

- [x] Run targeted tests from Task 1 and confirm all pass.
- [x] Run:

```bash
pytest -q -m "not api"
```

Expected: all non-API tests pass.
