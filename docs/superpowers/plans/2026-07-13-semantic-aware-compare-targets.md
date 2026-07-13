# Semantic-aware Compare Targets Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build semantic-mode-aware refactor verification so equivalent tables are compared directly, changed/unknown tables are validated at downstream boundaries, and every execution is bound to the analyzed workspace and plan.

**Architecture:** Add two focused domain modules: `semantic_mode.py` owns table identity, semantic fingerprints, strict automatic equivalence, propagation, historical-decision reuse, and boundary selection; `workspace_snapshot.py` owns workspace input enumeration and hashing. Existing orchestration remains in `run.py`, while `verification_plan.py` consumes the semantic resolution to select executable jobs and checks. Persisted manifest, plan, shadow result, and compare result all use one explicit format contract, with plan freshness and shadow provenance verified before database access.

**Tech Stack:** Python 3.7, standard-library `dataclasses`/`hashlib`/`json`/`subprocess`, PyYAML, sqlglot Doris dialect, pytest 7, Ruff 0.12, Doris/MySQL shadow environment.

## Global Constraints

- Use `semantic_mode` values exactly `equivalent`, `changed`, and `unknown`; automatic rules may emit only `equivalent` or `null`.
- User declarations require no reason and override upstream propagation and automatic detection.
- Unknown semantics continue with downstream observational checks and a top-level warning; they do not silently pass as equivalent.
- An equivalent table is a required direct Compare boundary; unchanged downstream jobs are not selected unless independently changed or required by another changed/unknown path.
- Manifest stores only user intent; plan stores resolved semantics and `analysis_snapshot`.
- Manifest, plan, shadow result, and compare result require `format_version=1`; do not add compatibility branches for old artifacts.
- Do not create a project-level semantic-decision cache; cross-run reuse scans historical run manifests.
- Fingerprints use canonical content hashes, never mtime, run ID, or base commit text.
- Freshness/provenance checks must finish before any database connection, query, QA reset, or DDL execution.
- Use the repository's `dw-refactor-py37` environment and `make doctor` / `make test`; do not invoke bare `pytest`.
- Preserve unrelated user changes and restore all temporary shop acceptance edits before completion.

---

## File Structure

- Create `src/dw_refactor_agent/refactor/artifact_contract.py`: shared format version, canonical JSON hashing, atomic JSON writes, and explicit artifact-format errors.
- Create `src/dw_refactor_agent/refactor/workspace_snapshot.py`: enumerate relevant project/tool inputs and calculate stable workspace fingerprints.
- Create `src/dw_refactor_agent/refactor/semantic_mode.py`: semantic asset snapshots, stable identities, automatic equivalence, context fingerprints, declaration resolution, DAG propagation, and boundary selection.
- Modify `src/dw_refactor_agent/refactor/session.py`: versioned/atomic manifests, historical manifest discovery, and run-ID resolution.
- Modify `src/dw_refactor_agent/refactor/plan_artifact.py`: versioned plans, external DDL refs, self-excluding plan fingerprint, and freshness validation.
- Modify `src/dw_refactor_agent/refactor/verification_plan.py`: consume semantic resolution, select minimal jobs/anchors, create rename-aware checks, and validate check-to-semantics invariants.
- Modify `src/dw_refactor_agent/refactor/run.py`: analyze/replan orchestration, `semantic-mode set`, `--run`, and stage preflight checks.
- Modify `src/dw_refactor_agent/refactor/shadow_run.py`: persist format/fingerprint provenance for dry-run, completed, and failed executions.
- Modify `src/dw_refactor_agent/refactor/compare.py`: require matching shadow provenance, support prod/QA rename projections, and emit the five-state verification result.
- Modify `pyproject.toml`: register `dw-refactor`.
- Modify `src/dw_refactor_agent/refactor/AGENTS.md`: document new commands, fields, warnings, status codes, and stale-plan behavior.
- Create focused tests in `tests/refact/test_artifact_contract.py`, `test_workspace_snapshot.py`, and `test_semantic_mode.py`; extend existing plan/session/CLI/shadow/compare tests.
- Create `docs/superpowers/reviews/2026-07-13-semantic-aware-compare-targets-review.md`: persistent-file review evidence and shop acceptance record.

---

### Task 1: Versioned and Atomic Artifact Foundation

**Files:**
- Create: `src/dw_refactor_agent/refactor/artifact_contract.py`
- Modify: `src/dw_refactor_agent/refactor/session.py`
- Modify: `src/dw_refactor_agent/refactor/plan_artifact.py`
- Test: `tests/refact/test_artifact_contract.py`
- Test: `tests/refact/test_session.py`
- Test: `tests/refact/test_plan_artifact.py`

**Interfaces:**
- Produces: `FORMAT_VERSION: int`, `ArtifactFormatError`, `canonical_json_bytes(value) -> bytes`, `sha256_json(value) -> str`, `atomic_write_json(path, value) -> None`, and `require_format_version(value, artifact_name) -> None`.
- Produces: `load_persisted_verification_plan(plan_path) -> dict`, `calculate_plan_fingerprint(persisted_plan) -> str`, and `validate_plan_fingerprint(persisted_plan) -> None`.
- Consumers: all later manifest, plan, shadow, and compare persistence.

- [ ] **Step 1: Write failing contract and persistence tests**

