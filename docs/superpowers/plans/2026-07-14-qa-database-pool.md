# Shadow-run QA Database Pool Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the project-wide destructive QA database reset with a pre-created, atomically claimed QA database pool, plus provenance-safe compare and manual cleanup commands.

**Architecture:** Persist the logical run ID and configured pool in each verification plan. A focused `qa_pool.py` module owns pool validation, immutable marker inspection, atomic claim, selection, and marker-last release; shadow-run and compare consume an exact claimed slot while `run.py` remains the thin CLI orchestrator. Pool slots are fixed Doris databases, so the QA account never needs permission to create arbitrary databases.

**Tech Stack:** Python 3.7, PyMySQL, Doris SQL, argparse, pytest 7, Ruff 0.12, YAML configuration.

## Global Constraints

- Use `dw-refactor-py37`; run tests through `make test` or an explicitly selected interpreter, never bare `pytest`.
- Do not add a resident agent, TTL janitor, heartbeat, lease, or execution lifecycle status.
- Never write to a production database; production is a read-only source for shadow-run and compare.
- Actual shadow-run and compare never drop or create a database.
- Claimed slots remain allocated until an explicit cleanup command releases them.
- Marker, plan, workspace, run, execution, and physical database ownership must fail closed on every mismatch.
- SQL identifiers must pass a strict identifier validator and be quoted; SQL values must use PyMySQL parameters.
- Cleanup deletes ordinary objects first and the marker table last.
- Cleanup without `--yes` is preview-only; bulk deletion without a selector is rejected.
- A markerless non-empty slot, a malformed marker, and a legacy marker are never automatically allocated.
- Keep Python syntax and standard-library use compatible with Python 3.7.

---

## File Structure

- Create `src/dw_refactor_agent/refactor/qa_pool.py`: pool configuration, dataclasses, Doris connection boundary, slot inspection, claim, cleanup selection, and release.
- Create `tests/refact/test_qa_pool.py`: pure and mocked-DB tests for pool behavior.
- Modify `src/dw_refactor_agent/config/core.py`: validate and normalize `verification.qa_database_pool` while loading warehouse configuration.
- Modify `src/dw_refactor_agent/refactor/verification_plan.py`: persist the normalized pool.
- Modify `src/dw_refactor_agent/refactor/plan_artifact.py`: validate persisted run/pool fields and preserve plan fingerprint behavior.
- Modify `src/dw_refactor_agent/refactor/run.py`: persist run ID, add cleanup CLI, and pass exact execution provenance.
- Modify `src/dw_refactor_agent/refactor/execution_provenance.py`: keep only run-scoped artifact locking; move marker SQL to `qa_pool.py`.
- Modify `src/dw_refactor_agent/refactor/shadow_run.py`: preview compile, claim, runtime recompile, and execute without database reset.
- Modify `src/dw_refactor_agent/refactor/compare.py`: resolve the physical database from the shadow result and validate exact ownership.
- Modify `tests/test_project_asset_paths.py`, `tests/refact/test_verification_plan.py`, `tests/refact/test_plan_artifact.py`, `tests/refact/test_run_cli.py`, `tests/refact/test_shadow_run.py`, and `tests/refact/test_compare.py` for public contract coverage.
- Modify `warehouses/shop/warehouse.yaml`: configure `shop_dm_qa` and `shop_dm_qa_02` as Shop pool members.
- Modify `AGENTS.md` and `src/dw_refactor_agent/refactor/AGENTS.md`: document pool, cleanup, concurrency, and real-validation behavior.

---

### Task 1: Persist and Validate the Pool Contract

**Files:**
- Create: `src/dw_refactor_agent/refactor/qa_pool.py`
- Modify: `src/dw_refactor_agent/config/core.py`
- Modify: `src/dw_refactor_agent/refactor/verification_plan.py`
- Modify: `src/dw_refactor_agent/refactor/plan_artifact.py`
- Modify: `src/dw_refactor_agent/refactor/run.py`
- Test: `tests/refact/test_qa_pool.py`
- Test: `tests/test_project_asset_paths.py`
- Test: `tests/refact/test_verification_plan.py`
- Test: `tests/refact/test_plan_artifact.py`
- Test: `tests/refact/test_run_cli.py`

**Interfaces:**
- Produces: `configured_qa_pool(project: str, project_config: dict) -> tuple[str, ...]`.
- Produces: `validate_qa_identifier(value: str) -> str`.
- Produces persisted plan fields `run_id: str` and `qa_database_pool: list[str]`.
- Consumers in later tasks must treat `qa_db` as a dry-run/default route only and `qa_database_pool` as the allowed physical database set.

- [ ] **Step 1: Write failing configuration tests**

Add `tests/refact/test_qa_pool.py`:

```python
import pytest

from dw_refactor_agent.refactor.qa_pool import configured_qa_pool


def test_configured_qa_pool_normalizes_explicit_pool():
    assert configured_qa_pool(
        "shop",
        {
            "db": "shop_dm",
            "qa_db": "shop_dm_qa",
            "lineage_db": "shop_lineage",
            "verification": {
                "qa_database_pool": ["shop_dm_qa", "shop_dm_qa_02"]
            },
        },
    ) == ("shop_dm_qa", "shop_dm_qa_02")


def test_configured_qa_pool_falls_back_to_legacy_qa_database():
    assert configured_qa_pool(
        "shop",
        {"db": "shop_dm", "qa_db": "shop_dm_qa"},
    ) == ("shop_dm_qa",)


@pytest.mark.parametrize(
    "pool, expected",
    [
        ([], "non-empty"),
        (["shop_dm"], "production database"),
        (["shop_lineage"], "lineage database"),
        (["bad-name"], "identifier"),
        (["shop_dm_qa", "SHOP_DM_QA"], "duplicate"),
    ],
)
def test_configured_qa_pool_rejects_unsafe_values(pool, expected):
    with pytest.raises(ValueError, match=expected):
        configured_qa_pool(
            "shop",
            {
                "db": "shop_dm",
                "qa_db": "shop_dm_qa",
                "lineage_db": "shop_lineage",
                "verification": {"qa_database_pool": pool},
            },
        )
```

