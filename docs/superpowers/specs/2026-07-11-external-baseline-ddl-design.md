# External Baseline DDL Design

## Goal

Move baseline DDL text out of `verification/plan.json` into standalone SQL
files while keeping the verification plan deterministic and self-validating.

## Artifact layout

Each `analyze` invocation writes the required baseline definitions under the
same verification directory as the plan:

```text
verification/
├── baseline_ddl/
│   ├── dwd_inventory.sql
│   └── dws_store_sales_daily.sql
└── plan.json
```

`plan.json` contains references instead of SQL text:

```json
{
  "baseline_ddl_refs": {
    "dwd_inventory": {
      "path": "baseline_ddl/dwd_inventory.sql",
      "sha256": "<lowercase hex digest>"
    }
  }
}
```

Paths are POSIX paths relative to `plan.json`. Table names remain the map keys
so consumers do not infer table identity from filenames.

## Compatibility boundary

Only the new reference format is supported. A plan containing the old
top-level `baseline_ddl` field is rejected with an error explaining that the
run must be recreated or analyzed again. There is no legacy fallback loader.

An empty `baseline_ddl_refs` map is valid when the plan needs no baseline
tables. Missing, malformed, absolute, or escaping paths are invalid.

## Producer flow

`build_verification_plan` continues to calculate the minimal required baseline
DDL as text because that calculation belongs to planning. A dedicated plan
artifact writer then:

1. validates table names before using them as filenames;
2. writes each planner-provided DDL text unchanged to one UTF-8 SQL file per
   table;
3. computes SHA-256 over the exact UTF-8 bytes written;
4. replaces the transient DDL payload with `baseline_ddl_refs` in serialized
   `plan.json`;
5. removes stale `.sql` files in `verification/baseline_ddl/` that are not
   referenced by the new plan.

The writer returns the serialized plan representation so subsequent analyze
logic uses the same public structure that was written to disk.

## Consumer flow

A single loader reads `plan.json`, rejects the legacy field, validates every
reference, resolves it relative to the plan directory, verifies its SHA-256,
and materializes an internal `baseline_ddl: dict[str, str]` for existing
shadow-manifest and execution code.

Only file-backed CLI entry points need resolution. Internal functions that
already receive an executable in-memory plan continue consuming materialized
DDL, keeping routing and execution logic independent from artifact storage.

Reference failures stop before QA database reset. Error messages identify the
table and the invalid, missing, or digest-mismatched file.

## DDL source fidelity

The writer does not format or regenerate DDL. Multiline source remains
multiline and single-line source remains single-line. This avoids changing
Doris-specific syntax, comments, schema identity annotations, statement
terminators, or other meaningful source text. The executable SQL and the
standalone SQL file are the same text; there is no hidden formatted copy.

## Manifest and documentation

The manifest continues pointing to `verification/plan.json`; individual DDL
files do not need separate manifest artifact keys because they are owned by and
resolved through the plan. Refactor documentation will describe
`baseline_ddl_refs` and show the new directory layout.

## Tests

Tests cover:

- serialization preserves exact DDL text and writes reference metadata;
- hashes match the exact file bytes;
- rerunning analyze removes stale baseline DDL files;
- filenames cannot escape the baseline DDL directory;
- the loader materializes referenced DDL for shadow execution;
- legacy embedded DDL, missing files, invalid paths, and digest mismatches fail
  before execution;
- an empty reference map works;
- analyze writes the new artifact layout;
- existing shadow-manifest and shadow-run behavior remains unchanged after
  loading a referenced plan.

Focused refactor tests run first. The final verification runs the repository's
non-API suite through the configured `dw-refactor-py37` environment, followed
by a code review of the resulting diff.