```python
def test_atomic_write_json_replaces_complete_document(tmp_path):
    path = tmp_path / "manifest.json"
    atomic_write_json(path, {"format_version": 1, "value": "old"})
    atomic_write_json(path, {"format_version": 1, "value": "new"})
    assert json.loads(path.read_text(encoding="utf-8")) == {
        "format_version": 1,
        "value": "new",
    }
    assert list(tmp_path.glob(".manifest.json.*.tmp")) == []


def test_load_manifest_rejects_missing_or_wrong_format_version(tmp_path):
    path = tmp_path / "manifest.json"
    path.write_text('{"project": "shop"}', encoding="utf-8")
    with pytest.raises(ArtifactFormatError, match="manifest.*format_version"):
        load_manifest(path)


def test_plan_fingerprint_excludes_its_own_field_and_detects_edit(tmp_path):
    path = tmp_path / "verification" / "plan.json"
    persisted = write_verification_plan(path, _plan({}))
    assert persisted["format_version"] == 1
    assert persisted["plan_fingerprint"] == calculate_plan_fingerprint(
        persisted
    )
    persisted["qa_db"] = "tampered"
    path.write_text(json.dumps(persisted), encoding="utf-8")
    with pytest.raises(ArtifactFormatError, match="plan_fingerprint"):
        load_persisted_verification_plan(path)
```

- [ ] **Step 2: Run focused tests and confirm the new contract is absent**

Run: `make test PYTEST_ARGS='tests/refact/test_artifact_contract.py tests/refact/test_session.py tests/refact/test_plan_artifact.py -q'`

Expected: FAIL because `artifact_contract` and plan fingerprint APIs do not exist and current manifests have no required format version.

- [ ] **Step 3: Implement the shared contract and atomic manifest writes**

```python
FORMAT_VERSION = 1


class ArtifactFormatError(ValueError):
    """Raised when a persisted refactor artifact violates its contract."""


def canonical_json_bytes(value) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode(TEXT_ENCODING)


def sha256_json(value) -> str:
    return "sha256:" + hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def atomic_write_json(path: Path, value: dict) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{target.name}.", suffix=".tmp", dir=str(target.parent)
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding=TEXT_ENCODING) as handle:
            json.dump(value, handle, ensure_ascii=False, indent=2)
            handle.flush()
            os.fsync(handle.fileno())
        temporary.replace(target)
    except BaseException:
        if temporary.exists():
            temporary.unlink()
        raise


def require_format_version(value: dict, artifact_name: str) -> None:
    actual = value.get("format_version")
    if actual != FORMAT_VERSION:
        raise ArtifactFormatError(
            f"{artifact_name} format_version must be {FORMAT_VERSION}; "
            f"received {actual!r}; create a new refactor run"
        )
```

`create_run_manifest()` writes `format_version=1`; `load_manifest()` validates before returning; `write_manifest()` delegates to `atomic_write_json()` while preserving every unknown manifest field supplied by the caller.

- [ ] **Step 4: Add plan fingerprinting after external DDL refs are written**

```python
def calculate_plan_fingerprint(persisted_plan: dict) -> str:
    canonical_plan = deepcopy(persisted_plan)
    canonical_plan.pop("plan_fingerprint", None)
    return sha256_json(canonical_plan)


def validate_plan_fingerprint(persisted_plan: dict) -> None:
    expected = persisted_plan.get("plan_fingerprint")
    actual = calculate_plan_fingerprint(persisted_plan)
    if expected != actual:
        raise ArtifactFormatError(
            "verification plan plan_fingerprint mismatch; run analyze again"
        )
```

`write_verification_plan()` adds `format_version=1`, adds `baseline_ddl_refs`, calculates `plan_fingerprint` with that field omitted, then atomically writes the plan. `load_persisted_verification_plan()` validates version, plan fingerprint, safe ref paths, and referenced bytes before returning the persisted form; `load_verification_plan()` calls it and adds in-memory `baseline_ddl` without changing the fingerprint input.

- [ ] **Step 5: Run focused tests and commit**

Run: `make test PYTEST_ARGS='tests/refact/test_artifact_contract.py tests/refact/test_session.py tests/refact/test_plan_artifact.py -q'`

Expected: PASS.

```bash
git add src/dw_refactor_agent/refactor/artifact_contract.py src/dw_refactor_agent/refactor/session.py src/dw_refactor_agent/refactor/plan_artifact.py tests/refact/test_artifact_contract.py tests/refact/test_session.py tests/refact/test_plan_artifact.py
git commit -m "feat(refactor): version persisted run artifacts"
```

### Task 2: Workspace Snapshot and Freshness Input Coverage

**Files:**
- Create: `src/dw_refactor_agent/refactor/workspace_snapshot.py`
- Test: `tests/refact/test_workspace_snapshot.py`

**Interfaces:**
- Produces: `workspace_file_entries(root: Path, project: str) -> list[dict]` and `workspace_fingerprint(root: Path, project: str) -> str`.
- Consumes: configured DDL/task/model paths and the tool source directories listed in the approved specification.
- Consumers: analyze, semantic-mode replan, shadow-run, and compare preflight.

- [ ] **Step 1: Write table-driven coverage and stability tests**