Extend the project config tests to assert Shop loads the two configured values after Task 7 updates its YAML.

- [ ] **Step 2: Write failing plan contract tests**

Update plan helpers to include `run_id="test-run"` and assert:

```python
def test_verification_plan_includes_normalized_qa_pool(
    sample_change_analysis, monkeypatch
):
    monkeypatch.setitem(
        config.PROJECT_CONFIG["shop"].setdefault("verification", {}),
        "qa_database_pool",
        ["shop_dm_qa", "shop_dm_qa_02"],
    )
    plan = build_verification_plan(
        "shop",
        sample_change_analysis,
        base_ref="HEAD",
        lineage_data={"tables": [], "edges": []},
    )
    assert plan["qa_db"] == "shop_dm_qa"
    assert plan["qa_database_pool"] == ["shop_dm_qa", "shop_dm_qa_02"]


def test_persisted_plan_rejects_database_outside_pool(tmp_path):
    plan_path = tmp_path / "verification" / "plan.json"
    persisted = write_verification_plan(
        plan_path,
        {
            **_plan({}),
            "run_id": "test-run",
            "qa_database_pool": ["other_qa"],
        },
    )
    with pytest.raises(ArtifactFormatError, match="qa_db.*pool"):
        load_persisted_verification_plan(plan_path)
```

Add a run CLI assertion that `_build_plan_for_run` copies `manifest["run_id"]` into the plan before `write_verification_plan`.

- [ ] **Step 3: Run the focused tests and verify failure**

Run:

```bash
make test PYTEST_ARGS='-q -m "not api" tests/refact/test_qa_pool.py tests/test_project_asset_paths.py tests/refact/test_verification_plan.py tests/refact/test_plan_artifact.py tests/refact/test_run_cli.py'
```

Expected: collection fails because `qa_pool.py` and `configured_qa_pool` do not exist, followed by plan assertions failing when imported incrementally.

- [ ] **Step 4: Implement the pure pool/config contract**

Create the initial `qa_pool.py` API:

```python
from __future__ import annotations

import re

_IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_SYSTEM_DATABASES = {"information_schema", "mysql"}


def validate_qa_identifier(value: str) -> str:
    normalized = str(value or "").strip()
    if not _IDENTIFIER_RE.fullmatch(normalized):
        raise ValueError(f"invalid Doris database identifier: {value!r}")
    return normalized


def configured_qa_pool(
    project: str,
    project_config: dict,
) -> tuple[str, ...]:
    verification = project_config.get("verification") or {}
    raw_pool = verification.get("qa_database_pool")
    if raw_pool is None:
        raw_pool = [project_config.get("qa_db")]
    if not isinstance(raw_pool, list) or not raw_pool:
        raise ValueError(
            f"{project} verification.qa_database_pool must be a non-empty list"
        )
    pool = tuple(validate_qa_identifier(value) for value in raw_pool)
    canonical = [value.casefold() for value in pool]
    if len(canonical) != len(set(canonical)):
        raise ValueError(f"{project} QA database pool contains duplicate names")
    protected = {
        str(project_config.get("db") or "").casefold(): "production database",
        str(project_config.get("lineage_db") or "").casefold(): "lineage database",
        **{value: "system database" for value in _SYSTEM_DATABASES},
    }
    for database in pool:
        reason = protected.get(database.casefold())
        if reason:
            raise ValueError(
                f"{project} QA pool cannot contain {reason}: {database}"
            )
    return pool
```

Have `config/core.py` validate the raw YAML value is a non-empty list of non-empty strings without importing the higher-level refactor module, and retain the original verification mapping. `configured_qa_pool()` performs the canonical duplicate and protected-database validation used by planning and cleanup. Have `verification_plan.py` emit `qa_database_pool=list(configured_qa_pool(project, cfg))`. In `_build_plan_for_run`, set `plan["run_id"] = manifest["run_id"]`. Extend persisted-plan validation to require a non-empty, unique list, require `qa_db` to be a member, and require a non-empty `run_id` for newly written plans.

- [ ] **Step 5: Run the focused tests and verify pass**

Run the command from Step 3.

Expected: all selected tests pass; Ruff reports no lint or format errors.

- [ ] **Step 6: Commit**

```bash
git add src/dw_refactor_agent/config/core.py src/dw_refactor_agent/refactor/qa_pool.py src/dw_refactor_agent/refactor/verification_plan.py src/dw_refactor_agent/refactor/plan_artifact.py src/dw_refactor_agent/refactor/run.py tests/refact/test_qa_pool.py tests/test_project_asset_paths.py tests/refact/test_verification_plan.py tests/refact/test_plan_artifact.py tests/refact/test_run_cli.py
git commit -m "feat(refactor): persist QA database pools"
```

---

### Task 2: Inspect New, Legacy, and Invalid Pool Slots

**Files:**
- Modify: `src/dw_refactor_agent/refactor/qa_pool.py`
- Test: `tests/refact/test_qa_pool.py`

**Interfaces:**
- Consumes: `configured_qa_pool()` and `validate_qa_identifier()` from Task 1.
- Produces: `QaSlotOwnership`, `QaSlotInspection`, `get_qa_connection()`, `inspect_qa_slot()`, and `require_slot_ownership()`.
- Availability values are exactly `free`, `claimed`, `legacy`, and `invalid`; they are not execution lifecycle states.

- [ ] **Step 1: Add failing slot-inspection tests**

Use a scripted fake cursor/connection and assert stable structured results:

