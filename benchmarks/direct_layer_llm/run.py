#!/usr/bin/env python3
from __future__ import annotations

import argparse
import inspect
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

import config  # noqa: E402
import assess.llm.model_metadata_writer as writer  # noqa: E402
from assess.llm.context_builder import build_contexts  # noqa: E402
from assess.llm.table_inspector import TableInspector  # noqa: E402

LAYER_PREFIXES = ("ods_", "dwd_", "dws_", "ads_", "dim_")
RUNNERS = ("direct", "table-inspector", "both")


def reset_config(project_root: Path) -> None:
    config.PROJECT_ROOT = project_root
    writer.PROJECT_ROOT = project_root
    config._naming_config_cache.clear()
    config._model_metadata_cache.clear()
    config._business_semantics_cache.clear()


def strip_layer_prefix(name: str) -> str:
    for prefix in LAYER_PREFIXES:
        if name.startswith(prefix):
            return name[len(prefix) :]
    return name


def sanitize_text(text: str) -> str:
    text = re.sub(r"\b(ODS|DWD|DWS|ADS|DIM)\b\s*", "", text)
    return re.sub(r"\b(ods|dwd|dws|ads|dim)\b\s*", "", text)


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


def model_paths(project: str) -> list[Path]:
    project_dir = REPO_ROOT / project
    paths = list((project_dir / "models").glob("*.yaml"))
    paths += list((project_dir / "ods" / "models").glob("*/*/*.yaml"))
    return sorted(paths)


def ddl_paths(project: str) -> list[Path]:
    project_dir = REPO_ROOT / project
    paths = list((project_dir / "ddl").glob("*.sql"))
    paths += list((project_dir / "ods" / "ddl").glob("*/*/*.sql"))
    return sorted(paths)


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


def configure_temp_project(
    *,
    source_project: str,
    target_project: str,
) -> None:
    config.PROJECT_CONFIG[target_project] = {
        "dir": target_project,
        "catalog": "internal",
        "db": config.PROJECT_CONFIG[source_project].get("db", ""),
        "naming_config": f"{target_project}/naming_config.yaml",
    }