```python
@pytest.mark.parametrize(
    "relative_path",
    [
        "warehouses/shop/mid/ddl/dws_sales.sql",
        "warehouses/shop/mid/tasks/dws_sales.sql",
        "warehouses/shop/mid/tasks/full_refresh/dws_sales.sql",
        "warehouses/shop/mid/models/dws_sales.yaml",
        "warehouses/shop/warehouse.yaml",
        "warehouses/shop/business_processes.yaml",
        "naming_config.yaml",
        "src/dw_refactor_agent/refactor/run.py",
        "src/dw_refactor_agent/lineage/asset_graph.py",
        "src/dw_refactor_agent/ddl_deriver/ddl_deriver.py",
        "src/dw_refactor_agent/execution/model_config.py",
        "src/dw_refactor_agent/config/assets.py",
        "src/dw_refactor_agent/sql/doris.py",
    ],
)
def test_relevant_file_content_changes_workspace_fingerprint(
    configured_root, relative_path
):
    before = workspace_fingerprint(configured_root, "shop")
    path = configured_root / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("changed", encoding="utf-8")
    assert workspace_fingerprint(configured_root, "shop") != before


def test_artifacts_docs_tests_and_other_project_do_not_change_fingerprint(
    configured_root,
):
    before = workspace_fingerprint(configured_root, "shop")
    for relative_path in (
        "warehouses/shop/artifacts/refactor_runs/x/plan.json",
        "docs/notes.md",
        "tests/test_notes.py",
        "warehouses/finance_analytics/mid/tasks/dws_sales.sql",
    ):
        path = configured_root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("ignored", encoding="utf-8")
    assert workspace_fingerprint(configured_root, "shop") == before
```

- [ ] **Step 2: Run the focused test and verify failure**

Run: `make test PYTEST_ARGS='tests/refact/test_workspace_snapshot.py -q'`

Expected: FAIL because snapshot enumeration is not implemented.

- [ ] **Step 3: Implement canonical path/content entries**

```python
TOOL_SOURCE_DIRECTORIES = (
    "src/dw_refactor_agent/refactor",
    "src/dw_refactor_agent/lineage",
    "src/dw_refactor_agent/ddl_deriver",
    "src/dw_refactor_agent/execution",
    "src/dw_refactor_agent/config",
    "src/dw_refactor_agent/sql",
)


def _entry(root: Path, path: Path) -> dict:
    content = path.read_bytes()
    return {
        "path": path.resolve().relative_to(root.resolve()).as_posix(),
        "content_sha256": "sha256:" + hashlib.sha256(content).hexdigest(),
    }


def workspace_fingerprint(root: Path, project: str) -> str:
    return sha256_json(
        {
            "fingerprint_version": 1,
            "project": project,
            "files": workspace_file_entries(root, project),
        }
    )
```

`workspace_file_entries()` unions configured project DDL, normal/full-refresh tasks, YAML models, warehouse/naming/business-semantics config, and `*.py` under `TOOL_SOURCE_DIRECTORIES`; it keeps only existing regular files, resolves paths under `root`, de-duplicates by relative path, and returns path-sorted entries. Add/delete/rename changes the entry set; mtimes never enter the hash.

- [ ] **Step 4: Run focused tests and commit**

Run: `make test PYTEST_ARGS='tests/refact/test_workspace_snapshot.py -q'`

Expected: PASS.

```bash
git add src/dw_refactor_agent/refactor/workspace_snapshot.py tests/refact/test_workspace_snapshot.py
git commit -m "feat(refactor): fingerprint analyzed workspace inputs"
```

### Task 3: Semantic Identity, Fingerprints, and Resolution

**Files:**
- Create: `src/dw_refactor_agent/refactor/semantic_mode.py`
- Test: `tests/refact/test_semantic_mode.py`

**Interfaces:**
- Produces: `SemanticResolution` dataclass with `target_semantics`, `boundaries`, `selected_tables`, `warnings`, and `inherited_declarations`.
- Produces: `resolve_semantic_modes(project, change_analysis, baseline_lineage, current_lineage, base_ref, repo_root, ddl_changes, current_manifest, historical_manifests) -> SemanticResolution`.
- Consumers: `run.py` and `verification_plan.py`.

- [ ] **Step 1: Write resolver priority, propagation, and fingerprint tests**

```python
def test_user_mode_overrides_upstream_risk(semantic_case):
    case = semantic_case(upstream_mode="changed")
    case.manifest["verification_intent"] = {
        "semantic_modes": {
            "dws_sales": {
                "mode": "equivalent",
                "semantic_context_fingerprint": case.context_for("dws_sales"),
                "confirmed_at": "2026-07-13T15:30:00+08:00",
            }
        }
    }
    result = case.resolve()
    assert result.target_semantics["dws_sales"]["resolved_mode"] == (
        "equivalent"
    )
    assert result.target_semantics["dws_sales"]["resolved_source"] == "user"


def test_unknown_propagates_until_nearest_equivalent_boundary(semantic_case):
    result = semantic_case(
        graph=[("dwd_order", "dws_sales"), ("dws_sales", "ads_sales")],
        direct_change="dwd_order",
        declared={"ads_sales": "equivalent"},
    ).resolve()
    assert result.target_semantics["dwd_order"]["resolved_mode"] == "unknown"
    assert result.target_semantics["dws_sales"]["resolved_source"] == (
        "upstream_propagation"
    )
    assert result.boundaries == {
        "authority": ["ads_sales"],
        "observational": [],
    }


def test_semantic_context_changes_when_affected_ancestor_changes(semantic_case):
    first = semantic_case(task_sql="SELECT amount FROM ods_order").resolve()
    second = semantic_case(
        task_sql="SELECT amount * 2 AS amount FROM ods_order"
    ).resolve()
    assert (
        first.target_semantics["dws_sales"]["semantic_context_fingerprint"]
        != second.target_semantics["dws_sales"]["semantic_context_fingerprint"]
    )
```