```python
class ScriptedCursor:
    def __init__(self, responses):
        self.responses = responses
        self.rows = []

    def execute(self, sql, params=None):
        for pattern, rows in self.responses:
            if pattern in sql:
                self.rows = list(rows)
                return
        raise AssertionError(f"unexpected SQL: {sql}")

    def fetchall(self):
        return list(self.rows)

    def close(self):
        pass


class ScriptedConnection:
    def __init__(self):
        self.responses = []

    def add(self, pattern, rows):
        self.responses.append((pattern, rows))

    def cursor(self):
        return ScriptedCursor(self.responses)

    def close(self):
        pass


@pytest.fixture
def scripted_connection():
    return ScriptedConnection()


def test_inspect_empty_slot_returns_free(scripted_connection):
    scripted_connection.add("SHOW FULL TABLES", [])
    result = inspect_qa_slot("shop", "shop_dm_qa_02", connection=scripted_connection)
    assert result == QaSlotInspection(
        project="shop",
        database="shop_dm_qa_02",
        availability="free",
        ownership=None,
        diagnostic=None,
        objects=(),
    )


def test_inspect_current_marker_schema_returns_legacy(scripted_connection):
    scripted_connection.add(
        "SHOW FULL TABLES",
        [("dw_refactor_execution_marker", "BASE TABLE")],
    )
    scripted_connection.add(
        "SHOW COLUMNS",
        [("marker_key",), ("execution_id",), ("plan_fingerprint",),
         ("workspace_fingerprint",), ("completed_at",)],
    )
    result = inspect_qa_slot("shop", "shop_dm_qa", connection=scripted_connection)
    assert result.availability == "legacy"
    assert result.ownership is None


def test_inspect_valid_marker_returns_exact_ownership(scripted_connection):
    scripted_connection.add(
        "SHOW FULL TABLES",
        [("dw_refactor_execution_marker", "BASE TABLE")],
    )
    scripted_connection.add(
        "SHOW COLUMNS",
        [(name,) for name in MARKER_COLUMNS],
    )
    scripted_connection.add(
        "UNIX_TIMESTAMP(claimed_at)",
        [(
            2, "current", "shop", "run-1", "execution-1",
            "shop_dm_qa_02", "sha256:" + "a" * 64,
            "sha256:" + "b" * 64, "2026-07-14 11:33:20", 1784000000,
        )],
    )
    result = inspect_qa_slot("shop", "shop_dm_qa_02", connection=scripted_connection)
    assert result.availability == "claimed"
    assert result.ownership.execution_id == "execution-1"
    assert result.ownership.qa_database == "shop_dm_qa_02"
    assert result.ownership.claimed_at_epoch == 1784000000
```

Also cover marker absent with ordinary tables (`invalid`), wrong format version (`invalid`), duplicate/missing marker rows (`invalid`), and marker `qa_database` mismatch (`invalid`).

- [ ] **Step 2: Run the tests and verify failure**

Run:

```bash
make test PYTEST_ARGS='-q -m "not api" tests/refact/test_qa_pool.py'
```

Expected: failures report missing dataclasses and inspection functions.

- [ ] **Step 3: Implement slot dataclasses and inspection**

Add these public contracts:

```python
@dataclass(frozen=True)
class QaSlotOwnership:
    format_version: int
    project: str
    run_id: str
    execution_id: str
    qa_database: str
    plan_fingerprint: str
    workspace_fingerprint: str
    claimed_at: str
    claimed_at_epoch: int


@dataclass(frozen=True)
class QaSlotInspection:
    project: str
    database: str
    availability: str
    ownership: QaSlotOwnership | None
    diagnostic: str | None
    objects: tuple[tuple[str, str], ...]
```

Because Python 3.7 evaluates annotations through `from __future__ import annotations`, retain the repository's existing union/type style. `get_qa_connection(database="information_schema")` must use `DORIS_HOST`, `DORIS_PORT`, `DORIS_QA_USER`, `charset="utf8mb4"`, and `autocommit=True`.

`inspect_qa_slot()` must issue quoted `SHOW FULL TABLES`, compare marker columns against an exact `MARKER_COLUMNS` tuple, recognize the existing five-column marker as legacy, and select the new marker with `UNIX_TIMESTAMP(claimed_at)` so age comparisons do not depend on the runner timezone.

`require_slot_ownership()` accepts expected project/run/execution/database/fingerprints, calls `inspect_qa_slot`, and raises `ArtifactFormatError` unless every field matches exactly.

- [ ] **Step 4: Run the tests and verify pass**

Run the command from Step 2.

Expected: all pool inspection tests pass.

- [ ] **Step 5: Commit**

```bash
git add src/dw_refactor_agent/refactor/qa_pool.py tests/refact/test_qa_pool.py
git commit -m "feat(refactor): inspect QA pool ownership"
```

---

### Task 3: Claim and Release Slots Atomically

**Files:**
- Modify: `src/dw_refactor_agent/refactor/qa_pool.py`
- Test: `tests/refact/test_qa_pool.py`

**Interfaces:**
- Consumes: slot models and inspection from Task 2.
- Produces: `claim_qa_slot(*, project: str, run_id: str, execution_id: str, pool: tuple[str, ...], plan_fingerprint: str, workspace_fingerprint: str) -> QaSlotOwnership`.
- Produces: `select_cleanup_slots(inspections: list[QaSlotInspection], *, project: str | None, run_id: str | None, execution_id: str | None, database: str | None, cutoff_epoch: int | None) -> list[QaSlotInspection]`.
- Produces: `release_qa_slot(inspection: QaSlotInspection, *, configured_pool: tuple[str, ...], protected_databases: set[str]) -> dict`.
- Produces: `QaPoolExhaustedError(ArtifactFormatError)` with `inspections` for diagnostics.
- Produces private seam `_try_claim_slot(database: str, **ownership_fields) -> QaSlotOwnership | None`; `None` means an atomic table-exists race, while other SQL failures raise.

- [ ] **Step 1: Write failing atomic-claim tests**

