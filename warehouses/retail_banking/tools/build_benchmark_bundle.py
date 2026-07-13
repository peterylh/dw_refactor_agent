#!/usr/bin/env python3
"""Build physically separated public and evaluator benchmark bundles."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
from pathlib import Path
from typing import Optional

import yaml

PROJECT_DIR = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = PROJECT_DIR.parents[1]
TEXT_ENCODING = "utf-8"
TRACKS = ("named_taxonomy_assisted", "prefixless_role_blind")
BENCHMARK_CONTRACT_FILENAME = "benchmark_contract.yaml"
PRIVATE_GOLD_SCHEMA_REFERENCE = f"{BENCHMARK_CONTRACT_FILENAME}#table_record"
LEGACY_PRIVATE_GOLD_SCHEMA_REFERENCE = "gold_schema.yaml#table_record"
_SCHEMA_KEYWORDS = {
    "type",
    "description",
    "required",
    "enum",
    "items",
    "minimum",
    "maximum",
    "min_items",
    "fields",
}


def _asset_paths() -> tuple[list[Path], list[Path]]:
    ddl_paths = sorted(PROJECT_DIR.glob("ods/ddl/*/*/*.sql"))
    ddl_paths += sorted(PROJECT_DIR.glob("mid/ddl/*.sql"))
    ddl_paths += sorted(PROJECT_DIR.glob("ads/ddl/*.sql"))
    task_paths = sorted(PROJECT_DIR.glob("mid/tasks/*.sql"))
    task_paths += sorted(PROJECT_DIR.glob("ads/tasks/*.sql"))
    return ddl_paths, task_paths


def _strip_semantic_comments(sql: str) -> str:
    sql = re.sub(r"(?m)^\s*--[^\n]*(?:\n|$)", "", sql)
    sql = re.sub(r"\s+COMMENT\s+'(?:''|[^'])*'", "", sql, flags=re.I)
    return re.sub(r"\n{3,}", "\n\n", sql).strip() + "\n"


def _transform_sql(sql: str, aliases: dict[str, str], role_blind: bool) -> str:
    value = sql.replace("retail_banking_dm", "benchmark_db")
    if role_blind:
        for source_name in sorted(aliases, key=len, reverse=True):
            value = re.sub(
                rf"(?<![A-Za-z0-9_]){re.escape(source_name)}(?![A-Za-z0-9_])",
                aliases[source_name],
                value,
            )
        value = _strip_semantic_comments(value)
    return value


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_yaml(path: Path) -> dict:
    value = yaml.safe_load(path.read_text(encoding=TEXT_ENCODING))
    if not isinstance(value, dict):
        raise ValueError(f"Expected YAML object: {path}")
    return value


def _schema_properties(schema: dict) -> dict:
    properties = dict(schema.get("fields") or {})
    properties.update(
        {
            key: value
            for key, value in schema.items()
            if key not in _SCHEMA_KEYWORDS and isinstance(value, dict)
        }
    )
    return properties


def _matches_type(value: object, expected_type: str) -> bool:
    return {
        "null": value is None,
        "string": isinstance(value, str),
        "number": isinstance(value, (int, float))
        and not isinstance(value, bool),
        "object": isinstance(value, dict),
        "array": isinstance(value, list),
        "boolean": isinstance(value, bool),
        "integer": isinstance(value, int) and not isinstance(value, bool),
    }.get(expected_type, False)


def _validate_schema_value(value: object, schema: object, path: str) -> None:
    if isinstance(schema, str):
        schema = {"type": schema}
    if not isinstance(schema, dict):
        raise ValueError(f"Invalid schema at {path}")
    expected_types = schema.get("type")
    if expected_types is not None:
        if isinstance(expected_types, str):
            expected_types = [expected_types]
        if not any(_matches_type(value, item) for item in expected_types):
            raise ValueError(
                f"{path}: expected type {expected_types}, got "
                f"{type(value).__name__}"
            )
    if value is None:
        return
    if "enum" in schema and value not in schema["enum"]:
        raise ValueError(f"{path}: value {value!r} is not in enum")
    if isinstance(value, dict):
        properties = _schema_properties(schema)
        required = set(schema.get("required") or [])
        missing = sorted(required - set(value))
        if missing:
            raise ValueError(f"{path}: missing required fields {missing}")
        unknown = sorted(set(value) - set(properties)) if properties else []
        if unknown:
            raise ValueError(f"{path}: unknown fields {unknown}")
        for key, item in value.items():
            if key in properties:
                _validate_schema_value(item, properties[key], f"{path}.{key}")
    if isinstance(value, list):
        minimum_items = schema.get("min_items")
        if minimum_items is not None and len(value) < minimum_items:
            raise ValueError(
                f"{path}: expected at least {minimum_items} items"
            )
        item_schema = schema.get("items")
        if item_schema is not None:
            for index, item in enumerate(value):
                _validate_schema_value(item, item_schema, f"{path}[{index}]")
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if "minimum" in schema and value < schema["minimum"]:
            raise ValueError(f"{path}: value is below minimum")
        if "maximum" in schema and value > schema["maximum"]:
            raise ValueError(f"{path}: value is above maximum")


def validate_private_gold(private_gold: Path) -> dict:
    private_gold = private_gold.expanduser().resolve()
    try:
        private_gold.relative_to(REPOSITORY_ROOT.resolve())
    except ValueError:
        pass
    else:
        raise ValueError(
            "Private gold must be supplied from outside the Git checkout"
        )
    payload = _load_yaml(private_gold)
    allowed_top_level = {
        "version",
        "project",
        "upstream_commit",
        "warning",
        "schema",
        "status",
        "records",
        "expected_asset_counts",
    }
    required_top_level = allowed_top_level
    missing = sorted(required_top_level - set(payload))
    if missing:
        raise ValueError(f"private_gold: missing required fields {missing}")
    unknown = sorted(set(payload) - allowed_top_level)
    if unknown:
        raise ValueError(f"private_gold: unknown fields {unknown}")
    if payload.get("project") != "retail_banking":
        raise ValueError("private_gold.project must be retail_banking")
    if payload.get("version") != 1:
        raise ValueError("private_gold.version must be 1")
    if payload.get("schema") not in {
        PRIVATE_GOLD_SCHEMA_REFERENCE,
        LEGACY_PRIVATE_GOLD_SCHEMA_REFERENCE,
    }:
        raise ValueError("private_gold.schema must reference the table record")
    if payload.get("status") != "candidate_not_gold_v1":
        raise ValueError("private_gold.status is not supported")
    records = payload.get("records")
    if not isinstance(records, list):
        raise ValueError("private_gold.records must be an array")
    expected_counts = payload.get("expected_asset_counts")
    if not isinstance(expected_counts, dict):
        raise ValueError(
            "private_gold.expected_asset_counts must be an object"
        )
    expected_count_keys = {"ODS", "DIM_DWD", "DWS", "ADS"}
    if set(expected_counts) != expected_count_keys or not all(
        isinstance(value, int) and not isinstance(value, bool) and value >= 0
        for value in expected_counts.values()
    ):
        raise ValueError(
            "private_gold.expected_asset_counts must contain non-negative "
            "integer ODS, DIM_DWD, DWS and ADS counts"
        )
    expected_record_count = sum(expected_counts.values())
    if len(records) != expected_record_count:
        raise ValueError(
            "private_gold record count does not match expected_asset_counts"
        )
    record_schema = _load_yaml(
        PROJECT_DIR / f"benchmark/{BENCHMARK_CONTRACT_FILENAME}"
    )["table_record"]
    registered_ddl_paths, registered_task_paths = _asset_paths()
    registered_ddl = {
        path.relative_to(PROJECT_DIR).as_posix(): path
        for path in registered_ddl_paths
    }
    registered_tasks = {
        path.relative_to(PROJECT_DIR).as_posix(): path
        for path in registered_task_paths
    }
    registered_tasks_by_asset = {}
    for relative_path, task_path in registered_tasks.items():
        registered_tasks_by_asset.setdefault(task_path.stem, set()).add(
            relative_path
        )
    asset_ids = []
    asset_names = []
    actual_counts = {key: 0 for key in expected_count_keys}
    for index, record in enumerate(records):
        _validate_schema_value(record, record_schema, f"records[{index}]")
        asset_ids.append(record["asset_id"])
        asset_names.append(record["asset_name"])
        layer = record["expected"]["layer"]
        actual_counts["DIM_DWD" if layer in {"DIM", "DWD"} else layer] += 1
        ddl_paths = record["evidence"]["ddl_paths"]
        if len(ddl_paths) != 1:
            raise ValueError(
                f"records[{index}].evidence.ddl_paths must contain one path"
            )
        ddl_reference = Path(ddl_paths[0]).as_posix()
        if ddl_reference not in registered_ddl:
            raise ValueError(
                f"records[{index}].evidence.ddl_paths is not a registered DDL asset"
            )
        task_references = [
            Path(path).as_posix() for path in record["evidence"]["task_paths"]
        ]
        expected_task_references = registered_tasks_by_asset.get(
            record["asset_name"], set()
        )
        if set(task_references) != expected_task_references or len(
            task_references
        ) != len(expected_task_references):
            raise ValueError(
                f"records[{index}].evidence.task_paths must exactly match "
                "the registered task assets"
            )
        if Path(ddl_reference).stem != record["asset_name"]:
            raise ValueError(
                f"records[{index}].asset_name does not match its DDL path"
            )
    if len(asset_ids) != len(set(asset_ids)):
        raise ValueError("private_gold.asset_id values must be unique")
    if len(asset_names) != len(set(asset_names)):
        raise ValueError("private_gold.asset_name values must be unique")
    if set(asset_names) != {path.stem for path in registered_ddl_paths}:
        raise ValueError(
            "private_gold assets do not match the warehouse DDL set"
        )
    if actual_counts != expected_counts:
        raise ValueError(
            "private_gold expected_asset_counts do not match record layers"
        )
    return payload


def _physical_key(ddl_path: Path) -> list[str]:
    match = re.search(
        r"DUPLICATE\s+KEY\s*\(([^)]*)\)",
        ddl_path.read_text(encoding=TEXT_ENCODING),
        flags=re.I,
    )
    if match is None:
        raise ValueError(f"Missing DUPLICATE KEY: {ddl_path}")
    return re.findall(r"`([^`]+)`", match.group(1))


def _constraint_payload(
    *, ddl_paths: list[Path], aliases: dict[str, str], role_blind: bool
) -> dict:
    schema = _load_yaml(PROJECT_DIR / "mappings/fineract_schema_snapshot.yaml")
    mapping = _load_yaml(PROJECT_DIR / "mappings/fineract_table_mapping.yaml")
    mapping_by_source = {
        item["source_table"]: item for item in mapping["mappings"]
    }
    source_by_ods = {
        item["ods_table"]: item["source_table"] for item in mapping["mappings"]
    }
    schema_by_source = {
        item["source_table"]: item for item in schema["tables"]
    }
    ddl_by_name = {path.stem: path for path in ddl_paths}
    table_names = set(ddl_by_name)
    external_reference_names = sorted(
        {
            constraint.get("referenced_table")
            for source_table in schema_by_source.values()
            for constraint in source_table.get("foreign_keys") or []
            if constraint.get("referenced_table")
            and (
                constraint.get("referenced_table") not in mapping_by_source
                or mapping_by_source[constraint.get("referenced_table")][
                    "ods_table"
                ]
                not in table_names
            )
        }
    )
    external_aliases = {
        name: f"external_asset_{index:04d}"
        for index, name in enumerate(external_reference_names, 1)
    }
    unique_count = 0
    foreign_key_count = 0
    external_foreign_key_count = 0
    tables = []
    for table_name in sorted(table_names):
        source_name = source_by_ods.get(table_name)
        source_table = schema_by_source.get(source_name, {})
        unique_constraints = []
        for constraint in source_table.get("unique_constraints") or []:
            unique_count += 1
            unique_constraints.append(
                {
                    "constraint_id": f"uk_{unique_count:04d}",
                    "columns": list(constraint.get("columns") or []),
                }
            )
        foreign_keys = []
        external_foreign_keys = []
        for constraint in source_table.get("foreign_keys") or []:
            referenced_source = constraint.get("referenced_table")
            if not referenced_source:
                raise ValueError(
                    f"Foreign key without referenced_table: {source_name}"
                )
            referenced_mapping = mapping_by_source.get(referenced_source)
            referenced_table = (
                referenced_mapping["ods_table"]
                if referenced_mapping is not None
                else None
            )
            if referenced_table not in table_names:
                external_foreign_key_count += 1
                external_foreign_keys.append(
                    {
                        "constraint_id": (
                            f"external_fk_{external_foreign_key_count:04d}"
                        ),
                        "columns": list(constraint.get("base_columns") or []),
                        "referenced_external_table": (
                            external_aliases[referenced_source]
                            if role_blind
                            else referenced_source
                        ),
                        "referenced_columns": list(
                            constraint.get("referenced_columns") or []
                        ),
                        "on_delete": constraint.get("on_delete"),
                        "on_update": constraint.get("on_update"),
                        "exclusion_reason": (
                            "referenced table is outside the analytical "
                            "warehouse scope"
                        ),
                    }
                )
                continue
            foreign_key_count += 1
            foreign_keys.append(
                {
                    "constraint_id": f"fk_{foreign_key_count:04d}",
                    "columns": list(constraint.get("base_columns") or []),
                    "referenced_table": (
                        aliases[referenced_table]
                        if role_blind
                        else referenced_table
                    ),
                    "referenced_columns": list(
                        constraint.get("referenced_columns") or []
                    ),
                    "on_delete": constraint.get("on_delete"),
                    "on_update": constraint.get("on_update"),
                }
            )
        tables.append(
            {
                "table": aliases[table_name] if role_blind else table_name,
                "key_model": "DUPLICATE",
                "physical_key": _physical_key(ddl_by_name[table_name]),
                "source_primary_key": list(
                    source_table.get("primary_key") or []
                ),
                "unique_constraints": unique_constraints,
                "foreign_keys": foreign_keys,
                "external_foreign_keys": external_foreign_keys,
            }
        )
    return {
        "version": 1,
        "track": (
            "prefixless_role_blind"
            if role_blind
            else "named_taxonomy_assisted"
        ),
        "semantics": (
            "Source PK/UK/FK evidence is recorded for ODS mirrors; references "
            "outside the analytical scope are explicit external_foreign_keys. "
            "physical_key records the Doris DUPLICATE KEY for every asset."
        ),
        "counts": {
            "tables": len(tables),
            "unique_constraints": unique_count,
            "foreign_keys": foreign_key_count,
            "external_foreign_keys": external_foreign_key_count,
            "source_foreign_keys": (
                foreign_key_count + external_foreign_key_count
            ),
        },
        "tables": tables,
    }


def build_bundle(
    *,
    output: Path,
    track: str,
    force: bool = False,
    private_gold: Optional[Path] = None,
) -> None:
    output = output.expanduser().resolve()
    try:
        output.relative_to(REPOSITORY_ROOT.resolve())
    except ValueError:
        pass
    else:
        raise ValueError("Bundle output must be outside the Git checkout")
    if output.exists():
        if not force:
            raise FileExistsError(f"Output already exists: {output}")
        shutil.rmtree(str(output))

    ddl_paths, task_paths = _asset_paths()
    table_names = sorted({path.stem for path in ddl_paths})
    aliases = {
        name: f"asset_{index:04d}" for index, name in enumerate(table_names, 1)
    }
    role_blind = track == "prefixless_role_blind"
    public_ddl = output / "public" / "ddl"
    public_tasks = output / "public" / "tasks"
    evaluator = output / "evaluator"
    for directory in (public_ddl, public_tasks, evaluator):
        directory.mkdir(parents=True, exist_ok=True)

    written_public: list[Path] = []
    for source_path, target_root in [
        *((path, public_ddl) for path in ddl_paths),
        *((path, public_tasks) for path in task_paths),
    ]:
        target_stem = (
            aliases[source_path.stem] if role_blind else source_path.stem
        )
        target_path = target_root / f"{target_stem}.sql"
        target_path.write_text(
            _transform_sql(
                source_path.read_text(encoding=TEXT_ENCODING),
                aliases,
                role_blind,
            ),
            encoding=TEXT_ENCODING,
        )
        written_public.append(target_path)
    if not role_blind:
        taxonomy_target = output / "public/business_taxonomy.yaml"
        shutil.copy2(
            str(PROJECT_DIR / "business_taxonomy.yaml"), str(taxonomy_target)
        )
        written_public.append(taxonomy_target)
    constraints_target = output / "public/constraints.yaml"
    constraints = _constraint_payload(
        ddl_paths=ddl_paths, aliases=aliases, role_blind=role_blind
    )
    constraints_target.write_text(
        yaml.safe_dump(
            constraints, allow_unicode=True, sort_keys=False, width=100
        ),
        encoding=TEXT_ENCODING,
    )
    written_public.append(constraints_target)

    alias_payload = {
        "version": 1,
        "track": track,
        "private": True,
        "table_aliases": aliases
        if role_blind
        else {name: name for name in table_names},
    }
    (evaluator / "alias_map.yaml").write_text(
        yaml.safe_dump(alias_payload, allow_unicode=True, sort_keys=True),
        encoding=TEXT_ENCODING,
    )
    shutil.copy2(
        str(PROJECT_DIR / f"benchmark/{BENCHMARK_CONTRACT_FILENAME}"),
        str(evaluator / BENCHMARK_CONTRACT_FILENAME),
    )
    if private_gold is not None:
        private_gold = private_gold.expanduser().resolve()
        gold_payload = validate_private_gold(private_gold)
        gold_payload["schema"] = PRIVATE_GOLD_SCHEMA_REFERENCE
        (evaluator / "private_gold.yaml").write_text(
            yaml.safe_dump(
                gold_payload,
                allow_unicode=True,
                sort_keys=False,
            ),
            encoding=TEXT_ENCODING,
        )
    manifest = {
        "version": 1,
        "project": "retail_banking",
        "track": track,
        "role_blind": role_blind,
        "counts": {"ddl": len(ddl_paths), "tasks": len(task_paths)},
        "constraint_counts": constraints["counts"],
        "evaluator_gold_included": private_gold is not None,
        "public_files": {
            str(path.relative_to(output / "public")): _sha256(path)
            for path in sorted(written_public)
        },
        "forbidden_source_families_absent": [
            "models",
            "mappings",
            "semantic_specs",
            "private_gold",
            "lineage_source_file",
        ]
        + (["business_catalogs"] if role_blind else []),
    }
    (output / "public/manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding=TEXT_ENCODING,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--track", choices=TRACKS, required=True)
    parser.add_argument("--force", action="store_true")
    parser.add_argument(
        "--private-gold",
        type=Path,
        help=(
            "Optional access-controlled gold file outside the Git checkout. "
            "Omit it to build a participant-only public bundle."
        ),
    )
    args = parser.parse_args()
    build_bundle(
        output=args.output,
        track=args.track,
        force=args.force,
        private_gold=args.private_gold,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