def accuracy_stats(
    rows: list[dict[str, Any]],
    *,
    predicted_layer_key: str,
    final_layer_key: str = "",
) -> dict[str, Any]:
    table_count = len(rows)
    predicted_correct = sum(
        row[predicted_layer_key] == row["expected_layer"] for row in rows
    )
    final_correct = (
        sum(row[final_layer_key] == row["expected_layer"] for row in rows)
        if final_layer_key
        else 0
    )
    by_expected = defaultdict(
        lambda: {"total": 0, "predicted_correct": 0, "final_correct": 0}
    )
    confusion = Counter()
    mismatches = []
    for row in rows:
        item = by_expected[row["expected_layer"]]
        item["total"] += 1
        item["predicted_correct"] += int(
            row[predicted_layer_key] == row["expected_layer"]
        )
        if final_layer_key:
            item["final_correct"] += int(
                row[final_layer_key] == row["expected_layer"]
            )
        confusion[(row["expected_layer"], row[predicted_layer_key])] += 1
        if row[predicted_layer_key] != row["expected_layer"] or (
            final_layer_key and row[final_layer_key] != row["expected_layer"]
        ):
            mismatches.append(row)

    return {
        "table_count": table_count,
        "predicted_correct": predicted_correct,
        "final_correct": final_correct,
        "predicted_accuracy": (
            predicted_correct / table_count if table_count else 0
        ),
        "final_accuracy": (
            final_correct / table_count
            if table_count and final_layer_key
            else 0
        ),
        "by_expected_layer": {
            key: dict(value) for key, value in by_expected.items()
        },
        "confusion": {
            f"{key[0]}->{key[1]}": value
            for key, value in sorted(confusion.items())
        },
        "mismatches": mismatches,
    }


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
    (target_dir / "ddl").mkdir(parents=True)
    (target_dir / "tasks").mkdir()
    (target_dir / "lineage").mkdir()
    shutil.copy2(
        source_dir / "business_semantics.yaml",
        target_dir / "business_semantics.yaml",
    )
    shutil.copy2(
        source_dir / "naming_config.yaml",
        target_dir / "naming_config.yaml",
    )

    expected = load_expected(source_project)
    used: set[str] = set()
    mapping = {
        path.stem: functional_name(path.stem, expected, used)
        for path in ddl_paths(source_project)
    }

    for ddl_path in ddl_paths(source_project):
        new = mapping[ddl_path.stem]
        (target_dir / "ddl" / f"{new}.sql").write_text(
            replace_table_refs(ddl_path.read_text(encoding="utf-8"), mapping),
            encoding="utf-8",
        )

    for task_path in sorted((source_dir / "tasks").rglob("*.sql")):
        old = task_path.stem
        if (
            old.endswith("_full_refresh")
            and old[: -len("_full_refresh")] in mapping
        ):
            new = mapping[old[: -len("_full_refresh")]] + "_full_refresh"
        elif old in mapping:
            new = mapping[old]
        else:
            continue
        rel_parent = task_path.parent.relative_to(source_dir / "tasks")
        out_dir = target_dir / "tasks" / rel_parent
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / f"{new}.sql").write_text(
            replace_table_refs(task_path.read_text(encoding="utf-8"), mapping),
            encoding="utf-8",
        )

    lineage_path = source_dir / "lineage" / "lineage_data.json"
    if lineage_path.exists():
        data = json.loads(lineage_path.read_text(encoding="utf-8"))
        for table in data.get("tables") or []:
            old = str(table.get("name") or "")
            if old in mapping:
                table["name"] = mapping[old]
                table["layer"] = "OTHER"
        raw = replace_table_refs(json.dumps(data, ensure_ascii=False), mapping)
        data = json.loads(raw)
    else:
        print(
            f"[{source_project}] warning: {lineage_path} not found; "
            "using table-only lineage data with no edges",
            flush=True,
        )
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
            data.setdefault("tables", []).append(
                {"name": new, "layer": "OTHER"}
            )
    (target_dir / "lineage" / "lineage_data.json").write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return target_dir, mapping, expected