```python
def test_claim_rotates_pool_and_returns_verified_owner(monkeypatch):
    owner = QaSlotOwnership(
        2, "shop", "run-1", "execution-1", "shop_dm_qa_02",
        "sha256:" + "a" * 64, "sha256:" + "b" * 64,
        "2026-07-14 12:00:00", 1784001600,
    )
    inspections = {
        "shop_dm_qa": QaSlotInspection(
            "shop", "shop_dm_qa", "claimed", owner, None, ()
        ),
        "shop_dm_qa_02": QaSlotInspection(
            "shop", "shop_dm_qa_02", "free", None, None, ()
        ),
    }
    calls = []
    monkeypatch.setattr(
        qa_pool, "_rotated_pool", lambda pool, execution_id: tuple(pool)
    )
    monkeypatch.setattr(
        qa_pool,
        "inspect_qa_slot",
        lambda project, database, **kwargs: inspections[database],
    )
    monkeypatch.setattr(
        qa_pool,
        "_try_claim_slot",
        lambda database, **fields: calls.append(database) or owner,
    )
    owner = claim_qa_slot(
        project="shop",
        run_id="run-1",
        execution_id="execution-1",
        pool=("shop_dm_qa", "shop_dm_qa_02"),
        plan_fingerprint="sha256:" + "a" * 64,
        workspace_fingerprint="sha256:" + "b" * 64,
    )
    assert owner.qa_database == "shop_dm_qa_02"
    assert calls == ["shop_dm_qa_02"]


def test_claim_loser_moves_to_next_slot_after_duplicate_table(monkeypatch):
    owner = QaSlotOwnership(
        2, "shop", "run-1", "execution-1", "shop_dm_qa_02",
        "sha256:" + "a" * 64, "sha256:" + "b" * 64,
        "2026-07-14 12:00:00", 1784001600,
    )
    monkeypatch.setattr(
        qa_pool,
        "_rotated_pool",
        lambda pool, execution_id: tuple(pool),
    )
    monkeypatch.setattr(
        qa_pool,
        "_try_claim_slot",
        lambda database, **fields: (
            None if database == "shop_dm_qa" else owner
        ),
    )
    result = claim_qa_slot(
        project="shop",
        run_id="run-1",
        execution_id="execution-1",
        pool=("shop_dm_qa", "shop_dm_qa_02"),
        plan_fingerprint="sha256:" + "a" * 64,
        workspace_fingerprint="sha256:" + "b" * 64,
    )
    assert result.qa_database == "shop_dm_qa_02"


def test_claim_exhaustion_never_drops_or_overwrites(monkeypatch):
    owner = QaSlotOwnership(
        2, "shop", "run-1", "execution-old", "shop_dm_qa",
        "sha256:" + "c" * 64, "sha256:" + "d" * 64,
        "2026-07-13 12:00:00", 1783915200,
    )
    monkeypatch.setattr(
        qa_pool,
        "inspect_qa_slot",
        lambda project, database, **kwargs: QaSlotInspection(
            project, database, "claimed", owner, None, ()
        ),
    )
    monkeypatch.setattr(
        qa_pool,
        "_try_claim_slot",
        lambda database, **fields: (_ for _ in ()).throw(
            AssertionError("claimed slots must not be overwritten")
        ),
    )
    with pytest.raises(QaPoolExhaustedError) as exc:
        claim_qa_slot(
            project="shop",
            run_id="run-1",
            execution_id="execution-1",
            pool=("shop_dm_qa", "shop_dm_qa_02"),
            plan_fingerprint="sha256:" + "a" * 64,
            workspace_fingerprint="sha256:" + "b" * 64,
        )
    assert {item.database for item in exc.value.inspections} == {
        "shop_dm_qa", "shop_dm_qa_02"
    }
```

Add release tests that assert views precede tables, the marker is the final DROP, a business-object failure prevents marker deletion, and exact legacy/invalid release is only possible for a configured pool member selected by database name.

- [ ] **Step 2: Run tests and verify failure**

Run:

```bash
make test PYTEST_ARGS='-q -m "not api" tests/refact/test_qa_pool.py'
```

Expected: missing claim/release APIs.

- [ ] **Step 3: Implement claim SQL and deterministic rotation**

Use `sha256(execution_id.encode("utf-8"))` modulo pool size for the starting index. Create the marker without `IF NOT EXISTS`, using `UNIQUE KEY(marker_key)` and replication 1. Insert the single `current` row with parameterized values and `NOW()`, then call `require_slot_ownership()` before returning.

Only error code 1050 or a message that unambiguously says the marker table already exists is a claim race. All other SQL errors raise `ArtifactFormatError`; failed insert/readback leaves the marker in place so the slot becomes invalid.

- [ ] **Step 4: Implement selector and marker-last release**

`select_cleanup_slots()` takes optional project, run ID, execution ID, database, cutoff epoch, and all-projects flag. It combines supplied selectors with AND semantics. Time selectors match only valid claimed ownership. Legacy/invalid entries match only an exact database selector.

`release_qa_slot()` re-inspects immediately before mutation, rejects databases outside the supplied project pool/protected set, drops views before base tables, stops on the first ordinary-object failure, and drops `dw_refactor_execution_marker` last. It returns:

```python
{
    "project": inspection.project,
    "database": inspection.database,
    "result": "released",
    "dropped_objects": ["view_a", "table_a", "dw_refactor_execution_marker"],
}
```

- [ ] **Step 5: Run tests and verify pass**

Run the command from Step 2.

Expected: all claim, race, exhaustion, selector, and release tests pass.

- [ ] **Step 6: Commit**

```bash
git add src/dw_refactor_agent/refactor/qa_pool.py tests/refact/test_qa_pool.py
git commit -m "feat(refactor): claim and release QA pool slots"
```

---

### Task 4: Route Shadow-run Through a Claimed Slot

**Files:**
- Modify: `src/dw_refactor_agent/refactor/execution_provenance.py`
- Modify: `src/dw_refactor_agent/refactor/shadow_run.py`
- Test: `tests/refact/test_shadow_run.py`
- Test: `tests/refact/test_shadow_manifest.py`

**Interfaces:**
- Consumes: `claim_qa_slot()` and `require_slot_ownership()`.
- Produces: `run_execution_lock(plan_path: Path)` and execute-mode shadow results with exact `run_id`, `execution_id`, `qa_db`, and fingerprints.
- `execute_shadow_plan()` receives an already claimed runtime plan and never allocates or resets a database itself.

- [ ] **Step 1: Replace project-lock and reset tests with failing pool tests**

Add assertions equivalent to:

```python
def test_run_locks_differ_between_runs_and_match_across_worktrees(tmp_path):
    first = _lock_path(tmp_path / "one/warehouses/shop/artifacts/refactor_runs/run-a/verification/plan.json")
    second = _lock_path(tmp_path / "two/warehouses/shop/artifacts/refactor_runs/run-a/verification/plan.json")
    other = _lock_path(tmp_path / "two/warehouses/shop/artifacts/refactor_runs/run-b/verification/plan.json")
    assert first == second
    assert first != other


def test_dry_run_does_not_claim_or_write_database(tmp_path, monkeypatch):
    def fail_if_called(*args, **kwargs):
        raise AssertionError("dry-run must not claim a database")

    monkeypatch.setattr(shadow_run_module, "claim_qa_slot", fail_if_called)
    plan_path = tmp_path / "verification" / "plan.json"
    output_path = tmp_path / "verification" / "shadow_run_result.json"
    _write_shadow_cli_plan(plan_path)
    result = run_shadow_plan(
        plan_path,
        output_path,
        provenance=_provenance(plan_path),
        dry_run=True,
    )
    assert result["mode"] == "dry_run"
    assert result["qa_database_pool"] == ["shop_dm_qa", "shop_dm_qa_02"]


def test_execute_claims_after_preview_and_recompiles_for_actual_slot(
    tmp_path, monkeypatch
):
    plan_path = tmp_path / "verification" / "plan.json"
    output_path = tmp_path / "verification" / "shadow_run_result.json"
    _write_shadow_cli_plan(plan_path)
    owner = QaSlotOwnership(
        2, "shop", "test-run", "execution-1", "shop_dm_qa_02",
        _provenance(plan_path)["plan_fingerprint"],
        _provenance(plan_path)["workspace_fingerprint"],
        "2026-07-14 12:00:00", 1784001600,
    )
    preview_databases = []
    executed_databases = []

    def fake_preview(plan, *args, **kwargs):
        preview_databases.append(plan["qa_db"])
        return {"blockers": [], "warnings": []}, {
            "name": "compile_shadow_manifest",
            "status": "success",
        }

    def fake_execute(plan, **kwargs):
        executed_databases.append(plan["qa_db"])
        return {"status": "completed", "mode": "execute", "phases": []}

    monkeypatch.setattr(shadow_run_module, "_compile_shadow_manifest_phase", fake_preview)
    monkeypatch.setattr(shadow_run_module, "claim_qa_slot", lambda **kwargs: owner)
    monkeypatch.setattr(shadow_run_module, "execute_shadow_plan", fake_execute)
    monkeypatch.setattr(shadow_run_module.uuid, "uuid4", lambda: "execution-1")
    result = run_shadow_plan(
        plan_path,
        output_path,
        provenance=_provenance(plan_path),
    )
    assert preview_databases == ["shop_dm_qa"]
    assert executed_databases == ["shop_dm_qa_02"]
    assert result["qa_db"] == "shop_dm_qa_02"
```

Update existing reset-phase tests to expect `claim_qa_slot`, and assert baseline DDL, prefill, DDL changes, and jobs all reference the actual claimed database.

- [ ] **Step 2: Add a reserved marker reference blocker test**

In `tests/refact/test_shadow_manifest.py`, compile a task that reads or writes `dw_refactor_execution_marker` and assert one blocker names the reserved marker. This protects cleanup ownership from warehouse SQL.

- [ ] **Step 3: Run focused tests and verify failure**

Run:

```bash
make test PYTEST_ARGS='-q -m "not api" tests/refact/test_shadow_run.py tests/refact/test_shadow_manifest.py'
```

Expected: failures show the old project lock, reset phase, post-execution marker publication, and absent marker blocker.

- [ ] **Step 4: Implement run-scoped locking**

Change `_lock_path()` to derive both project and run ID from the concrete `refactor_runs` path and return `Path(tempfile.gettempdir()) / "dw_refactor_agent_locks" / f"{safe_project}.{safe_run_id}.shadow_execution.lock"`. Rename the context manager to `run_execution_lock` and change its error to `another shadow-run or compare is active for this run`.

- [ ] **Step 5: Implement preview/claim/runtime execution**

Refactor `run_shadow_plan()` to:

1. validate the fresh bundle and provenance;
2. dry-run using `plan["qa_db"]` without calling the allocator;
3. preview-compile execute mode with the default QA name and stop on blockers;
4. generate execution ID and call `claim_qa_slot()`;
5. deep-copy the plan, set `runtime_plan["qa_db"]` to the claimed database, and recompile;
6. call `execute_shadow_plan(runtime_plan, root=bundle.root, claimed_ownership=owner, dry_run=False, timing_detail=timing_detail, parallel=parallel, batch_size=batch_size)`;
7. persist actual database and ownership in the result;
8. leave the slot claimed for every return path.

Remove `reset_qa_db` and post-success `publish_execution_marker`. Add a `claim_qa_slot` phase summary. At execute core entry, call `require_slot_ownership()` before creating baseline tables. Add the reserved marker blocker in shadow manifest compilation.

- [ ] **Step 6: Run focused tests and verify pass**

Run the command from Step 3.

Expected: all shadow-run and manifest tests pass with no DROP/CREATE DATABASE SQL.

- [ ] **Step 7: Commit**

```bash
git add src/dw_refactor_agent/refactor/execution_provenance.py src/dw_refactor_agent/refactor/shadow_run.py src/dw_refactor_agent/refactor/shadow_manifest.py tests/refact/test_shadow_run.py tests/refact/test_shadow_manifest.py
git commit -m "feat(refactor): execute shadow plans in claimed QA slots"
```

---

### Task 5: Bind Compare to the Claimed Physical Database

**Files:**
- Modify: `src/dw_refactor_agent/refactor/compare.py`
- Test: `tests/refact/test_compare.py`
- Test: `tests/refact/test_run_cli.py`

**Interfaces:**
- Consumes: shadow result exact `qa_db`, run/execution/fingerprints, `require_slot_ownership()`, and `run_execution_lock()`.
- Produces: compare result behavior unchanged except it reads the physical QA database from the shadow result.

- [ ] **Step 1: Write failing compare tests**