Add table-driven cases for all precedence branches, self-read edge exclusion, stable ordering, unrelated-branch stability, stale current declarations, exact historical reuse, corrupt/wrong-version history diagnostics, and `changed` never being automatic.

- [ ] **Step 2: Write strict automatic-equivalence tests**

```python
@pytest.mark.parametrize(
    "baseline_sql,current_sql,expected",
    [
        ("SELECT id FROM ods_order", "-- note\nSELECT  id  FROM ods_order", True),
        ("SELECT id FROM ods_order", "SELECT id FROM ods_order WHERE id > 0", False),
        ("SELECT * FROM ods_order", "SELECT id FROM ods_order", False),
        ("SELECT id FROM a JOIN b ON a.id=b.id", "SELECT id FROM a LEFT JOIN b ON a.id=b.id", False),
        ("SELECT id, SUM(v) FROM a GROUP BY id", "SELECT id, MAX(v) FROM a GROUP BY id", False),
    ],
)
def test_automatic_sql_equivalence_is_strict(
    baseline_sql, current_sql, expected
):
    assert sql_ast_equivalent(baseline_sql, current_sql, rename_mapping={}) is expected
```

Add a managed table/column rename case whose DDL changes contain only a table rename and column renames with matching stable IDs, whose YAML differs only in renamed references, and whose SQL AST matches after identifier rewriting; assert automatic equivalent and a complete `column_mapping`. Add negative cases for missing IDs, add/drop/modify columns, changed grain/metrics/business process/execution, or any non-rename SQL expression difference.

- [ ] **Step 3: Run the focused test and verify failure**

Run: `make test PYTEST_ARGS='tests/refact/test_semantic_mode.py -q'`

Expected: FAIL because semantic resolution does not exist.

- [ ] **Step 4: Implement typed resolution records and canonical fingerprints**

```python
VALID_SEMANTIC_MODES = frozenset(("equivalent", "changed", "unknown"))


@dataclass(frozen=True)
class SemanticResolution:
    target_semantics: dict
    boundaries: dict
    selected_tables: tuple
    warnings: tuple
    inherited_declarations: dict
    diagnostics: tuple


def _context_fingerprint(local_fingerprint: str, upstream_records: list) -> str:
    return sha256_json(
        {
            "fingerprint_version": 1,
            "local_change_fingerprint": local_fingerprint,
            "affected_upstreams": sorted(
                upstream_records,
                key=lambda item: (
                    item["upstream_table_id"],
                    item["upstream_semantic_context_fingerprint"],
                    item["upstream_resolved_mode"],
                ),
            ),
        }
    )
```

Build baseline/current asset snapshots from raw Git bytes and current bytes for DDL, normal task, full-refresh task, and model. Match renamed tables by normalized `table_id`; represent missing assets as `null`; calculate `local_change_fingerprint` from the exact schema in the approved specification. Parse the union of baseline/current asset-table edges, remove self-edges, restrict it to affected tables, and topologically sort; a cycle raises a user-facing `ValueError`.

- [ ] **Step 5: Implement resolution priority and boundary traversal**

```python
def _resolved_mode(declaration, risky_upstreams, automatic_mode):
    if declaration is not None:
        return declaration["mode"], declaration["source"]
    if risky_upstreams:
        return "unknown", "upstream_propagation"
    if automatic_mode == "equivalent":
        return "equivalent", "automatic"
    return "unknown", "default_unknown"
```

For each table in topological order, validate the current declaration against its computed context fingerprint, otherwise search history newest-first for exact `table_id + context fingerprint + valid mode`. Emit one top-level stale-declaration warning without deleting the manifest entry. Then traverse every changed/unknown path to the nearest equivalent descendant; if none exists, choose structurally comparable leaves as observational boundaries. Equivalent direct tables select themselves and stop; independently changed descendants and descendants with a valid explicit user declaration remain independent seeds. Each unknown table produces exactly one `unknown_table_semantics` warning.

- [ ] **Step 6: Run focused tests and commit**

Run: `make test PYTEST_ARGS='tests/refact/test_semantic_mode.py -q'`

Expected: PASS.

```bash
git add src/dw_refactor_agent/refactor/semantic_mode.py tests/refact/test_semantic_mode.py
git commit -m "feat(refactor): resolve table semantic modes"
```

### Task 4: Semantic-aware Verification Plan and Rename Checks

**Files:**
- Modify: `src/dw_refactor_agent/refactor/verification_plan.py`
- Modify: `tests/refact/test_verification_plan.py`

**Interfaces:**
- Consumes: `SemanticResolution` from Task 3.
- Produces: plan `verification.target_semantics`, top-level `verification.warnings`, minimal `jobs_to_run`, and checks containing optional `prod_table`, `qa_table`, and `column_mapping`.

- [ ] **Step 1: Write direct-equivalent and downstream-boundary tests**

```python
def test_equivalent_direct_table_is_compared_without_unchanged_downstream(
    semantic_plan_case,
):
    plan = semantic_plan_case(
        graph=[
            ("dws_store_sales_daily", "ads_store_performance"),
            ("dws_store_sales_daily", "dim_store_metric_snapshot"),
        ],
        direct={"dws_store_sales_daily": "equivalent"},
    ).build()
    assert [job["job"] for job in plan["jobs_to_run"]] == [
        "dws_store_sales_daily"
    ]
    assert plan["verification"]["anchor_tables"] == [
        "dws_store_sales_daily"
    ]
    assert {
        check["table"] for check in plan["verification"]["checks"]
    } == {"dws_store_sales_daily"}


def test_unknown_direct_table_runs_path_to_observational_leaf(
    semantic_plan_case,
):
    plan = semantic_plan_case(
        graph=[("dwd_order", "dws_sales"), ("dws_sales", "ads_sales")],
        direct={"dwd_order": "unknown"},
    ).build()
    assert [job["job"] for job in plan["jobs_to_run"]] == [
        "dwd_order",
        "dws_sales",
        "ads_sales",
    ]
    assert plan["verification"]["anchor_tables"] == ["ads_sales"]
    assert plan["verification"]["warnings"][0]["type"] == (
        "unknown_table_semantics"
    )
```