def summarize_project_with_direct_generation(
    *,
    source_project: str,
    target_project: str,
    tmp_root: Path,
    api_key: str,
    model: str,
    base_url: str,
    parallelism: int,
    max_retries: int,
) -> dict[str, Any]:
    try:
        from assess.llm.model_metadata_writer import run_direct_model_generation
    except ImportError as exc:
        raise SystemExit(
            "direct runner is unavailable on this branch because "
            "assess.llm.model_metadata_writer.run_direct_model_generation "
            "is not present; use --runner table-inspector instead"
        ) from exc

    print(f"[{source_project}] preparing temp project", flush=True)
    target_dir, mapping, expected = build_temp_project(
        source_project, target_project, tmp_root
    )
    configure_temp_project(
        source_project=source_project,
        target_project=target_project,
    )
    reset_config(tmp_root)
    print(
        f"[{source_project}] direct runner calling LLM "
        f"for {len(mapping)} tables",
        flush=True,
    )
    result = run_direct_model_generation(
        target_project,
        dry_run=True,
        ignore_existing_models=True,
        infer_layer_with_llm=True,
        api_key=api_key,
        model=model,
        base_url=base_url,
        max_retries=max_retries,
        parallelism=parallelism,
        no_cache=True,
        show_progress=True,
    )
    cache_path = target_dir / "assess" / "cache" / "direct_layer.json"
    cache = (
        json.loads(cache_path.read_text(encoding="utf-8"))
        if cache_path.exists()
        else {}
    )
    updates_by_new = {
        update["table"]: update for update in result["model_updates"]
    }
    reverse = {new: old for old, new in mapping.items()}
    rows = []
    for new, old in sorted(reverse.items(), key=lambda item: item[1]):
        if old not in expected:
            continue
        llm = (cache.get(new) or {}).get("result") or {}
        update = updates_by_new.get(new) or {}
        rows.append(
            {
                "original_table": old,
                "test_table": new,
                "expected_layer": expected[old]["layer"],
                "expected_table_type": expected[old]["table_type"],
                "llm_layer": str(llm.get("layer") or "MISSING").upper(),
                "llm_confidence": llm.get("confidence"),
                "llm_reason": llm.get("reason"),
                "final_layer": str(update.get("layer") or "MISSING").upper(),
                "final_table_type": update.get("table_type"),
                "layer_source": update.get("layer_assignment_source"),
            }
        )

    stats = accuracy_stats(
        rows,
        predicted_layer_key="llm_layer",
        final_layer_key="final_layer",
    )
    for item in stats["by_expected_layer"].values():
        item["llm_correct"] = item.pop("predicted_correct")
        item["final_correct"] = item.pop("final_correct")

    print(
        f"[{source_project}] direct llm="
        f"{stats['predicted_correct']}/{stats['table_count']}, "
        f"final={stats['final_correct']}/{stats['table_count']}, "
        f"mismatches={len(stats['mismatches'])}",
        flush=True,
    )
    return {
        "runner": "direct",
        "source_project": source_project,
        "target_project": target_project,
        "tmp_dir": str(target_dir),
        "table_count": stats["table_count"],
        "inspected_table_count": result["inspected_table_count"],
        "warning_count": result["warning_count"],
        "warnings": result["warnings"],
        "llm_attempt_count": result.get("llm_layer_inference_attempt_count"),
        "llm_used_count": result.get("llm_layer_inference_count"),
        "llm_correct": stats["predicted_correct"],
        "final_correct": stats["final_correct"],
        "llm_accuracy": stats["predicted_accuracy"],
        "final_accuracy": stats["final_accuracy"],
        "by_expected_layer": stats["by_expected_layer"],
        "confusion": stats["confusion"],
        "mismatches": stats["mismatches"],
    }