```python
def test_compare_uses_shadow_result_physical_database(tmp_path, monkeypatch):
    plan_path = tmp_path / "verification" / "plan.json"
    shadow_path = tmp_path / "verification" / "shadow_run_result.json"
    output_path = tmp_path / "verification" / "compare_result.json"
    persisted = _write_compare_plan(plan_path, _semantic_verification([]))
    shadow_result = {
        "mode": "execute",
        "status": "completed",
        "run_id": "run-1",
        "execution_id": "execution-1",
        "qa_db": "shop_dm_qa_02",
        "plan_fingerprint": persisted["plan_fingerprint"],
        "workspace_fingerprint": persisted["analysis_snapshot"][
            "workspace_fingerprint"
        ],
    }
    monkeypatch.setattr(compare_module, "require_matching_shadow_result", lambda *args: shadow_result)
    monkeypatch.setattr(compare_module, "require_slot_ownership", lambda **kwargs: None)
    checked_plans = []
    monkeypatch.setattr(
        compare_module,
        "run_checks",
        lambda plan, **kwargs: checked_plans.append(plan) or {
            "verification_status": "passed", "warnings": []
        },
    )
    result = compare_shadow_results(plan_path, shadow_path, output_path)
    assert checked_plans[0]["qa_db"] == "shop_dm_qa_02"
    assert result["shadow_execution_id"] == "execution-1"


def test_compare_rejects_shadow_database_outside_pool_before_connections(
    tmp_path, monkeypatch
):
    plan_path = tmp_path / "verification" / "plan.json"
    shadow_path = tmp_path / "verification" / "shadow_run_result.json"
    output_path = tmp_path / "verification" / "compare_result.json"
    _write_compare_plan(plan_path, _semantic_verification([]))
    shadow_result = {
        "mode": "execute",
        "status": "completed",
        "run_id": "test-run",
        "execution_id": "execution-1",
        "qa_db": "shop_dm",
        "plan_fingerprint": "sha256:" + "a" * 64,
        "workspace_fingerprint": "sha256:" + "b" * 64,
    }
    monkeypatch.setattr(compare_module, "require_matching_shadow_result", lambda *args: shadow_result)
    database_connections = []
    monkeypatch.setattr(
        compare_module,
        "get_pymysql_conn",
        lambda *args, **kwargs: database_connections.append(args) or None,
    )
    with pytest.raises(ArtifactFormatError, match="not in.*pool"):
        compare_shadow_results(plan_path, shadow_path, output_path)
    assert database_connections == []
```

Add ownership mismatch cases for project, run ID, execution ID, database, plan fingerprint, and workspace fingerprint.

- [ ] **Step 2: Run focused tests and verify failure**

Run:

```bash
make test PYTEST_ARGS='-q -m "not api" tests/refact/test_compare.py tests/refact/test_run_cli.py'
```

Expected: compare still connects to persisted `plan["qa_db"]` and uses the old marker selector.

- [ ] **Step 3: Implement exact physical database resolution**

After `require_matching_shadow_result`, read and validate `shadow_result["qa_db"]`, require case-insensitive membership in `plan["qa_database_pool"]`, then call `require_slot_ownership()` with every expected field. Deep-copy the plan, set the canonical configured spelling of the actual slot as `runtime_plan["qa_db"]`, and pass only that runtime plan to `run_checks()`.

Remove marker SQL from `execution_provenance.py` and remove `require_qa_execution_marker()` from compare. Keep marker validation before `run_checks()` opens production and QA connections.

- [ ] **Step 4: Run focused tests and verify pass**

Run the command from Step 2.

Expected: selected compare and CLI tests pass.

- [ ] **Step 5: Commit**

```bash
git add src/dw_refactor_agent/refactor/compare.py src/dw_refactor_agent/refactor/execution_provenance.py tests/refact/test_compare.py tests/refact/test_run_cli.py
git commit -m "feat(refactor): compare exact claimed QA executions"
```

---

### Task 6: Add Manual Pool List and Cleanup Commands

**Files:**
- Modify: `src/dw_refactor_agent/refactor/qa_pool.py`
- Modify: `src/dw_refactor_agent/refactor/run.py`
- Test: `tests/refact/test_qa_pool.py`
- Test: `tests/refact/test_run_cli.py`

**Interfaces:**
- Consumes: pool inspection, selector, and release APIs from Tasks 2–3.
- Produces CLI commands `dw-refactor cleanup list` and `dw-refactor cleanup delete`.
- Produces pure parsers `parse_age(value: str) -> int` and `parse_created_before(value: str) -> int` for cutoff epochs.

- [ ] **Step 1: Write failing CLI parser and behavior tests**

```python
def test_cleanup_list_filters_by_project_and_run(monkeypatch, capsys):
    owner = QaSlotOwnership(
        2, "shop", "run-1", "execution-1", "shop_dm_qa_02",
        "sha256:" + "a" * 64, "sha256:" + "b" * 64,
        "2026-07-14 12:00:00", 1784001600,
    )
    inspections = [
        QaSlotInspection(
            "shop", "shop_dm_qa_02", "claimed", owner, None, ()
        ),
        QaSlotInspection(
            "finance_analytics", "other_run_slot", "free", None, None, ()
        ),
    ]
    monkeypatch.setattr(
        run_cli, "inspect_configured_slots", lambda **kwargs: inspections
    )
    assert run_cli.main(["cleanup", "list", "--project", "shop", "--run", "run-1"]) == 0
    output = capsys.readouterr().out
    assert "shop_dm_qa_02" in output
    assert "other_run_slot" not in output


def test_cleanup_delete_without_yes_is_preview(monkeypatch, capsys):
    owner = QaSlotOwnership(
        2, "shop", "run-1", "execution-1", "shop_dm_qa_02",
        "sha256:" + "a" * 64, "sha256:" + "b" * 64,
        "2026-07-14 12:00:00", 1784001600,
    )
    inspection = QaSlotInspection(
        "shop", "shop_dm_qa_02", "claimed", owner, None, ()
    )
    monkeypatch.setattr(
        run_cli,
        "inspect_configured_slots",
        lambda **kwargs: [inspection],
    )

    def fail_if_called(*args, **kwargs):
        raise AssertionError("preview must not release a slot")

    monkeypatch.setattr(run_cli, "release_qa_slot", fail_if_called)
    assert run_cli.main(["cleanup", "delete", "--execution", "execution-1"]) == 0
    assert "would release" in capsys.readouterr().out


def test_cleanup_delete_rejects_unbounded_yes():
    with pytest.raises(SystemExit, match="selector"):
        run_cli.main(["cleanup", "delete", "--yes"])


def test_time_cleanup_requires_project_or_all_projects():
    with pytest.raises(SystemExit, match="--project.*--all-projects"):
        run_cli.main(["cleanup", "delete", "--older-than", "7d", "--yes"])
```