Add cases for changed-to-nearest-equivalent, an independently changed descendant below an equivalent boundary, a user-declared affected descendant explicitly selected below an equivalent boundary, rename reference propagation, missing required compare metadata causing `blocked`, and the invariant that every check table exists in `target_semantics`.

- [ ] **Step 2: Write rename check contract tests**

```python
def test_pure_rename_check_maps_prod_and_qa_by_stable_column_id(
    semantic_plan_case,
):
    plan = semantic_plan_case(pure_rename=True).build()
    row_check = next(
        check
        for check in plan["verification"]["checks"]
        if check["method"] == "row_compare"
    )
    assert row_check == {
        "table": "DIM_BASE_STORE_PROFILE_INFO",
        "prod_table": "dwd_store",
        "qa_table": "DIM_BASE_STORE_PROFILE_INFO",
        "method": "row_compare",
        "column_mapping": [
            {
                "column_id": "89316282-1115-42d8-b953-5c41134e7829",
                "prod": "store_name",
                "qa": "STORE_NAME",
            }
        ],
    }
```

- [ ] **Step 3: Run the focused test and verify failure**

Run: `make test PYTEST_ARGS='tests/refact/test_verification_plan.py -q'`

Expected: FAIL on the new semantic target assertions.

- [ ] **Step 4: Replace scope-equals-execution with semantic selection**

```python
selected_tables = set(semantic_resolution.selected_tables)
job_entries = {}
for job_name in selected_tables:
    entry = _job_entry(project, job_name)
    if entry:
        job_entries[job_name] = entry

authority = semantic_resolution.boundaries["authority"]
observational = semantic_resolution.boundaries["observational"]
anchors = sorted(set(authority) | set(observational))
```

Build execution values only after this selection. Generate count and row checks from semantic boundary metadata. For renamed equivalent tables, preserve the logical current `table`, add distinct production/QA names, and attach the stable-ID projection. Before returning, validate that changed tables have no direct check, equivalent direct tables have both required methods, and every check resolves to a `target_semantics` record; validation failure marks verification blocked with a structured reason.

- [ ] **Step 5: Run focused tests and commit**

Run: `make test PYTEST_ARGS='tests/refact/test_verification_plan.py -q'`

Expected: PASS.

```bash
git add src/dw_refactor_agent/refactor/verification_plan.py tests/refact/test_verification_plan.py
git commit -m "feat(refactor): route verification by semantic boundary"
```

### Task 5: Manifest Intent, Historical Reuse, Short CLI, and Lightweight Replan

**Files:**
- Modify: `src/dw_refactor_agent/refactor/session.py`
- Modify: `src/dw_refactor_agent/refactor/run.py`
- Modify: `pyproject.toml`
- Modify: `tests/refact/test_session.py`
- Modify: `tests/refact/test_run_cli.py`

**Interfaces:**
- Produces: `resolve_manifest_path(manifest, run_id, root) -> Path`, `historical_manifests(manifest_path, manifest) -> list[tuple[Path, dict]]`, and the `semantic-mode set` command.
- Consumes: Tasks 1–4 artifact and semantic APIs.

- [ ] **Step 1: Write run resolution and declaration persistence tests**

```python
def test_resolve_run_id_requires_exact_unique_match(configured_root):
    first = create_manifest(configured_root, "shop", "20260713_113226_shop")
    assert resolve_manifest_path(None, "20260713_113226_shop", configured_root) == first
    create_manifest(
        configured_root, "finance_analytics", "20260713_113226_shop"
    )
    with pytest.raises(SystemExit, match="multiple.*--manifest"):
        resolve_manifest_path(None, "20260713_113226_shop", configured_root)


def test_semantic_mode_set_preserves_manifest_and_lightly_replans(
    analyzed_run, monkeypatch
):
    before = json.loads(analyzed_run.manifest_path.read_text())
    calls = install_replan_spies(monkeypatch)
    assert run_cli.main(
        [
            "semantic-mode",
            "set",
            "--manifest",
            str(analyzed_run.manifest_path),
            "--table",
            "dws_store_sales_daily",
            "--mode",
            "equivalent",
        ]
    ) == 0
    after = json.loads(analyzed_run.manifest_path.read_text())
    assert after["artifacts"] == before["artifacts"]
    assert after["base_git"] == before["base_git"]
    assert after["root"] == before["root"]
    assert after["verification_intent"]["semantic_modes"][
        "dws_store_sales_daily"
    ]["mode"] == "equivalent"
    assert calls == {"lineage": 0, "assessment": 0, "plan": 1}
```

Add tests for invalid mode, unknown/unaffected table, mutually exclusive `--run`/`--manifest`, zero matches, inherited historical declaration copied with `inherited_from_run_id`, stale history not reused, and corrupt current manifest never overwritten.

- [ ] **Step 2: Run focused tests and verify failure**