def summarize_project_with_table_inspector(
    *,
    source_project: str,
    target_project: str,
    tmp_root: Path,
    api_key: str,
    model: str,
    base_url: str,
    parallelism: int,
    max_retries: int,
) -> dict[str, Any]:
    print(f"[{source_project}] preparing temp project", flush=True)
    target_dir, mapping, expected = build_temp_project(
        source_project, target_project, tmp_root
    )
    configure_temp_project(
        source_project=source_project,
        target_project=target_project,
    )
    reset_config(tmp_root)

    lineage_data = json.loads(
        (target_dir / "lineage" / "lineage_data.json").read_text(
            encoding="utf-8"
        )
    )
    contexts = build_contexts(target_project, lineage_data, layers={"OTHER"})
    contexts_by_table = {ctx.table_name: ctx for ctx in contexts}
    cache_path = (
        target_dir / "assess" / "cache" / "table_inspector_layer.json"
    )
    if cache_path.exists():
        cache_path.unlink()
    inspector_kwargs = {
        "api_key": api_key,
        "model": model,
        "cache_file": cache_path,
        "max_retries": max_retries,
        "parallelism": parallelism,
    }
    if "base_url" in inspect.signature(TableInspector).parameters:
        inspector_kwargs["base_url"] = base_url
    inspector = TableInspector(**inspector_kwargs)

    print(
        f"[{source_project}] table-inspector runner calling LLM "
        f"for {len(contexts)} tables",
        flush=True,
    )

    def on_progress(event: dict[str, Any]) -> None:
        if event.get("event") not in {"api_call", "cache_hit", "finish"}:
            return
        table = event.get("table")
        index = event.get("index")
        total = event.get("total")
        if event.get("event") == "finish":
            print(
                f"{table} table-inspector ({index}/{total}) "
                f"-> {event.get('status')}",
                flush=True,
            )
        elif event.get("event") == "cache_hit":
            print(
                f"{table} table-inspector cache ({index}/{total})",
                flush=True,
            )
        else:
            print(
                f"{table} table-inspector ({index}/{total})",
                flush=True,
            )

    inspector.progress_callback = on_progress
    results = inspector.inspect_batch(contexts)
    results_by_table = {result.table_name: result for result in results}
    reverse = {new: old for old, new in mapping.items()}
    rows = []
    for new, old in sorted(reverse.items(), key=lambda item: item[1]):
        if old not in expected:
            continue
        result = results_by_table.get(new)
        ctx = contexts_by_table.get(new)
        rows.append(
            {
                "original_table": old,
                "test_table": new,
                "expected_layer": expected[old]["layer"],
                "expected_table_type": expected[old]["table_type"],
                "declared_layer": ctx.layer if ctx else "MISSING",
                "inspector_layer": (
                    str(result.inferred_layer or "MISSING").upper()
                    if result
                    else "MISSING"
                ),
                "inspector_table_type": (
                    result.table_type if result else "missing"
                ),
                "inspector_confidence": (
                    result.confidence if result else 0.0
                ),
                "inspector_status": result.status if result else "missing",
                "inspector_retry_count": (
                    result.retry_count if result else 0
                ),
                "inspector_reasoning_steps": (
                    result.reasoning_steps if result else []
                ),
            }
        )

    stats = accuracy_stats(rows, predicted_layer_key="inspector_layer")
    for item in stats["by_expected_layer"].values():
        item["inspector_correct"] = item.pop("predicted_correct")
        item.pop("final_correct", None)

    blocked_count = sum(
        1 for result in results if result.status == "blocked"
    )
    warning_count = sum(
        1 for result in results if result.status == "warning"
    )
    print(
        f"[{source_project}] table-inspector="
        f"{stats['predicted_correct']}/{stats['table_count']}, "
        f"mismatches={len(stats['mismatches'])}, "
        f"blocked={blocked_count}, warning={warning_count}",
        flush=True,
    )
    return {
        "runner": "table-inspector",
        "source_project": source_project,
        "target_project": target_project,
        "tmp_dir": str(target_dir),
        "table_count": stats["table_count"],
        "inspected_table_count": len(results),
        "warning_count": warning_count,
        "blocked_count": blocked_count,
        "inspector_correct": stats["predicted_correct"],
        "inspector_accuracy": stats["predicted_accuracy"],
        "by_expected_layer": stats["by_expected_layer"],
        "confusion": stats["confusion"],
        "mismatches": stats["mismatches"],
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    parser.add_argument("--model", default="deepseek-v4-pro")
    parser.add_argument("--base-url", default="https://api.deepseek.com")
    parser.add_argument("--parallel", type=int, default=4)
    parser.add_argument("--max-retries", type=int, default=1)
    parser.add_argument("--runner", choices=RUNNERS, default="table-inspector")
    parser.add_argument(
        "--projects",
        nargs="+",
        default=["shop", "finance_analytics"],
    )
    return parser.parse_args()


def aggregate_direct_summaries(
    summaries: list[dict[str, Any]],
) -> dict[str, Any]:
    total = sum(summary["table_count"] for summary in summaries)
    llm_correct = sum(summary["llm_correct"] for summary in summaries)
    final_correct = sum(summary["final_correct"] for summary in summaries)
    return {
        "total_table_count": total,
        "total_llm_attempt_count": sum(
            summary["llm_attempt_count"] or 0 for summary in summaries
        ),
        "total_llm_used_count": sum(
            summary["llm_used_count"] or 0 for summary in summaries
        ),
        "combined_llm_accuracy": llm_correct / total if total else 0,
        "combined_final_accuracy": final_correct / total if total else 0,
        "projects": summaries,
    }


def aggregate_table_inspector_summaries(
    summaries: list[dict[str, Any]],
) -> dict[str, Any]:
    total = sum(summary["table_count"] for summary in summaries)
    inspector_correct = sum(
        summary["inspector_correct"] for summary in summaries
    )
    return {
        "total_table_count": total,
        "total_warning_count": sum(
            summary["warning_count"] for summary in summaries
        ),
        "total_blocked_count": sum(
            summary["blocked_count"] for summary in summaries
        ),
        "combined_inspector_accuracy": (
            inspector_correct / total if total else 0
        ),
        "projects": summaries,
    }


def runner_names(selected: str) -> list[str]:
    if selected == "both":
        return ["direct", "table-inspector"]
    return [selected]


def run_project_summary(
    *,
    runner: str,
    project: str,
    tmp_root: Path,
    api_key: str,
    model: str,
    base_url: str,
    parallelism: int,
    max_retries: int,
) -> dict[str, Any]:
    if runner == "direct":
        return summarize_project_with_direct_generation(
            source_project=project,
            target_project=f"{project}_full_no_layer_llm",
            tmp_root=tmp_root,
            api_key=api_key,
            model=model,
            base_url=base_url,
            parallelism=parallelism,
            max_retries=max_retries,
        )
    return summarize_project_with_table_inspector(
        source_project=project,
        target_project=f"{project}_full_no_layer_table_inspector",
        tmp_root=tmp_root,
        api_key=api_key,
        model=model,
        base_url=base_url,
        parallelism=parallelism,
        max_retries=max_retries,
    )


def aggregate_runner(
    runner: str,
    summaries: list[dict[str, Any]],
) -> dict[str, Any]:
    if runner == "direct":
        return aggregate_direct_summaries(summaries)
    return aggregate_table_inspector_summaries(summaries)


def console_summary(payload: dict[str, Any]) -> dict[str, Any]:
    summary = {
        "output": payload["output"],
        "runner": payload["runner"],
        "tmp_root": payload["tmp_root"],
    }
    if payload["runner"] == "direct":
        summary.update(
            {
                "total_table_count": payload["total_table_count"],
                "combined_llm_accuracy": payload["combined_llm_accuracy"],
                "combined_final_accuracy": payload[
                    "combined_final_accuracy"
                ],
            }
        )
    elif payload["runner"] == "table-inspector":
        summary.update(
            {
                "total_table_count": payload["total_table_count"],
                "combined_inspector_accuracy": payload[
                    "combined_inspector_accuracy"
                ],
                "total_blocked_count": payload["total_blocked_count"],
            }
        )
    else:
        for runner, runner_payload in payload["runners"].items():
            if runner == "direct":
                summary["direct_accuracy"] = runner_payload[
                    "combined_final_accuracy"
                ]
            else:
                summary["table_inspector_accuracy"] = runner_payload[
                    "combined_inspector_accuracy"
                ]
    return summary


def main() -> None:
    args = parse_args()
    api_key = os.environ.get("DEEPSEEK_API_KEY")
    if not api_key:
        raise SystemExit("DEEPSEEK_API_KEY is required")

    original_config = dict(config.PROJECT_CONFIG)
    try:
        tmp_root = Path(tempfile.mkdtemp(prefix="dw_full_llm_layer_"))
        config.PROJECT_CONFIG.clear()
        config.PROJECT_CONFIG.update(original_config)
        runner_payloads = {}
        for runner in runner_names(args.runner):
            summaries = []
            for project in args.projects:
                summaries.append(
                    run_project_summary(
                        runner=runner,
                        project=project,
                        tmp_root=tmp_root,
                        api_key=api_key,
                        model=args.model,
                        base_url=args.base_url,
                        parallelism=args.parallel,
                        max_retries=args.max_retries,
                    )
                )
            runner_payloads[runner] = aggregate_runner(runner, summaries)

        payload: dict[str, Any] = {
            "model": args.model,
            "base_url": args.base_url,
            "parallelism": args.parallel,
            "runner": args.runner,
            "tmp_root": str(tmp_root),
        }
        if args.runner == "both":
            payload["runners"] = runner_payloads
        else:
            payload.update(runner_payloads[args.runner])

        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        payload["output"] = str(output)
        output.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(
            json.dumps(
                console_summary(payload),
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