Cover AND-combined filters, exact database cleanup for legacy/invalid, timezone-required absolute timestamps, invalid age units, partial release failures, and non-zero return when any selected slot is blocked/failed.

- [ ] **Step 2: Run focused tests and verify failure**

Run:

```bash
make test PYTEST_ARGS='-q -m "not api" tests/refact/test_qa_pool.py tests/refact/test_run_cli.py'
```

Expected: argparse rejects the unknown cleanup command and time parser APIs are absent.

- [ ] **Step 3: Implement cleanup argparse tree**

Add `cleanup` with required subcommands. Both subcommands accept `--root` defaulting to `config.PROJECT_ROOT` and use `_project_root_context()` so worktree-local warehouse configuration is authoritative.

`list` accepts `--project` and `--run`. `delete` accepts `--project`, `--all-projects`, `--run`, `--execution`, `--database`, `--older-than`, `--created-before`, and `--yes`. Validate the selector rules before connecting to Doris.

- [ ] **Step 4: Implement stable list/preview/release output**

Print one tabular line per configured pool slot with project, database, availability, run ID, execution ID, claimed time, and age. For delete, print the exact selected set first. Without `--yes`, print `would release` and return 0. With `--yes`, release each target, continue after failures, summarize `released`, `blocked`, and `failed`, and return 1 if blocked/failed is non-empty.

- [ ] **Step 5: Run focused tests and verify pass**

Run the command from Step 2.

Expected: all pool and cleanup CLI tests pass.

- [ ] **Step 6: Commit**

```bash
git add src/dw_refactor_agent/refactor/qa_pool.py src/dw_refactor_agent/refactor/run.py tests/refact/test_qa_pool.py tests/refact/test_run_cli.py
git commit -m "feat(refactor): add manual QA pool cleanup"
```

---

### Task 7: Configure Shop and Update User-Facing Contracts

**Files:**
- Modify: `warehouses/shop/warehouse.yaml`
- Modify: `AGENTS.md`
- Modify: `src/dw_refactor_agent/refactor/AGENTS.md`
- Modify: `tests/test_project_asset_paths.py`
- Modify: `tests/refact/test_run_cli.py`

**Interfaces:**
- Consumes all prior public behavior.
- Produces Shop pool `shop_dm_qa`, `shop_dm_qa_02` and documented cleanup commands.

- [ ] **Step 1: Write failing configuration assertion**

```python
def test_shop_uses_precreated_qa_database_pool():
    assert config.PROJECT_CONFIG["shop"]["verification"]["qa_database_pool"] == [
        "shop_dm_qa",
        "shop_dm_qa_02",
    ]
```

- [ ] **Step 2: Run focused test and verify failure**

Run:

```bash
make test PYTEST_ARGS='-q -m "not api" tests/test_project_asset_paths.py tests/refact/test_run_cli.py'
```

Expected: Shop config lacks `qa_database_pool`.

- [ ] **Step 3: Update Shop configuration and documentation**

Add:

```yaml
verification:
  qa_database_pool:
    - shop_dm_qa
    - shop_dm_qa_02
```

Keep existing week-start and row-compare keys. Document that shadow-run claims a pre-created slot, compare uses the exact shadow result slot, no command automatically releases it, cleanup is operator-controlled, and legacy/invalid slots require exact `--database` selection.

- [ ] **Step 4: Run focused tests and verify pass**

Run the command from Step 2.

Expected: configuration and CLI documentation tests pass.

- [ ] **Step 5: Commit**

```bash
git add warehouses/shop/warehouse.yaml AGENTS.md src/dw_refactor_agent/refactor/AGENTS.md tests/test_project_asset_paths.py tests/refact/test_run_cli.py
git commit -m "docs(refactor): configure and document QA pool"
```

---

### Task 8: Automated Verification, Prod Provisioning, and Real QA Validation

**Files:**
- Verify: all modified source, tests, config, and documentation.
- Create external Doris database: `internal.shop_dm_qa_02` only.
- Create run artifacts under the concrete directory printed by the supported `start` CLI command.

**Interfaces:**
- Consumes the complete feature.
- Produces verified prod grants, one real shadow/compare execution, and a released empty test slot.

- [ ] **Step 1: Run all focused refactor tests**

Run:

```bash
make test PYTEST_ARGS='-q -m "not api" tests/refact/test_qa_pool.py tests/refact/test_shadow_manifest.py tests/refact/test_shadow_run.py tests/refact/test_compare.py tests/refact/test_plan_artifact.py tests/refact/test_verification_plan.py tests/refact/test_run_cli.py tests/test_project_asset_paths.py'
```

Expected: all selected tests pass.

- [ ] **Step 2: Run the complete non-API suite**

Run:

```bash
make test
```

Expected: Ruff check/format pass and the complete `not api` test selection passes.

- [ ] **Step 3: Inspect the target database and grant state with root**

Run read-only queries first:

```bash
mysql -h172.16.0.90 -P19030 -uroot -N -e "SHOW DATABASES LIKE 'shop_dm_qa_02'; SHOW GRANTS FOR 'qa'@'%';"
```

Expected before provisioning: `shop_dm_qa_02` is absent and QA grants name only the current `internal.shop_dm_qa` slot.

- [ ] **Step 4: Create the second database and grant exact database privileges**

Run as root:

```sql
CREATE DATABASE shop_dm_qa_02;
GRANT SELECT_PRIV, LOAD_PRIV, ALTER_PRIV, CREATE_PRIV, DROP_PRIV,
      SHOW_VIEW_PRIV
ON internal.shop_dm_qa_02.* TO 'qa'@'%';
```