Run: `make test PYTEST_ARGS='tests/refact/test_session.py tests/refact/test_run_cli.py -q'`

Expected: FAIL because short-run resolution and semantic-mode commands are absent.

- [ ] **Step 3: Implement manifest selection and neutral CLI**

```python
def _add_manifest_selector(parser):
    selector = parser.add_mutually_exclusive_group(required=True)
    selector.add_argument("--manifest")
    selector.add_argument("--run")


def _semantic_mode_set(args) -> int:
    manifest_path = _manifest_path_from_args(args)
    manifest = load_manifest(manifest_path)
    persisted_plan = require_fresh_plan(
        artifact_path(manifest_path, "verification_plan"),
        root=_root_from_manifest(manifest, manifest_path),
        project=manifest["project"],
    )
    semantics = persisted_plan["verification"]["target_semantics"]
    if args.table not in semantics:
        raise SystemExit(f"table is not in affected semantic scope: {args.table}")
    declaration = {
        "table_id": semantics[args.table]["table_id"],
        "mode": args.mode,
        "semantic_context_fingerprint": semantics[args.table][
            "semantic_context_fingerprint"
        ],
        "confirmed_at": _now().isoformat(),
    }
    updated = deepcopy(manifest)
    intent = updated.setdefault("verification_intent", {})
    intent.setdefault("semantic_modes", {})[args.table] = declaration
    write_manifest(manifest_path, updated)
    _replan(manifest_path, updated, persisted_plan["analysis_snapshot"]["partition"])
    return 0
```

Use the same selector on analyze/shadow-run/compare. `resolve_manifest_path()` searches every configured standard `refactor_runs_dir`, never chooses latest, and reports all collisions. `_replan()` reads saved baseline/current lineage and change analysis, rebuilds only semantic resolution/plan/baseline DDL refs, and does not call lineage or assessment. During analyze/replan, merge exact inherited declarations into a deep copy of current intent and atomically persist without dropping unknown fields.

- [ ] **Step 4: Register the executable and run focused tests**

```toml
[project.scripts]
dw-refactor = "dw_refactor_agent.refactor.run:main"
```

Run: `make test PYTEST_ARGS='tests/refact/test_session.py tests/refact/test_run_cli.py -q'`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/dw_refactor_agent/refactor/session.py src/dw_refactor_agent/refactor/run.py pyproject.toml tests/refact/test_session.py tests/refact/test_run_cli.py
git commit -m "feat(refactor): persist semantic verification intent"
```

### Task 6: Plan Freshness and Shadow Execution Provenance

**Files:**
- Modify: `src/dw_refactor_agent/refactor/plan_artifact.py`
- Modify: `src/dw_refactor_agent/refactor/run.py`
- Modify: `src/dw_refactor_agent/refactor/shadow_run.py`
- Modify: `tests/refact/test_plan_artifact.py`
- Modify: `tests/refact/test_run_cli.py`
- Modify: `tests/refact/test_shadow_run.py`

**Interfaces:**
- Produces: `require_fresh_plan(plan_path, root, project) -> dict` and shadow result fields `format_version`, `workspace_fingerprint`, and `plan_fingerprint`.
- Consumers: semantic-mode set, shadow-run, and compare.

- [ ] **Step 1: Write stale-before-database and provenance tests**

```python
def test_shadow_run_rejects_changed_workspace_before_handler(
    analyzed_run, monkeypatch
):
    called = False
    monkeypatch.setattr(run_cli, "run_shadow_plan", lambda *args, **kwargs: called)
    analyzed_run.task_path.write_text("SELECT changed", encoding="utf-8")
    with pytest.raises(SystemExit, match="stale_plan.*analyze"):
        run_cli.main(
            ["shadow-run", "--manifest", str(analyzed_run.manifest_path)]
        )
    assert called is False


def test_execute_shadow_result_binds_workspace_and_plan(
    executable_plan, tmp_path
):
    result = run_shadow_plan(
        executable_plan.path,
        tmp_path / "shadow_run_result.json",
        provenance={
            "workspace_fingerprint": "sha256:workspace",
            "plan_fingerprint": "sha256:plan",
        },
    )
    assert result["format_version"] == 1
    assert result["mode"] == "execute"
    assert result["status"] == "completed"
    assert result["workspace_fingerprint"] == "sha256:workspace"
    assert result["plan_fingerprint"] == "sha256:plan"
```

Add tests that stale DDL/model/config/tool source is rejected; a changed plan body/ref is rejected; failed and dry-run results retain provenance but cannot qualify for compare; and freshness errors occur before `run_sql`, `run_sql_text`, or connection helpers.

- [ ] **Step 2: Run focused tests and verify failure**

Run: `make test PYTEST_ARGS='tests/refact/test_plan_artifact.py tests/refact/test_run_cli.py tests/refact/test_shadow_run.py -q'`

Expected: FAIL on freshness/provenance assertions.

- [ ] **Step 3: Save analysis snapshot and enforce preflight**

```python
def require_fresh_plan(plan_path: Path, *, root: Path, project: str) -> dict:
    persisted = load_persisted_verification_plan(plan_path)
    snapshot = persisted.get("analysis_snapshot")
    if not isinstance(snapshot, dict):
        raise ArtifactFormatError("verification plan analysis_snapshot is required")
    expected = snapshot.get("workspace_fingerprint")
    actual = workspace_fingerprint(root, project)
    if expected != actual:
        raise StalePlanError(
            "stale_plan: workspace changed after analyze; run analyze again"
        )
    return persisted
