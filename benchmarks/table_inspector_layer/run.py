#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
import tempfile
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import assess.llm.model_metadata_writer as writer  # noqa: E402
import config  # noqa: E402
from assess.llm.model_metadata_writer import (
    run_direct_model_generation,  # noqa: E402
)

LAYER_PREFIXES = ("ods_", "dwd_", "dws_", "ads_", "dim_")
LAYER_WORD_PATTERN = re.compile(
    r"(?i)\b(?:ODS|DWD|DWS|ADS|DIM)\b|"
    r"(?:贴源层|原始层|明细层|汇总层|应用层|维度层|维表|"
    r"明细事实表|汇总事实表|应用表|看板表|驾驶舱|"
    r"明细粒度|汇总指标|分层|数据分层|层级)"
)
SQL_LINE_COMMENT_PATTERN = re.compile(r"(?m)^\s*--[^\n]*(?:\n|$)")
SQL_COMMENT_CLAUSE_PATTERN = re.compile(
    r"\s+COMMENT\s+(?:'[^']*'|\"[^\"]*\")", re.IGNORECASE
)
FIXED_LAYER_GROUPS = {"ODS", "ADS"}
MIDDLE_LAYER_GROUPS = {"DWD", "DWS", "DIM"}


def reset_config(project_root: Path) -> None:
    config.core.PROJECT_ROOT = project_root
    config.PROJECT_ROOT = project_root
    writer.PROJECT_ROOT = project_root
    config.clear_naming_config_cache()
    config.clear_model_metadata_cache()
    config.clear_business_semantics_cache()


def strip_layer_prefix(name: str) -> str:
    for prefix in LAYER_PREFIXES:
        if name.startswith(prefix):
            return name[len(prefix) :]
    return name


def sanitize_text(text: str) -> str:
    return LAYER_WORD_PATTERN.sub("", text)


def replace_table_refs(text: str, mapping: dict[str, str]) -> str:
    for old, new in sorted(
        mapping.items(), key=lambda item: len(item[0]), reverse=True
    ):
        text = re.sub(
            rf"(?<![A-Za-z0-9_]){re.escape(old)}(?![A-Za-z0-9_])",
            new,
            text,
        )
    return sanitize_text(text)


