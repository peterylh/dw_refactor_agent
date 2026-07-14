"""Strict contracts for public lineage version 2 artifacts."""

from __future__ import annotations

from typing import Any, Callable

from dw_refactor_agent.lineage.identifiers import (
    identifier_match_key,
    table_identity_match_key,
)

FORMAT_VERSION = 2
DATASET_TYPES = frozenset({"managed", "process", "temporary", "external"})
DIAGNOSTIC_REASONS = frozenset({"not_found", "multiple_candidates"})

LINEAGE_KEYS = frozenset(
    {"format_version", "tables", "jobs", "edges", "diagnostics"}
)
TABLE_KEYS = frozenset({"name", "full_name", "dataset_type", "columns"})
COLUMN_KEYS = frozenset({"name", "type"})
JOB_KEYS = frozenset({"name", "source_file", "inputs", "outputs"})
EDGE_KEYS = frozenset(
    {
        "source",
        "target",
        "relation_type",
        "transformation_type",
        "expression",
        "job",
    }
)
DIAGNOSTIC_KEYS = frozenset(
    {
        "code",
        "dataset",
        "reason",
        "consumer_jobs",
        "candidate_producer_jobs",
    }
)
DAG_KEYS = frozenset(
    {"format_version", "jobs", "data_dependencies", "deps", "rev"}
)
DEPENDENCY_KEYS = frozenset({"upstream_job", "downstream_job", "datasets"})


class LineageContractError(ValueError):
    """Raised when a public lineage artifact violates version 2."""


def _fail(path: str, message: str) -> None:
    raise LineageContractError(f"{path}: {message}")


def _require_object(value: Any, path: str) -> dict:
    if not isinstance(value, dict):
        _fail(path, f"must be an object; received {type(value).__name__}")
    return value


def _require_array(value: Any, path: str) -> list:
    if not isinstance(value, list):
        _fail(path, f"must be an array; received {type(value).__name__}")
    return value


def _require_exact_keys(value: dict, expected: frozenset, path: str) -> None:
    missing = sorted(expected.difference(value))
    unexpected = sorted(set(value).difference(expected))
    if missing:
        _fail(path, f"missing required fields: {', '.join(missing)}")
    if unexpected:
        _fail(path, f"unexpected fields: {', '.join(unexpected)}")


def _require_string(
    value: Any, path: str, *, allow_empty: bool = False
) -> str:
    if not isinstance(value, str):
        _fail(path, f"must be a string; received {type(value).__name__}")
    if not allow_empty and not value.strip():
        _fail(path, "must be a non-empty string")
    return value


def _validate_format_version(value: Any, path: str) -> None:
    if type(value) is not int or value != FORMAT_VERSION:
        _fail(
            path,
            f"must be integer {FORMAT_VERSION}; received {value!r}",
        )


def _validate_sorted_unique_strings(
    value: Any,
    path: str,
    *,
    key: Callable[[str], Any],
    known: set | None = None,
) -> list[str]:
    values = _require_array(value, path)
    normalized = []
    seen = set()
    for index, item in enumerate(values):
        text = _require_string(item, f"{path}[{index}]")
        item_key = key(text)
        if item_key in seen:
            _fail(path, f"contains duplicate value {text!r}")
        if known is not None and item_key not in known:
            _fail(path, f"references missing value {text!r}")
        seen.add(item_key)
        normalized.append(item_key)
    if normalized != sorted(normalized):
        _fail(path, "must be sorted by canonical identifier")
    return values


def _validate_table(table: Any, path: str) -> tuple:
    table = _require_object(table, path)
    _require_exact_keys(table, TABLE_KEYS, path)
    _require_string(table["name"], f"{path}.name")
    full_name = _require_string(table["full_name"], f"{path}.full_name")
    dataset_type = _require_string(
        table["dataset_type"], f"{path}.dataset_type"
    )
    if dataset_type not in DATASET_TYPES:
        _fail(
            f"{path}.dataset_type",
            f"unsupported value {dataset_type!r}; expected one of "
            f"{sorted(DATASET_TYPES)!r}",
        )

    columns = _require_array(table["columns"], f"{path}.columns")
    column_names = set()
    for index, column in enumerate(columns):
        column_path = f"{path}.columns[{index}]"
        column = _require_object(column, column_path)
        _require_exact_keys(column, COLUMN_KEYS, column_path)
        name = _require_string(column["name"], f"{column_path}.name")
        _require_string(
            column["type"], f"{column_path}.type", allow_empty=True
        )
        name_key = identifier_match_key(name)
        if name_key in column_names:
            _fail(column_path, f"duplicate column name {name!r}")
        column_names.add(name_key)
    return table_identity_match_key(full_name)