```

Analyze calculates the workspace fingerprint only after lineage/change analysis inputs are finalized and adds `analysis_snapshot = {partition, workspace_fingerprint}` before writing the plan. `semantic-mode set`, shadow-run, and compare call `require_fresh_plan()` before their handler; the shadow handler receives the two fingerprints as explicit provenance.

- [ ] **Step 4: Persist provenance in every shadow terminal result**

```python
def _with_provenance(result: dict, provenance: dict) -> dict:
    enriched = dict(result)
    enriched["format_version"] = FORMAT_VERSION
    enriched["workspace_fingerprint"] = provenance["workspace_fingerprint"]
    enriched["plan_fingerprint"] = provenance["plan_fingerprint"]
    return enriched
```

Apply this exactly once before writing dry-run, completed, or failed results, and write the enriched result with `atomic_write_json()`. Do not infer fingerprints inside `shadow_run.py`; `run.py` passes values from the already validated persisted plan.

- [ ] **Step 5: Run focused tests and commit**

Run: `make test PYTEST_ARGS='tests/refact/test_plan_artifact.py tests/refact/test_run_cli.py tests/refact/test_shadow_run.py -q'`

Expected: PASS.

```bash
git add src/dw_refactor_agent/refactor/plan_artifact.py src/dw_refactor_agent/refactor/run.py src/dw_refactor_agent/refactor/shadow_run.py tests/refact/test_plan_artifact.py tests/refact/test_run_cli.py tests/refact/test_shadow_run.py
git commit -m "feat(refactor): bind shadow execution to analyzed plan"
```

### Task 7: Provenance-gated Compare, Rename Projections, and Final Status

**Files:**
- Modify: `src/dw_refactor_agent/refactor/compare.py`
- Modify: `src/dw_refactor_agent/refactor/run.py`
- Modify: `tests/refact/test_compare.py`
- Modify: `tests/refact/test_run_cli.py`

**Interfaces:**
- Consumes: fresh persisted plan plus matching `shadow_run_result.json`; `compare_shadow_results(plan_path, shadow_result_path, output_path, ...)` requires both artifacts.
- Produces: format-versioned compare result with `verification_status`, `warnings`, and `results`; exit codes 0/1/2.

- [ ] **Step 1: Write shadow provenance gate tests**

```python
@pytest.mark.parametrize(
    "shadow_patch,error",
    [
        ({"mode": "dry-run"}, "stale_shadow_result"),
        ({"status": "failed"}, "stale_shadow_result"),
        ({"plan_fingerprint": "sha256:other"}, "stale_shadow_result"),
        ({"workspace_fingerprint": "sha256:other"}, "stale_shadow_result"),
    ],
)
def test_compare_rejects_unqualified_shadow_before_connect(
    analyzed_run, shadow_patch, error, monkeypatch
):
    analyzed_run.patch_shadow_result(shadow_patch)
    monkeypatch.setattr(
        compare_module,
        "get_pymysql_conn",
        lambda *args, **kwargs: pytest.fail("database connection attempted"),
    )
    with pytest.raises(SystemExit, match=error):
        run_cli.main(
            ["compare", "--manifest", str(analyzed_run.manifest_path)]
        )
```

- [ ] **Step 2: Write status aggregation and rename SQL tests**

```python
@pytest.mark.parametrize(
    "modes,matches,warnings,expected",
    [
        (["equivalent"], [True], [], "passed"),
        (["equivalent", "unknown"], [True, True], [{}], "passed_with_warnings"),
        (["equivalent"], [False], [], "failed"),
        (["unknown"], [False], [{}], "inconclusive"),
        ([], [], [], "inconclusive"),
    ],
)
def test_compare_status_uses_target_semantics(
    modes, matches, warnings, expected
):
    assert aggregate_verification_status(modes, matches, warnings) == expected


def test_row_compare_uses_distinct_prod_qa_projection_for_rename():
    check = {
        "table": "new_store",
        "prod_table": "old_store",
        "qa_table": "new_store",
        "method": "row_compare",
        "column_mapping": [
            {"column_id": "id-1", "prod": "store_name", "qa": "STORE_NAME"}
        ],
    }
    result = check_row_compare(prod_conn, qa_conn, check, 0, 0.01)
    assert result["match"] is True
    assert prod_cursor.executed[-1].startswith("SELECT store_name FROM old_store")
    assert qa_cursor.executed[-1].startswith("SELECT STORE_NAME FROM new_store")
```

Add blocked metadata, observational mismatch, warnings copied exactly once, count using distinct tables, exclusions mapped from QA to prod, and CLI exit code assertions.

- [ ] **Step 3: Run focused tests and verify failure**

Run: `make test PYTEST_ARGS='tests/refact/test_compare.py tests/refact/test_run_cli.py -q'`

Expected: FAIL because compare still uses `all_pass` and ignores shadow provenance/rename mappings.

- [ ] **Step 4: Implement preflight, queries, and five-state aggregation**

```python
def require_matching_shadow_result(path: Path, plan: dict) -> dict:
    result = json.loads(Path(path).read_text(encoding=TEXT_ENCODING))
    require_format_version(result, "shadow_run_result")
    if result.get("mode") != "execute" or result.get("status") != "completed":
        raise StaleShadowResultError(
            "stale_shadow_result: completed execute shadow-run is required"
        )
    for field, expected in (
        ("workspace_fingerprint", plan["analysis_snapshot"]["workspace_fingerprint"]),
        ("plan_fingerprint", plan["plan_fingerprint"]),
    ):
        if result.get(field) != expected:
            raise StaleShadowResultError(
                f"stale_shadow_result: {field} does not match current plan"
            )
    return result