Then run `SHOW GRANTS FOR 'qa'@'%'` and require the new exact `internal.shop_dm_qa_02` DatabasePrivs entry with the same privilege set as `shop_dm_qa`. Do not grant catalog/global CREATE or DROP.

- [ ] **Step 5: Verify initial pool discovery**

Run:

```bash
PYTHONPATH=src conda run -n dw-refactor-py37 python -m dw_refactor_agent.refactor.run cleanup list --project shop
```

Expected: `shop_dm_qa` is `legacy` and `shop_dm_qa_02` is `free`.

- [ ] **Step 6: Create and analyze a real no-asset-change Shop run**

Run supported commands and capture the emitted exact manifest path in `MANIFEST_PATH`:

```bash
START_OUTPUT="$(PYTHONPATH=src conda run -n dw-refactor-py37 python -m dw_refactor_agent.refactor.run start --project shop)"
MANIFEST_PATH="$(printf '%s\n' "$START_OUTPUT" | sed -n 's/^Run manifest: //p')"
test -f "$MANIFEST_PATH"
PYTHONPATH=src conda run -n dw-refactor-py37 python -m dw_refactor_agent.refactor.run analyze --manifest "$MANIFEST_PATH"
```

Expected: analyze writes a fresh plan with run ID and both pool members. No production writes occur.

- [ ] **Step 7: Verify dry-run does not claim a slot**

Run shadow-run with `--dry-run`, then `cleanup list --project shop`.

Expected: dry-run succeeds or reports existing plan blockers without writing Doris; `shop_dm_qa_02` remains free.

- [ ] **Step 8: Execute real shadow-run and compare**

Run actual shadow-run and inspect its result before compare:

```bash
PYTHONPATH=src conda run -n dw-refactor-py37 python -m dw_refactor_agent.refactor.run shadow-run --manifest "$MANIFEST_PATH"
PYTHONPATH=src conda run -n dw-refactor-py37 python -m dw_refactor_agent.refactor.run compare --manifest "$MANIFEST_PATH" --method all
```

Expected: shadow-run claims `shop_dm_qa_02`, never emits DROP/CREATE DATABASE, and persists exact marker ownership. Compare connects to `shop_dm_qa_02` and passes provenance validation; an empty-check plan may return the repository's existing inconclusive exit code 2.

- [ ] **Step 9: Preview cleanup and retain the real test execution**

Read execution ID from `shadow_run_result.json`, preview cleanup by exact execution and by age without `--yes`, then verify the marker remains:

```bash
EXECUTION_ID="$(PYTHONPATH=src conda run -n dw-refactor-py37 python -c 'import json, pathlib, sys; manifest=pathlib.Path(sys.argv[1]); result=manifest.parent / "verification" / "shadow_run_result.json"; print(json.loads(result.read_text(encoding="utf-8"))["execution_id"])' "$MANIFEST_PATH")"
PYTHONPATH=src conda run -n dw-refactor-py37 python -m dw_refactor_agent.refactor.run cleanup delete --project shop --execution "$EXECUTION_ID"
PYTHONPATH=src conda run -n dw-refactor-py37 python -m dw_refactor_agent.refactor.run cleanup delete --project shop --older-than 1s
PYTHONPATH=src conda run -n dw-refactor-py37 python -m dw_refactor_agent.refactor.run cleanup list --project shop
```

Expected: both previews select the claimed test slot and change nothing; cleanup list still shows the exact execution as claimed. Leave it for a later explicit manual cleanup rather than releasing it during validation.

- [ ] **Step 10: Commit any verification-driven corrections**

If Steps 1–9 reveal a defect, add a failing regression test, implement the minimal correction, rerun focused and full suites, then commit only those corrections:

```bash
git add src/dw_refactor_agent/refactor/qa_pool.py src/dw_refactor_agent/refactor/shadow_run.py src/dw_refactor_agent/refactor/compare.py src/dw_refactor_agent/refactor/run.py tests/refact/test_qa_pool.py tests/refact/test_shadow_run.py tests/refact/test_compare.py tests/refact/test_run_cli.py
git commit -m "fix(refactor): harden QA pool validation"
```

If no correction is required, do not create an empty commit.

---

### Task 9: Code Review and Final Verification

**Files:**
- Review: every file changed since commit `0fb2ccf5`.

**Interfaces:**
- Consumes the completed implementation and real-validation evidence.
- Produces a review report with findings ordered by severity; fixes are required before completion.

- [ ] **Step 1: Review the full diff and ownership boundaries**

Run:

```bash
git diff 0fb2ccf5...HEAD --check
git diff 0fb2ccf5...HEAD -- src/dw_refactor_agent/refactor src/dw_refactor_agent/config warehouses/shop/warehouse.yaml tests/refact tests/test_project_asset_paths.py AGENTS.md
```

Review for atomic claim races, duplicate-table error classification, identifier injection, accidental non-pool/prod deletion, marker-last cleanup, runtime manifest rebinding, exact compare provenance, legacy handling, and same-run artifact races.

- [ ] **Step 2: Convert every finding into a regression test before fixing**

For each actionable finding, add a test that fails for the reviewed behavior, run the focused Task 8 Step 1 command, apply the smallest fix, and rerun the same command. Do not make speculative refactors unrelated to the feature.

- [ ] **Step 3: Rerun final verification**

Run:

```bash
make test
git status --short --branch
git log --oneline -12
```

Expected: the full non-API suite and Ruff pass; only intentional generated run artifacts, if any, remain untracked and are reported rather than committed.

- [ ] **Step 4: Commit review fixes when present**

```bash
git add src/dw_refactor_agent/refactor/qa_pool.py src/dw_refactor_agent/refactor/shadow_run.py src/dw_refactor_agent/refactor/compare.py src/dw_refactor_agent/refactor/run.py tests/refact/test_qa_pool.py tests/refact/test_shadow_run.py tests/refact/test_compare.py tests/refact/test_run_cli.py
git commit -m "fix(refactor): address QA pool code review"
```

If review has no findings, do not create an empty commit. Report the review scope, automated evidence, prod provisioning, actual claimed slot, compare status, and cleanup result in the final handoff.