def sanitize_sql(text: str, mapping: dict[str, str]) -> str:
    text = replace_table_refs(text, mapping)
    text = SQL_LINE_COMMENT_PATTERN.sub("", text)
    text = SQL_COMMENT_CLAUSE_PATTERN.sub("", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip() + "\n"


def rewrite_source_files(value: Any, source_mapping: dict[str, str]) -> Any:
    if isinstance(value, dict):
        return {
            key: (
                source_mapping.get(raw, raw)
                if key in {"source_file", "source_path"} and isinstance(raw, str)
                else rewrite_source_files(raw, source_mapping)
            )
            for key, raw in value.items()
        }
    if isinstance(value, list):
        return [rewrite_source_files(item, source_mapping) for item in value]
    if isinstance(value, str):
        return source_mapping.get(value, value)
    return value


def model_paths(project: str) -> list[Path]:
    project_dir = REPO_ROOT / project
    paths = list((project_dir / "models").glob("*.yaml"))
    paths += list((project_dir / "mid" / "models").glob("*.yaml"))
    paths += list((project_dir / "ads" / "models").glob("*.yaml"))
    paths += list((project_dir / "ods" / "models").glob("*/*/*.yaml"))
    return sorted(paths)


def ddl_paths(project: str) -> list[Path]:
    project_dir = REPO_ROOT / project
    paths = list((project_dir / "ddl").glob("*.sql"))
    paths += list((project_dir / "mid" / "ddl").glob("*.sql"))
    paths += list((project_dir / "ads" / "ddl").glob("*.sql"))
    paths += list((project_dir / "ods" / "ddl").glob("*/*/*.sql"))
    return sorted(paths)


def task_roots(project: str) -> list[Path]:
    project_dir = REPO_ROOT / project
    roots = [
        project_dir / "tasks",
        project_dir / "mid" / "tasks",
        project_dir / "ads" / "tasks",
    ]
    return [root for root in roots if root.exists()]


def load_expected(project: str) -> dict[str, dict[str, str]]:
    expected = {}
    for path in model_paths(project):
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        table = str(data.get("name") or path.stem)
        expected[table] = {
            "layer": str(data.get("layer") or "OTHER").upper(),
            "table_type": str(data.get("table_type") or "other"),
        }
    return expected


def expected_layer(
    table_name: str, expected: dict[str, dict[str, str]]
) -> str:
    return str(expected.get(table_name, {}).get("layer") or "OTHER").upper()


def table_group(table_name: str, expected: dict[str, dict[str, str]]) -> str:
    layer = expected_layer(table_name, expected)
    if layer == "ODS":
        return "ods"
    if layer == "ADS":
        return "ads"
    return "middle"


def ddl_output_path(
    target_dir: Path,
    table_name: str,
    expected: dict[str, dict[str, str]],
) -> Path:
    group = table_group(table_name, expected)
    if group == "ods":
        return target_dir / "ods" / "ddl" / "internal" / "benchmark"
    if group == "ads":
        return target_dir / "ads" / "ddl"
    return target_dir / "mid" / "ddl"


def task_output_path(
    target_dir: Path,
    table_name: str,
    expected: dict[str, dict[str, str]],
    rel_parent: Path,
) -> Path:
    group = table_group(table_name, expected)
    if group == "ads":
        return target_dir / "ads" / "tasks" / rel_parent
    return target_dir / "mid" / "tasks" / rel_parent


def write_fixed_layer_model_seed(
    target_dir: Path,
    table_name: str,
    metadata: dict[str, str],
) -> None:
    layer = str(metadata.get("layer") or "OTHER").upper()
    if layer not in FIXED_LAYER_GROUPS:
        return
    payload = {
        "name": table_name,
        "layer": layer,
        "table_type": str(metadata.get("table_type") or "other"),
    }
    if layer == "ODS":
        out_dir = target_dir / "ods" / "models" / "internal" / "benchmark"
    else:
        out_dir = target_dir / "ads" / "models"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / f"{table_name}.yaml").write_text(
        yaml.safe_dump(payload, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )


def functional_name(
    table_name: str,
    expected: dict[str, dict[str, str]],
    used: set[str],
) -> str:
    base = strip_layer_prefix(table_name)
    layer = expected.get(table_name, {}).get("layer") or "OTHER"
    table_type = expected.get(table_name, {}).get("table_type") or ""
    if layer == "ODS":
        candidate = f"{base}_source"
    elif layer == "DIM" or table_type == "dimension":
        candidate = f"{base}_profile"
    elif layer == "DWS":
        if any(
            token in base
            for token in (
                "summary",
                "daily",
                "monthly",
                "snapshot",
                "effect",
            )
        ):
            candidate = base
        else:
            candidate = f"{base}_summary"
    elif layer == "ADS":
        if any(
            token in base
            for token in (
                "dashboard",
                "report",
                "alert",
                "topn",
                "rfm",
                "performance",
                "roi",
                "segment",
                "geography",
                "age_group",
                "summary",
            )
        ):
            candidate = base
        else:
            candidate = f"{base}_report"
    elif layer == "DWD":
        if any(
            token in base
            for token in (
                "detail",
                "events",
                "transactions",
                "payments",
                "applications",
                "alerts",
                "reports",
                "assessments",
                "interactions",
            )
        ):
            candidate = base
        else:
            candidate = f"{base}_detail"
    else:
        candidate = base

    candidate = re.sub(r"__+", "_", candidate).strip("_") or table_name
    original = candidate
    index = 2
    while candidate in used:
        candidate = f"{original}_{index}"
        index += 1
    used.add(candidate)
    return candidate


def build_temp_project(
    source_project: str,
    target_project: str,
    tmp_root: Path,
) -> tuple[Path, dict[str, str], dict[str, dict[str, str]]]:
    source_dir = REPO_ROOT / source_project
    target_dir = tmp_root / target_project
    (target_dir / "ads" / "ddl").mkdir(parents=True)
    (target_dir / "mid" / "ddl").mkdir(parents=True)
    (target_dir / "ods" / "ddl" / "internal" / "benchmark").mkdir(
        parents=True
    )
    (target_dir / "ads" / "tasks").mkdir(parents=True)
    (target_dir / "mid" / "tasks").mkdir(parents=True)
    (target_dir / "lineage").mkdir()
    shutil.copy2(
        source_dir / "business_semantics.yaml",
        target_dir / "business_semantics.yaml",
    )
    shutil.copy2(source_dir / "naming_config.yaml", target_dir / "naming_config.yaml")

    expected = load_expected(source_project)
    used: set[str] = set()
    mapping = {
        path.stem: functional_name(path.stem, expected, used)
        for path in ddl_paths(source_project)
    }

    for ddl_path in ddl_paths(source_project):
        new = mapping[ddl_path.stem]
        out_dir = ddl_output_path(target_dir, ddl_path.stem, expected)
        out_dir.mkdir(parents=True, exist_ok=True)
        sanitized_ddl = sanitize_sql(
            ddl_path.read_text(encoding="utf-8"), mapping
        )
        (out_dir / f"{new}.sql").write_text(
            sanitized_ddl,
            encoding="utf-8",
        )
        write_fixed_layer_model_seed(target_dir, new, expected[ddl_path.stem])

    task_source_mapping: dict[str, str] = {}
    for task_root in task_roots(source_project):
        for task_path in sorted(task_root.rglob("*.sql")):
            old = task_path.stem
            target_table = old
            if (
                old.endswith("_full_refresh")
                and old[: -len("_full_refresh")] in mapping
            ):
                target_table = old[: -len("_full_refresh")]
                new = mapping[old[: -len("_full_refresh")]] + "_full_refresh"
            elif old in mapping:
                new = mapping[old]
            else:
                continue
            rel_parent = task_path.parent.relative_to(task_root)
            out_dir = task_output_path(
                target_dir, target_table, expected, rel_parent
            )
            out_dir.mkdir(parents=True, exist_ok=True)
            old_source_file = task_path.relative_to(task_root).as_posix()
            new_source_file = task_path.relative_to(task_root).with_name(
                f"{new}.sql"
            ).as_posix()
            task_source_mapping[old_source_file] = new_source_file
            (out_dir / f"{new}.sql").write_text(
                sanitize_sql(task_path.read_text(encoding="utf-8"), mapping),
                encoding="utf-8",
            )

    lineage_path = source_dir / "lineage" / "lineage_data.json"
    if lineage_path.exists():
        data = json.loads(lineage_path.read_text(encoding="utf-8"))
        data = rewrite_source_files(data, task_source_mapping)
        for table in data.get("tables") or []:
            old = str(table.get("name") or "")
            if old in mapping:
                table["name"] = mapping[old]
                layer = expected_layer(old, expected)
                table["layer"] = layer if layer in FIXED_LAYER_GROUPS else "OTHER"
        raw = replace_table_refs(json.dumps(data, ensure_ascii=False), mapping)
        data = json.loads(raw)
    else:
        data = {
            "tables": [
                {"name": new, "layer": "OTHER"} for new in mapping.values()
            ],
            "edges": [],
            "indirect_edges": [],
        }

    existing_tables = {
        str(table.get("name") or "") for table in data.get("tables") or []
    }
    for new in mapping.values():
        if new not in existing_tables:
            old = {value: key for key, value in mapping.items()}[new]
            layer = expected_layer(old, expected)
            data.setdefault("tables", []).append(
                {
                    "name": new,
                    "layer": layer if layer in FIXED_LAYER_GROUPS else "OTHER",
                }
            )
    (target_dir / "lineage" / "lineage_data.json").write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return target_dir, mapping, expected


def summarize_project(
    *,
    source_project: str,
    target_project: str,
    tmp_root: Path,
    api_key: str,
    model: str,
    base_url: str,
    parallelism: int,
    max_retries: int,
    request_timeout: int,
) -> dict[str, Any]:
    print(f"[{source_project}] preparing temp project", flush=True)
    target_dir, mapping, expected = build_temp_project(
        source_project, target_project, tmp_root
    )
    config.PROJECT_CONFIG[target_project] = {
        "dir": target_project,
        "catalog": "internal",
        "db": "benchmark",
        "naming_config": f"{target_project}/naming_config.yaml",
    }
    reset_config(tmp_root)
    print(
        f"[{source_project}] calling table inspector for middle-layer tables",
        flush=True,
    )
    result = run_direct_model_generation(
        target_project,
        dry_run=False,
        ignore_existing_models=False,
        infer_layer_with_llm=True,
        api_key=api_key,
        model=model,
        base_url=base_url,
        max_retries=max_retries,
        parallelism=parallelism,
        request_timeout=request_timeout,
        no_cache=True,
        show_progress=True,
    )
    cache_path = (
        target_dir / "assess" / "cache" / "table_inspector_layer.json"
    )
    cache = (
        json.loads(cache_path.read_text(encoding="utf-8"))
        if cache_path.exists()
        else {}
    )
    updates_by_new = {update["table"]: update for update in result["model_updates"]}
    reverse = {new: old for old, new in mapping.items()}
    rows = []
    for new, old in sorted(reverse.items(), key=lambda item: item[1]):
        if old not in expected:
            continue
        inspection = (cache.get(new) or {}).get("result") or {}
        reasoning_steps = inspection.get("reasoning_steps") or []
        update = updates_by_new.get(new) or {}
        evaluation_group = (
            "middle" if expected[old]["layer"] in MIDDLE_LAYER_GROUPS else "fixed"
        )
        rows.append(
            {
                "original_table": old,
                "test_table": new,
                "expected_layer": expected[old]["layer"],
                "expected_table_type": expected[old]["table_type"],
                "layer_evaluation_group": evaluation_group,
                "table_inspector_layer": (
                    str(
                        inspection.get("layer")
                        or inspection.get("inferred_layer")
                        or "MISSING"
                    ).upper()
                    if evaluation_group == "middle"
                    else "NOT_RUN"
                ),
                "table_inspector_confidence": inspection.get("confidence"),
                "table_inspector_reason": inspection.get("reason")
                or "；".join(str(step) for step in reasoning_steps[:3]),
                "final_layer": str(update.get("layer") or "MISSING").upper(),
                "final_table_type": update.get("table_type"),
                "layer_source": update.get("layer_assignment_source"),
                "assignment_source": update.get("assignment_source"),
                "metric_count": int(update.get("metric_count") or 0),
                "entity_count": int(update.get("entity_count") or 0),
                "has_grain": bool(update.get("has_grain")),
                "grain_changed": bool(update.get("grain_changed")),
                "metric_generation_source": update.get(
                    "metric_generation_source"
                ),
            }
        )

    table_count = len(rows)
    inspector_rows = [
        row
        for row in rows
        if row["expected_layer"] in MIDDLE_LAYER_GROUPS
    ]
    table_inspector_correct = sum(
        row["table_inspector_layer"] == row["expected_layer"]
        for row in inspector_rows
    )
    final_correct = sum(
        row["final_layer"] == row["expected_layer"] for row in rows
    )
    by_expected = defaultdict(
        lambda: {
            "total": 0,
            "table_inspector_evaluated": 0,
            "table_inspector_correct": 0,
            "final_correct": 0,
        }
    )
    confusion = Counter()
    mismatches = []
    final_layer_counts = Counter()
    final_ads_metric_tables = []
    for row in rows:
        item = by_expected[row["expected_layer"]]
        item["total"] += 1
        if row["expected_layer"] in MIDDLE_LAYER_GROUPS:
            item["table_inspector_evaluated"] += 1
            item["table_inspector_correct"] += int(
                row["table_inspector_layer"] == row["expected_layer"]
            )
        item["final_correct"] += int(row["final_layer"] == row["expected_layer"])
        if row["expected_layer"] in MIDDLE_LAYER_GROUPS:
            confusion[(row["expected_layer"], row["table_inspector_layer"])] += 1
        final_layer_counts[row["final_layer"]] += 1
        if row["final_layer"] == "ADS" and row["metric_count"]:
            final_ads_metric_tables.append(row)
        inspector_mismatch = (
            row["expected_layer"] in MIDDLE_LAYER_GROUPS
            and row["table_inspector_layer"] != row["expected_layer"]
        )
        if inspector_mismatch or row["final_layer"] != row["expected_layer"]:
            mismatches.append(row)

    print(
        f"[{source_project}] table_inspector="
        f"{table_inspector_correct}/{len(inspector_rows)}, "
        f"final={final_correct}/{table_count}, mismatches={len(mismatches)}",
        flush=True,
    )
    return {
        "source_project": source_project,
        "target_project": target_project,
        "tmp_dir": str(target_dir),
        "table_count": table_count,
        "inspected_table_count": result["inspected_table_count"],
        "warning_count": result["warning_count"],
        "warnings": result["warnings"],
        "table_inspector_attempt_count": result.get(
            "table_inspector_layer_inference_attempt_count"
        ),
        "table_inspector_candidate_count": result.get(
            "table_inspector_layer_inference_candidate_count"
        ),
        "table_inspector_used_count": result.get(
            "table_inspector_layer_inference_count"
        ),
        "table_inspector_eval_count": len(inspector_rows),
        "table_inspector_correct_count": table_inspector_correct,
        "table_inspector_accuracy": (
            table_inspector_correct / len(inspector_rows)
            if inspector_rows
            else 0
        ),
        "final_correct_count": final_correct,
        "final_accuracy": final_correct / table_count if table_count else 0,
        "by_expected_layer": dict(by_expected),
        "confusion": {
            f"{key[0]}->{key[1]}": value
            for key, value in sorted(confusion.items())
        },
        "final_layer_counts": dict(sorted(final_layer_counts.items())),
        "metric_count": sum(row["metric_count"] for row in rows),
        "metric_table_count": sum(1 for row in rows if row["metric_count"]),
        "entity_count": sum(row["entity_count"] for row in rows),
        "entity_table_count": sum(1 for row in rows if row["entity_count"]),
        "grain_table_count": sum(1 for row in rows if row["has_grain"]),
        "grain_change_count": sum(1 for row in rows if row["grain_changed"]),
        "final_ads_metric_tables": final_ads_metric_tables,
        "mismatches": mismatches,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    parser.add_argument("--model", default="deepseek-v4-pro")
    parser.add_argument("--base-url", default="https://api.deepseek.com")
    parser.add_argument("--parallel", type=int, default=4)
    parser.add_argument("--max-retries", type=int, default=1)
    parser.add_argument("--request-timeout", type=int, default=240)
    parser.add_argument(
        "--projects",
        nargs="+",
        default=["shop", "finance_analytics"],
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    api_key = os.environ.get("DEEPSEEK_API_KEY")
    if not api_key:
        raise SystemExit("DEEPSEEK_API_KEY is required")

    original_config = dict(config.PROJECT_CONFIG)
    try:
        tmp_root = Path(tempfile.mkdtemp(prefix="dw_full_table_inspector_layer_"))
        config.PROJECT_CONFIG.clear()
        config.PROJECT_CONFIG.update(original_config)
        summaries = []
        for project in args.projects:
            summaries.append(
                summarize_project(
                    source_project=project,
                    target_project=f"{project}_full_no_layer_table_inspector",
                    tmp_root=tmp_root,
                    api_key=api_key,
                    model=args.model,
                    base_url=args.base_url,
                    parallelism=args.parallel,
                    max_retries=args.max_retries,
                    request_timeout=args.request_timeout,
                )
            )
        total = sum(summary["table_count"] for summary in summaries)
        table_inspector_eval_count = sum(
            summary["table_inspector_eval_count"] for summary in summaries
        )
        table_inspector_correct = sum(
            summary["table_inspector_correct_count"] for summary in summaries
        )
        final_correct = sum(
            summary["final_correct_count"] for summary in summaries
        )
        payload = {
            "model": args.model,
            "base_url": args.base_url,
            "parallelism": args.parallel,
            "request_timeout": args.request_timeout,
            "tmp_root": str(tmp_root),
            "total_table_count": total,
            "total_table_inspector_attempt_count": sum(
                summary["table_inspector_attempt_count"]
                for summary in summaries
            ),
            "total_table_inspector_used_count": sum(
                summary["table_inspector_used_count"]
                for summary in summaries
            ),
            "total_table_inspector_eval_count": table_inspector_eval_count,
            "total_table_inspector_correct_count": table_inspector_correct,
            "combined_table_inspector_accuracy": (
                table_inspector_correct / table_inspector_eval_count
                if table_inspector_eval_count
                else 0
            ),
            "total_final_correct_count": final_correct,
            "combined_final_accuracy": final_correct / total if total else 0,
            "total_metric_count": sum(
                summary["metric_count"] for summary in summaries
            ),
            "total_metric_table_count": sum(
                summary["metric_table_count"] for summary in summaries
            ),
            "total_final_ads_metric_table_count": sum(
                len(summary["final_ads_metric_tables"])
                for summary in summaries
            ),
            "projects": summaries,
        }
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(
            json.dumps(
                {
                    "output": str(output),
                    "tmp_root": str(tmp_root),
                    "total_table_count": payload["total_table_count"],
                    "combined_table_inspector_accuracy": payload[
                        "combined_table_inspector_accuracy"
                    ],
                    "combined_final_accuracy": payload["combined_final_accuracy"],
                },
                ensure_ascii=False,
                indent=2,
            ),
            flush=True,
        )
    finally:
        config.PROJECT_CONFIG.clear()
        config.PROJECT_CONFIG.update(original_config)
        reset_config(REPO_ROOT)


if __name__ == "__main__":
    main()