```

`run.py` performs fresh-plan validation before calling `compare_shadow_results(plan_path, shadow_result_path, output_path, ...)`; the compare function independently requires matching shadow provenance before opening connections, so the standalone module path cannot bypass the gate. Compare resolves each check's semantics from `verification.target_semantics[check.table]`; equivalent mismatches fail, unknown mismatches are inconclusive, unknown matches preserve warnings, and changed tables cannot have checks. Persist `{format_version, verification_status, warnings, results}` through `atomic_write_json()` and remove `all_pass`. Main returns 0 for passed/passed-with-warnings, 1 for failed/blocked, and 2 for inconclusive.

- [ ] **Step 5: Run focused tests and commit**

Run: `make test PYTEST_ARGS='tests/refact/test_compare.py tests/refact/test_run_cli.py -q'`

Expected: PASS.

```bash
git add src/dw_refactor_agent/refactor/compare.py src/dw_refactor_agent/refactor/run.py tests/refact/test_compare.py tests/refact/test_run_cli.py
git commit -m "feat(refactor): gate compare by semantic execution proof"
```

### Task 8: Documentation, Full Verification, Detailed Review, and Shop Acceptance

**Files:**
- Modify: `src/dw_refactor_agent/refactor/AGENTS.md`
- Create: `docs/superpowers/reviews/2026-07-13-semantic-aware-compare-targets-review.md`
- Verify: all changed production, test, manifest, plan, shadow, compare, and documentation files.

**Interfaces:**
- Produces: operator documentation and auditable acceptance/review evidence.
- Consumes: all prior tasks.

- [ ] **Step 1: Update operator documentation**

Document the exact `dw-refactor start/analyze/semantic-mode set/shadow-run/compare` commands, the neutral three-choice explanation, manifest intent schema, plan semantics/fingerprints, warning/status semantics, exit codes, and the required recovery sequence after `stale_plan` or `stale_shadow_result`.

Run: `rg -n 'semantic-mode|target_semantics|plan_fingerprint|passed_with_warnings|stale_plan' src/dw_refactor_agent/refactor/AGENTS.md`

Expected: each operator-facing contract appears in the directory guide.

- [ ] **Step 2: Run environment and full non-API verification**

Run: `make doctor`

Expected: Python 3.7 environment and all required modules pass.

Run: `make test`

Expected: Ruff check, Ruff format check, and the complete non-API pytest suite pass.

- [ ] **Step 3: Execute the real shop acceptance sequence**

Apply narrowly scoped temporary shop SQL changes with `apply_patch`, record the inverse edits before execution, then run:

```bash
START_OUTPUT="$(dw-refactor start --project shop)"
MANIFEST_PATH="$(printf '%s\n' "$START_OUTPUT" | sed -n 's/^Run manifest: //p')"
RUN_ID="$(basename "$(dirname "$MANIFEST_PATH")")"
dw-refactor analyze --run "$RUN_ID" --partition 2024-12-31
dw-refactor semantic-mode set --run "$RUN_ID" --table dws_store_sales_daily --mode equivalent
dw-refactor shadow-run --run "$RUN_ID"
dw-refactor compare --run "$RUN_ID" --method all
```

The temporary SQL edits must exercise: initial unknown with downstream observational warning; direct equivalent confirmation removing unchanged `ads_store_performance` and `dim_store_metric_snapshot`; an independently changed downstream; historical reuse in a second run; changed context invalidating reuse; stale workspace blocking shadow before QA reset; stale workspace blocking compare before connection; restored workspace completing a same-plan execute/compare; and stable-ID table/column rename direct Compare. Restore every temporary asset through an exact reverse patch or `apply_patch`, never destructive checkout/reset.

- [ ] **Step 4: Perform persistent-file-focused code review**

Inspect `git diff e8beffd5...HEAD` and record evidence for all 13 items in the approved review checklist. The review document must include:

```markdown
## Findings

- High: none
- Medium: none
- Low: none after fixes

## Persisted artifact audit

| Artifact | Producer | Consumer validation | Atomic write | Version |
|---|---|---|---|---|
| manifest.json | session/run | load_manifest | yes | 1 |
| plan.json | plan_artifact | semantic/shadow/compare preflight | yes | 1 |
| shadow_run_result.json | shadow_run | compare preflight | yes | 1 |
| compare_result.json | compare | operator/CI | yes | 1 |

## Shop acceptance evidence

Record run IDs, partition, selected jobs/checks, statuses, fingerprints, stale-stage exit behavior, and confirmation that temporary warehouse assets were restored.
```

Verify no manifest field loss, no stale declaration activation, exact history matching, no mtime/run/base-ref digest input, complete workspace coverage, self-excluding plan digest, pre-DB freshness checks, aligned format versions, no duplicated check authority/warnings, and no leftover shop asset diff.

- [ ] **Step 5: Re-run final checks and commit documentation**

Run: `git diff --check`

Expected: no whitespace errors.

Run: `make test`

Expected: PASS.

Run: `git status --short`

Expected: only the review/documentation files intended for the final commit remain; no temporary shop SQL, DDL, model, manifest, or generated run artifact is tracked.

```bash
git add src/dw_refactor_agent/refactor/AGENTS.md docs/superpowers/reviews/2026-07-13-semantic-aware-compare-targets-review.md
git commit -m "docs(refactor): document semantic verification workflow"
```