def _validate_job(
    job: Any,
    path: str,
    known_tables: set,
) -> tuple[str, Any]:
    job = _require_object(job, path)
    _require_exact_keys(job, JOB_KEYS, path)
    name = _require_string(job["name"], f"{path}.name")
    _require_string(job["source_file"], f"{path}.source_file")
    for field in ("inputs", "outputs"):
        _validate_sorted_unique_strings(
            job[field],
            f"{path}.{field}",
            key=table_identity_match_key,
            known=known_tables,
        )
    return name, identifier_match_key(name)


def _validate_source_ref(value: Any, path: str) -> None:
    value = _require_object(value, path)
    ref_type = _require_string(value.get("type"), f"{path}.type")
    if ref_type == "column":
        _require_exact_keys(value, frozenset({"type", "id"}), path)
        _require_string(value["id"], f"{path}.id")
        return
    if ref_type == "literal":
        _require_exact_keys(value, frozenset({"type", "value"}), path)
        if type(value["value"]) not in {str, int, float, bool, type(None)}:
            _fail(f"{path}.value", "must be a JSON scalar")
        return
    if ref_type == "expression":
        _require_exact_keys(value, frozenset({"type", "expression"}), path)
        _require_string(value["expression"], f"{path}.expression")
        return
    _fail(
        f"{path}.type",
        f"unsupported value {ref_type!r}; expected column/literal/expression",
    )


def _validate_target_ref(value: Any, path: str) -> None:
    value = _require_object(value, path)
    _require_exact_keys(value, frozenset({"type", "id"}), path)
    ref_type = _require_string(value["type"], f"{path}.type")
    if ref_type not in {"column", "table"}:
        _fail(
            f"{path}.type",
            f"unsupported value {ref_type!r}; expected column/table",
        )
    _require_string(value["id"], f"{path}.id")


def _validate_edge(edge: Any, path: str, known_jobs: set) -> None:
    edge = _require_object(edge, path)
    _require_exact_keys(edge, EDGE_KEYS, path)
    _validate_source_ref(edge["source"], f"{path}.source")
    _validate_target_ref(edge["target"], f"{path}.target")
    for field in ("relation_type", "transformation_type"):
        _require_string(edge[field], f"{path}.{field}")
    _require_string(edge["expression"], f"{path}.expression", allow_empty=True)
    job = _require_string(edge["job"], f"{path}.job")
    if identifier_match_key(job) not in known_jobs:
        _fail(f"{path}.job", f"references missing Job {job!r}")


def _validate_diagnostic(
    diagnostic: Any,
    path: str,
    known_tables: set,
    known_jobs: set,
) -> None:
    diagnostic = _require_object(diagnostic, path)
    _require_exact_keys(diagnostic, DIAGNOSTIC_KEYS, path)
    code = _require_string(diagnostic["code"], f"{path}.code")
    if code != "UNRESOLVED_DATASET_PRODUCER":
        _fail(f"{path}.code", f"unsupported value {code!r}")
    dataset = _require_string(diagnostic["dataset"], f"{path}.dataset")
    if table_identity_match_key(dataset) not in known_tables:
        _fail(f"{path}.dataset", f"references missing table {dataset!r}")
    reason = _require_string(diagnostic["reason"], f"{path}.reason")
    if reason not in DIAGNOSTIC_REASONS:
        _fail(f"{path}.reason", f"unsupported value {reason!r}")
    for field in ("consumer_jobs", "candidate_producer_jobs"):
        _validate_sorted_unique_strings(
            diagnostic[field],
            f"{path}.{field}",
            key=identifier_match_key,
            known=known_jobs,
        )


def validate_lineage_v2(data: dict) -> None:
    """Validate one strict lineage version 2 public artifact.

    Raises:
        LineageContractError: If the artifact is not strict version 2.
    """
    data = _require_object(data, "lineage")
    _require_exact_keys(data, LINEAGE_KEYS, "lineage")
    _validate_format_version(data["format_version"], "lineage.format_version")

    tables = _require_array(data["tables"], "lineage.tables")
    known_tables = set()
    for index, table in enumerate(tables):
        table_key = _validate_table(table, f"lineage.tables[{index}]")
        if table_key in known_tables:
            _fail(
                f"lineage.tables[{index}].full_name",
                f"duplicate table {table['full_name']!r}",
            )
        known_tables.add(table_key)

    jobs = _require_array(data["jobs"], "lineage.jobs")
    known_jobs = set()
    for index, job in enumerate(jobs):
        name, name_key = _validate_job(
            job,
            f"lineage.jobs[{index}]",
            known_tables,
        )
        if name_key in known_jobs:
            _fail(f"lineage.jobs[{index}].name", f"duplicate Job {name!r}")
        known_jobs.add(name_key)

    edges = _require_array(data["edges"], "lineage.edges")
    for index, edge in enumerate(edges):
        _validate_edge(edge, f"lineage.edges[{index}]", known_jobs)

    diagnostics = _require_array(data["diagnostics"], "lineage.diagnostics")
    for index, diagnostic in enumerate(diagnostics):
        _validate_diagnostic(
            diagnostic,
            f"lineage.diagnostics[{index}]",
            known_tables,
            known_jobs,
        )


