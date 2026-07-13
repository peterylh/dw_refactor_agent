# Refactor AGENTS Documentation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a detailed refactor directory guide and reduce the root guide to project-level refactor navigation.

**Architecture:** Move module-specific workflow and artifact semantics into `src/dw_refactor_agent/refactor/AGENTS.md`. Keep `AGENTS.md` as a stable index that links to the directory guide and gives only the main commands and artifact root.

**Tech Stack:** Markdown, Python CLI source inspection, Git whitespace validation

## Global Constraints

- Use the standard uppercase filename `AGENTS.md`.
- Keep `docs/refactor_guides/` focused on warehouse asset refactoring operations.
- Document the current implementation; do not change Python behavior or generated artifacts.
- Run project checks through the configured `dw-refactor-py37` conda environment or Makefile, never bare `pytest`.

---

### Task 1: Verify Current Refactor Interfaces and Outputs

**Files:**
- Read: `src/dw_refactor_agent/refactor/run.py`
- Read: `src/dw_refactor_agent/refactor/session.py`
- Read: `src/dw_refactor_agent/refactor/change_analysis.py`
- Read: `src/dw_refactor_agent/refactor/verification_plan.py`
- Read: `src/dw_refactor_agent/refactor/shadow_manifest.py`
- Read: `src/dw_refactor_agent/refactor/shadow_run.py`
- Read: `src/dw_refactor_agent/refactor/compare.py`

**Interfaces:**
- Consumes: Current CLI parser definitions, run path constants, and JSON writer call sites.
- Produces: Verified command names, output paths, lifecycle rules, and terminology for Tasks 2 and 3.

- [ ] **Step 1: Inspect CLI and artifact writer definitions**

Run:

```bash
rg -n "add_parser|add_argument|write_json|manifest|baseline|current|analysis|verification" src/dw_refactor_agent/refactor
```

Expected: matches identify all four workflow commands and their output-producing code.

- [ ] **Step 2: Inspect the complete relevant source sections**

Run `sed -n` on the matching ranges and record the exact current names in the directory guide. Expected: every documented path and option is backed by source.

### Task 2: Create the Directory-Level Refactor Guide

**Files:**
- Create: `src/dw_refactor_agent/refactor/AGENTS.md`

**Interfaces:**
- Consumes: Verified interfaces and artifact names from Task 1.
- Produces: The authoritative module-level instructions linked by the root guide.

- [ ] **Step 1: Write the module scope and responsibility map**

Document which changes are governed by this file and describe each Python module in one concise entry.

- [ ] **Step 2: Write the standard workflow and runtime constraints**

Include exact commands for `start`, `analyze`, `shadow-run`, and `compare`; cover partition requirements, dry-run, minimal recomputation, production read-through, QA writes, and comparison exclusions.

- [ ] **Step 3: Explain the output tree and lifecycle**

Include the `refactor_runs/{run_id}` tree and explain `manifest.json`, `baseline/`, `current/`, `analysis/`, and `verification/`, including which outputs are frozen and which are regenerated.

- [ ] **Step 4: Add maintenance checks**

State that changes must keep CLI help, JSON schemas/consumers, guides, and focused tests synchronized.

### Task 3: Reduce Root Refactor Documentation to a Summary

**Files:**
- Modify: `AGENTS.md`

**Interfaces:**
- Consumes: `src/dw_refactor_agent/refactor/AGENTS.md` as the detailed authority.
- Produces: A project-level summary and link without duplicated detailed semantics.

- [ ] **Step 1: Replace the long refactor section**

Keep the supported-project summary, directory-guide link, four main commands, artifact root, and schema-identity baseline warning. Remove detailed plan fields, phase explanations, compare options, and row-exclusion examples.

- [ ] **Step 2: Check cross-document boundaries**

Run:

```bash
rg -n "refactor/AGENTS.md|verification/plan.json|compare_result.json|Phase [0-3]|exclude_columns" AGENTS.md src/dw_refactor_agent/refactor/AGENTS.md
```

Expected: the root guide links to the directory guide; detailed terms primarily occur in the directory guide.

### Task 4: Validate Documentation

**Files:**
- Verify: `AGENTS.md`
- Verify: `src/dw_refactor_agent/refactor/AGENTS.md`

**Interfaces:**
- Consumes: Completed documentation changes.
- Produces: Evidence that formatting, links, commands, and source terminology are consistent.

- [ ] **Step 1: Run whitespace validation**

Run:

```bash
git diff --check
```

Expected: exit code 0 with no output.

- [ ] **Step 2: Verify links and command/module names**

Run targeted `test -e` and `rg` checks for every linked local file and documented `dw_refactor_agent.refactor` module. Expected: all paths exist and all workflow commands match `run.py`.

- [ ] **Step 3: Review the final diff**

Run:

```bash
git diff -- AGENTS.md src/dw_refactor_agent/refactor/AGENTS.md
```

Expected: one new detailed module guide and a substantially shorter root refactor section, with no Python changes.
