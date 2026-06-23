#!/usr/bin/env python3
import argparse
import json
import shutil
import sys
import tempfile
import time
from pathlib import Path

import sqlglot

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import config
import lineage.lineage_extractor as lineage_extractor
from benchmarks.lineage_extractor.dataset import (
    CATALOG,
    COMPLEXITIES,
    DATABASE,
    PROFILES,
    PROJECT_NAME,
    generate_dataset,
)


def run_benchmark(
    size="medium",
    complexity="normal",
    parallel=1,
    repeat=1,
    output_path=None,
    asset_dir=None,
    keep_assets=False,
):
    if size not in PROFILES:
        choices = ", ".join(sorted(PROFILES))
        raise ValueError(
            "unknown benchmark size: {} ({})".format(size, choices)
        )
    if complexity not in COMPLEXITIES:
        choices = ", ".join(sorted(COMPLEXITIES))
        raise ValueError(
            "unknown benchmark complexity: {} ({})".format(
                complexity,
                choices,
            )
        )
    repeat = max(1, int(repeat or 1))
    parallel = max(1, int(parallel or 1))
    output_path = Path(output_path) if output_path else None

    managed_root = None
    root = Path(asset_dir) if asset_dir is not None else None
    if root is None:
        managed_root = Path(tempfile.mkdtemp(prefix="lineage-benchmark-"))
        root = managed_root
    root.mkdir(parents=True, exist_ok=True)

    original_config = config.PROJECT_CONFIG.get(PROJECT_NAME)
    original_project = lineage_extractor.CURRENT_PROJECT
    original_catalog = lineage_extractor.CURRENT_CATALOG
    original_db = lineage_extractor.CURRENT_DB

    results = []
    dataset_summary = None
    try:
        config.PROJECT_CONFIG[PROJECT_NAME] = {
            "dir": str(root),
            "catalog": CATALOG,
            "db": DATABASE,
        }
        lineage_extractor.configure_project(PROJECT_NAME)

        for index in range(repeat):
            run_root = root / "run_{:02d}".format(index + 1)
            if run_root.exists():
                shutil.rmtree(str(run_root))
            run_root.mkdir(parents=True)

            result = _run_once(size, complexity, parallel, run_root)
            results.append(result)
            dataset_summary = result.pop("dataset")
    finally:
        if original_config is None:
            config.PROJECT_CONFIG.pop(PROJECT_NAME, None)
        else:
            config.PROJECT_CONFIG[PROJECT_NAME] = original_config
        lineage_extractor.CURRENT_PROJECT = original_project
        lineage_extractor.CURRENT_CATALOG = original_catalog
        lineage_extractor.CURRENT_DB = original_db
        if managed_root is not None and not keep_assets:
            shutil.rmtree(str(managed_root))

    report = {
        "benchmark": "lineage_extractor",
        "size": size,
        "complexity": complexity,
        "parallel": parallel,
        "repeat": repeat,
        "python_version": sys.version.split()[0],
        "sqlglot_version": getattr(sqlglot, "__version__", "unknown"),
        "dataset": dataset_summary,
        "results": results,
    }
    if keep_assets:
        report["asset_dir"] = str(root)

    if output_path is not None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(report, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    return report


def _run_once(size, complexity, parallel, root):
    generated_at = time.perf_counter()
    dataset = generate_dataset(size, root, complexity=complexity)
    generation_seconds = _elapsed(generated_at)

    ddl_texts = [
        path.read_text(encoding=config.TEXT_ENCODING)
        for path in dataset.ddl_files
    ]
    schema_started_at = time.perf_counter()
    schema = lineage_extractor.build_schema_from_texts(
        ddl_texts,
        default_catalog=dataset.catalog,
        default_db=dataset.database,
    )
    schema_build_seconds = _elapsed(schema_started_at)

    actual_table_count = lineage_extractor.schema_table_count(schema)
    if actual_table_count != dataset.table_count:
        raise RuntimeError(
            "generated schema table count mismatch: expected {}, got {}".format(
                dataset.table_count,
                actual_table_count,
            )
        )

    cold_cache_path = root / "cold_task_lineage_cache.json"
    cold_started_at = time.perf_counter()
    cold = lineage_extractor.extract_lineage_from_task_files(
        dataset.task_files,
        dataset.tasks_dir,
        schema,
        parallel=parallel,
        previous_cache_file=cold_cache_path,
        cache_project=dataset.project_name,
    )
    cold_extraction_seconds = _elapsed(cold_started_at)
    _raise_on_fatal("cold extraction", cold["errors"])

    cold_cache_path.write_text(
        json.dumps(cold["task_cache"], ensure_ascii=False, indent=2),
        encoding=config.TEXT_ENCODING,
    )

    warm_started_at = time.perf_counter()
    warm = lineage_extractor.extract_lineage_from_task_files(
        dataset.task_files,
        dataset.tasks_dir,
        schema,
        parallel=parallel,
        previous_cache_file=cold_cache_path,
        cache_project=dataset.project_name,
    )
    warm_extraction_seconds = _elapsed(warm_started_at)
    _raise_on_fatal("warm extraction", warm["errors"])

    warm_cache_hits = sum(
        1 for result in warm["task_results"] if result.get("cache_hit")
    )
    if warm_cache_hits != dataset.task_count:
        raise RuntimeError(
            "warm cache hit mismatch: expected {}, got {}".format(
                dataset.task_count,
                warm_cache_hits,
            )
        )

    output_started_at = time.perf_counter()
    cold_output = lineage_extractor.build_lineage_output(
        cold["lineage"],
        schema,
        transient_tables=cold["transient_tables"],
    )
    output_build_seconds = _elapsed(output_started_at)
    warm_output = lineage_extractor.build_lineage_output(
        warm["lineage"],
        schema,
        transient_tables=warm["transient_tables"],
    )
    if len(cold_output["edges"]) != len(warm_output["edges"]):
        raise RuntimeError(
            "cold and warm edge counts differ: {} != {}".format(
                len(cold_output["edges"]),
                len(warm_output["edges"]),
            )
        )
    if len(cold_output["edges"]) < dataset.expected_min_edges:
        raise RuntimeError(
            "lineage output is incomplete: expected at least {} edges, got {}".format(
                dataset.expected_min_edges,
                len(cold_output["edges"]),
            )
        )

    direct_edges = sum(
        1
        for edge in cold_output["edges"]
        if edge.get("relation_type") == "direct"
    )
    indirect_edges = len(cold_output["edges"]) - direct_edges
    diagnostics = list(cold["errors"]) + list(warm["errors"])

    return {
        "dataset": {
            "tables": dataset.table_count,
            "tasks": dataset.task_count,
            "columns": dataset.column_count,
        },
        "generation_seconds": generation_seconds,
        "schema_build_seconds": schema_build_seconds,
        "cold_extraction_seconds": cold_extraction_seconds,
        "warm_extraction_seconds": warm_extraction_seconds,
        "output_build_seconds": output_build_seconds,
        "direct_edges": direct_edges,
        "indirect_edges": indirect_edges,
        "warnings": _diagnostic_count(diagnostics, "warning"),
        "errors": _diagnostic_count(diagnostics, "error"),
        "warm_cache_hits": warm_cache_hits,
    }


def _raise_on_fatal(label, diagnostics):
    fatal = lineage_extractor._fatal_diagnostics(diagnostics)
    if fatal:
        first = fatal[0]
        raise RuntimeError(
            "{} failed with {} fatal diagnostics; first: {}".format(
                label,
                len(fatal),
                first,
            )
        )


def _diagnostic_count(diagnostics, severity):
    return sum(
        1 for item in diagnostics if item.get("severity", "error") == severity
    )


def _elapsed(started_at):
    return round(time.perf_counter() - started_at, 6)


def _print_report(report):
    print("lineage_extractor benchmark")
    print("  size: {}".format(report["size"]))
    print("  complexity: {}".format(report["complexity"]))
    print("  parallel: {}".format(report["parallel"]))
    print("  repeat: {}".format(report["repeat"]))
    dataset = report["dataset"]
    print(
        "  dataset: {tables} tables, {tasks} tasks, {columns} columns".format(
            **dataset
        )
    )
    for index, result in enumerate(report["results"], start=1):
        print(
            "  run {index}: cold={cold:.3f}s warm={warm:.3f}s "
            "output={output:.3f}s edges={edges} cache_hits={hits}".format(
                index=index,
                cold=result["cold_extraction_seconds"],
                warm=result["warm_extraction_seconds"],
                output=result["output_build_seconds"],
                edges=result["direct_edges"] + result["indirect_edges"],
                hits=result["warm_cache_hits"],
            )
        )
    if report.get("asset_dir"):
        print("  assets: {}".format(report["asset_dir"]))


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Run lineage_extractor benchmark profiles."
    )
    parser.add_argument(
        "--size",
        default="medium",
        choices=sorted(PROFILES),
        help="Benchmark size profile.",
    )
    parser.add_argument(
        "--parallel",
        type=int,
        default=1,
        help="Task extraction parallelism.",
    )
    parser.add_argument(
        "--complexity",
        default="normal",
        choices=sorted(COMPLEXITIES),
        help="Task SQL complexity profile.",
    )
    parser.add_argument(
        "--repeat",
        type=int,
        default=1,
        help="Number of benchmark repetitions.",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Optional JSON report path.",
    )
    parser.add_argument(
        "--asset-dir",
        default=None,
        help="Directory for generated benchmark assets.",
    )
    parser.add_argument(
        "--keep-assets",
        action="store_true",
        help="Keep generated benchmark assets after the run.",
    )
    args = parser.parse_args(argv)
    report = run_benchmark(
        size=args.size,
        complexity=args.complexity,
        parallel=args.parallel,
        repeat=args.repeat,
        output_path=args.output,
        asset_dir=args.asset_dir,
        keep_assets=args.keep_assets,
    )
    _print_report(report)
    return report


if __name__ == "__main__":
    main()