def _validate_dag_jobs(value: Any) -> tuple[list[str], set]:
    jobs = _validate_sorted_unique_strings(
        value,
        "job_dag.jobs",
        key=identifier_match_key,
    )
    return jobs, {identifier_match_key(job) for job in jobs}


def _validate_adjacency(
    value: Any,
    path: str,
    jobs: list[str],
    known_jobs: set,
) -> set[tuple]:
    value = _require_object(value, path)
    keys_by_id = {}
    for raw_key in value:
        key = _require_string(raw_key, f"{path} key")
        key_id = identifier_match_key(key)
        if key_id in keys_by_id:
            _fail(path, f"contains duplicate Job key {key!r}")
        keys_by_id[key_id] = key
    missing = known_jobs.difference(keys_by_id)
    unexpected = set(keys_by_id).difference(known_jobs)
    if missing:
        _fail(path, f"missing Job keys: {sorted(missing)!r}")
    if unexpected:
        _fail(path, f"unexpected Job keys: {sorted(unexpected)!r}")

    pairs = set()
    for job in jobs:
        job_key = identifier_match_key(job)
        displayed_key = keys_by_id[job_key]
        neighbours = _validate_sorted_unique_strings(
            value[displayed_key],
            f"{path}.{displayed_key}",
            key=identifier_match_key,
            known=known_jobs,
        )
        for neighbour in neighbours:
            neighbour_key = identifier_match_key(neighbour)
            if neighbour_key == job_key:
                _fail(f"{path}.{displayed_key}", "must not contain self edges")
            pairs.add((job_key, neighbour_key))
    return pairs


def validate_job_dag_v2(data: dict) -> None:
    """Validate one strict Job DAG version 2 public artifact.

    Raises:
        LineageContractError: If the artifact is not strict version 2.
    """
    data = _require_object(data, "job_dag")
    _require_exact_keys(data, DAG_KEYS, "job_dag")
    _validate_format_version(data["format_version"], "job_dag.format_version")

    jobs, known_jobs = _validate_dag_jobs(data["jobs"])
    dependencies = _require_array(
        data["data_dependencies"], "job_dag.data_dependencies"
    )
    dependency_pairs = set()
    for index, dependency in enumerate(dependencies):
        path = f"job_dag.data_dependencies[{index}]"
        dependency = _require_object(dependency, path)
        _require_exact_keys(dependency, DEPENDENCY_KEYS, path)
        upstream = _require_string(
            dependency["upstream_job"], f"{path}.upstream_job"
        )
        downstream = _require_string(
            dependency["downstream_job"], f"{path}.downstream_job"
        )
        upstream_key = identifier_match_key(upstream)
        downstream_key = identifier_match_key(downstream)
        for field, display, job_key in (
            ("upstream_job", upstream, upstream_key),
            ("downstream_job", downstream, downstream_key),
        ):
            if job_key not in known_jobs:
                _fail(f"{path}.{field}", f"references missing Job {display!r}")
        if upstream_key == downstream_key:
            _fail(path, "must not describe a self dependency")
        pair = (upstream_key, downstream_key)
        if pair in dependency_pairs:
            _fail(
                path,
                f"duplicate Job dependency {upstream!r} -> {downstream!r}",
            )
        dependency_pairs.add(pair)
        datasets = _validate_sorted_unique_strings(
            dependency["datasets"],
            f"{path}.datasets",
            key=table_identity_match_key,
        )
        if not datasets:
            _fail(f"{path}.datasets", "must contain dependency evidence")

    deps_pairs = _validate_adjacency(
        data["deps"], "job_dag.deps", jobs, known_jobs
    )
    rev_pairs = {
        (upstream, downstream)
        for downstream, upstream in _validate_adjacency(
            data["rev"], "job_dag.rev", jobs, known_jobs
        )
    }
    if deps_pairs != dependency_pairs:
        _fail(
            "job_dag.deps",
            "must describe the same edges as data_dependencies",
        )
    if rev_pairs != dependency_pairs:
        _fail(
            "job_dag.rev",
            "must describe the same edges as data_dependencies",
        )
