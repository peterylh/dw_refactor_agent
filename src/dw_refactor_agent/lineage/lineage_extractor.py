#!/usr/bin/env python3
"""
通用字段级 SQL 血缘采集器
使用 sqlglot.lineage() 替代手写 AST 遍历
支持: INSERT, UPDATE, CTAS, CREATE VIEW, SELECT INTO, MERGE
"""

import argparse
import json
import logging
import re
import sys
from concurrent.futures import (
    ProcessPoolExecutor as ProcessPoolExecutor,
)
from concurrent.futures import as_completed as as_completed
from pathlib import Path
from typing import TYPE_CHECKING

_src_root = Path(__file__).resolve().parents[2]
if str(_src_root) not in sys.path:
    sys.path.insert(0, str(_src_root))

import sqlglot as sqlglot
from sqlglot.lineage import build_scope as build_lineage_scope  # noqa: F401
from sqlglot.lineage import lineage as lineage
from sqlglot.lineage import qualify as lineage_qualify  # noqa: F401

from dw_refactor_agent.config import (
    PROJECT_CONFIG,
    TEXT_ENCODING,
    iter_project_task_files,
    lineage_data_path,
    lineage_task_cache_path,
    task_source_file,
)
from dw_refactor_agent.config import (
    determine_layer as determine_config_layer,  # noqa: F401
)
from dw_refactor_agent.config import (
    ods_source_catalog_ddl_dialect as ods_source_catalog_ddl_dialect,
)
from dw_refactor_agent.config import (
    project_asset_dirs as project_asset_dirs,
)
from dw_refactor_agent.config import (
    project_dir as configured_project_dir,
)
from dw_refactor_agent.config import (
    project_ods_asset_dirs as project_ods_asset_dirs,
)
from dw_refactor_agent.lineage.identifiers import (
    canonical_identifier,
    canonical_qualified_identifier,
    display_table_name,
    identifier_match_key,
    qualified_table_name,
    schema_table_match_key,
    table_identity,
    table_identity_match_key,
)
from dw_refactor_agent.lineage.sql_task_facts import (
    extract_task_table_facts as extract_task_table_facts,
)
from dw_refactor_agent.lineage.sql_task_facts import (
    extract_task_table_facts_from_statements as extract_task_table_facts_from_statements,
)
from dw_refactor_agent.sql.doris import (
    normalize_create_table_for_sqlglot as normalize_create_table_for_sqlglot,
)

if TYPE_CHECKING:
    from dw_refactor_agent.lineage.lineage_output import (
        build_lineage_output,
        format_layer_statistics,
        format_lineage_output_statistics,
        warn_jobs_with_multiple_non_process_outputs,
    )
    from dw_refactor_agent.lineage.lineage_schema import (
        build_schema_from_project_ddl,
        schema_table_count,
    )
    from dw_refactor_agent.lineage.lineage_tasks import (
        _reset_stats,
        extract_lineage_from_task_files,
    )
    from dw_refactor_agent.lineage.lineage_trace import (
        _diagnostics_by_source_file,
        _fatal_diagnostics,
        _format_diagnostic,
        _should_write_lineage_output,
        format_missing_ddl_warnings,
    )

AGGREGATE_PATTERN = re.compile(
    r"\b(SUM|COUNT|AVG|MIN|MAX)\s*\(",
    flags=re.IGNORECASE,
)
DROP_TABLE_FORCE_PATTERN = re.compile(
    r"(\bDROP\s+TABLE\b[^;]*?)\s+FORCE(\s*(?:;|$))",
    flags=re.IGNORECASE,
)


# ============================================================
# 0. 项目配置
# ============================================================

CURRENT_PROJECT = "shop"
CURRENT_CATALOG = "internal"
CURRENT_DB = "shop_dm"
LINEAGE_DIALECT = "doris, normalization_strategy=lowercase"
DDL_DIALECTS_WITH_PARTITIONED_BY = {"hive", "spark"}
LOGGER = logging.getLogger(__name__)


def configure_project(project_name):
    global CURRENT_PROJECT, CURRENT_CATALOG, CURRENT_DB
    cfg = PROJECT_CONFIG.get(project_name)
    if not cfg:
        raise ValueError(
            f"未知项目: {project_name}, 可选: {list(PROJECT_CONFIG.keys())}"
        )
    CURRENT_PROJECT = project_name
    CURRENT_CATALOG = cfg.get("catalog", "internal")
    CURRENT_DB = cfg["db"]


def _sqlglot_task_sql(sql_text):
    """Remove Doris task syntax that sqlglot cannot parse."""
    return DROP_TABLE_FORCE_PATTERN.sub(r"\1\2", str(sql_text or ""))


def _canonical_identifier(name):
    """Return the logical identifier name without SQL quote wrappers."""
    return canonical_identifier(name)


def _identifier_match_key(name):
    return identifier_match_key(name)


def _canonical_qualified_identifier(name):
    return canonical_qualified_identifier(name)


def _default_catalog():
    return _canonical_identifier(CURRENT_CATALOG) or "internal"


def _default_db():
    return _canonical_identifier(CURRENT_DB)


def _table_identity(name, default_catalog=None, default_db=None):
    """Return (catalog, database, table), filling project defaults as needed."""
    return table_identity(
        name,
        default_catalog=default_catalog or _default_catalog(),
        default_db=default_db or _default_db(),
    )


def _schema_table_match_key(catalog, database, table):
    return schema_table_match_key(catalog, database, table)


def _table_identity_match_key(name, default_catalog=None, default_db=None):
    return table_identity_match_key(
        name,
        default_catalog=default_catalog or _default_catalog(),
        default_db=default_db or _default_db(),
    )


def _qualified_table_name(catalog, database, table):
    return qualified_table_name(catalog, database, table)


def _display_table_name(name, strip_current_db=False):
    """Format a table name for output, hiding the default internal catalog."""
    return display_table_name(
        name,
        default_catalog=_default_catalog(),
        default_db=_default_db(),
        strip_current_db=strip_current_db,
    )


def _strip_db(name):
    return _display_table_name(name, strip_current_db=True)


def _canonical_column(name):
    return _canonical_identifier(name)


from dw_refactor_agent.lineage import lineage_output as _lineage_output
from dw_refactor_agent.lineage import lineage_projection as _lineage_projection
from dw_refactor_agent.lineage import lineage_schema as _lineage_schema_module
from dw_refactor_agent.lineage import lineage_tasks as _lineage_tasks
from dw_refactor_agent.lineage import lineage_trace as _lineage_trace

__lineage_runtime__ = sys.modules[__name__]
_LINEAGE_RUNTIME = __lineage_runtime__


def _call_projection(name, *args, **kwargs):
    return _lineage_projection.call(name, _LINEAGE_RUNTIME, *args, **kwargs)


def _call_output(name, *args, **kwargs):
    return _lineage_output.call(name, _LINEAGE_RUNTIME, *args, **kwargs)


STATS = {"parse_failures": 0, "lineage_failures": 0}


class TaskWorkItem(_lineage_tasks.TaskWorkItem):
    """Compatibility task work item with a facade-stable pickle identity."""


class ParsedTaskContext(_lineage_tasks.ParsedTaskContext):
    """Compatibility parsed context with a facade-stable pickle identity."""


class _SchemaLookup(_lineage_schema_module._SchemaLookup):
    """Compatibility schema lookup owned by this extractor facade."""


_lineage_schema_module.install_facade(globals())
_lineage_projection.install_facade(globals())
_lineage_trace.install_facade(globals())
_lineage_tasks.install_facade(globals())
_lineage_output.install_facade(globals())


def main():
    logging.basicConfig(
        level=logging.WARNING, format="%(levelname)s: %(message)s"
    )
    parser = argparse.ArgumentParser(description="SQL 血缘采集器")
    parser.add_argument(
        "--project",
        default="shop",
        choices=list(PROJECT_CONFIG.keys()),
        help="项目名称, 对应 PROJECT_CONFIG 中的 key",
    )
    parser.add_argument(
        "--parallel",
        type=int,
        default=1,
        help="task 文件级并行度, 默认 1",
    )
    parser.add_argument(
        "--force-overwrite-on-error",
        action="store_true",
        help="存在严重错误时仍覆盖写出 lineage_data 文件",
    )
    parser.add_argument(
        "--output",
        default=None,
        help=(
            "血缘 JSON 输出文件; 默认使用 warehouses/{project}/artifacts/lineage/lineage_data.json"
        ),
    )
    parser.add_argument(
        "--cache-file",
        default=None,
        help=(
            "task 级血缘缓存文件; 默认使用 "
            "warehouses/{project}/artifacts/lineage/task_lineage_cache.json"
        ),
    )
    parser.add_argument(
        "--no-cache",
        action="store_true",
        help="禁用 task 级血缘缓存",
    )
    args = parser.parse_args()
    configure_project(args.project)
    _reset_stats()
    project_dir = configured_project_dir(args.project)
    if project_dir is None:
        raise KeyError(f"未知项目: {args.project}")
    # 1. 构建 Schema
    schema = build_schema_from_project_ddl(args.project)
    table_count = schema_table_count(schema)
    print(f"Schema: {table_count} 个表")

    # 2. 提取血缘
    all_lineage = []
    task_files = iter_project_task_files(
        args.project,
        include_full_refresh=False,
    )

    parallel = max(1, int(args.parallel or 1))
    print(f"Tasks: {len(task_files)} 个文件, 并行度: {parallel}")

    def print_task_progress(completed, total, task_result):
        entries = task_result["entries"]
        diagnostics = task_result.get("errors") or []
        fatal_count = len(_fatal_diagnostics(diagnostics))
        warning_count = len(diagnostics) - fatal_count
        diagnostic_parts = []
        if task_result.get("cache_hit"):
            diagnostic_parts.append("cache hit")
        if fatal_count:
            diagnostic_parts.append(f"{fatal_count} 个错误")
        if warning_count:
            diagnostic_parts.append(f"{warning_count} 个警告")
        diagnostic_text = (
            f", {', '.join(diagnostic_parts)}" if diagnostic_parts else ""
        )
        print(
            f"  [{completed}/{total}] {task_result['source_file']}: "
            f"{len(entries)} 条血缘{diagnostic_text}"
        )

    cache_path = None
    if not args.no_cache:
        cache_path = (
            Path(args.cache_file)
            if args.cache_file
            else lineage_task_cache_path(CURRENT_PROJECT)
        )

    extraction_result = extract_lineage_from_task_files(
        task_files,
        project_dir,
        schema,
        parallel=parallel,
        progress_callback=print_task_progress,
        previous_cache_file=cache_path,
        cache_project=CURRENT_PROJECT,
        source_file_for_path=lambda path: task_source_file(
            CURRENT_PROJECT,
            path,
        ),
    )
    all_lineage = extraction_result["lineage"]
    warning_lines = format_missing_ddl_warnings(
        extraction_result["task_results"],
        extraction_result["missing_ddl_tables"],
    )
    if warning_lines:
        print()
        for line in warning_lines:
            print(line)

    output_path = (
        Path(args.output)
        if args.output
        else lineage_data_path(CURRENT_PROJECT)
    )
    output_paths = [output_path]

    diagnostics = extraction_result["errors"]
    fatal_diagnostics = _fatal_diagnostics(diagnostics)
    if diagnostics:
        print()
        print("诊断明细:")
        for source_file, source_diagnostics in sorted(
            _diagnostics_by_source_file(diagnostics).items()
        ):
            source_fatal_count = len(_fatal_diagnostics(source_diagnostics))
            source_warning_count = len(source_diagnostics) - source_fatal_count
            print(
                f"  {source_file}: "
                f"{source_fatal_count} 个错误, "
                f"{source_warning_count} 个警告"
            )
            for diagnostic in source_diagnostics[:5]:
                print(f"    - {_format_diagnostic(diagnostic)}")
            if len(source_diagnostics) > 5:
                print(f"    - ... 还有 {len(source_diagnostics) - 5} 个诊断")
    should_write_output = _should_write_lineage_output(
        fatal_diagnostics,
        output_paths,
        force_overwrite_on_error=args.force_overwrite_on_error,
    )
    if fatal_diagnostics and not should_write_output:
        print(
            "\n血缘提取失败: "
            f"存在 {len(fatal_diagnostics)} 个错误, "
            "未覆盖已有输出文件; 如需覆盖请使用 --force-overwrite-on-error"
        )
        sys.exit(1)

    output = build_lineage_output(
        all_lineage,
        schema,
        task_results=extraction_result["task_results"],
    )
    warn_jobs_with_multiple_non_process_outputs(
        output["jobs"],
        output["tables"],
    )
    for path in output_paths:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding=TEXT_ENCODING) as fp:
            json.dump(output, fp, ensure_ascii=False, indent=2)
    if cache_path is not None:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        with open(cache_path, "w", encoding=TEXT_ENCODING) as fp:
            json.dump(
                extraction_result["task_cache"],
                fp,
                ensure_ascii=False,
                indent=2,
            )

    if fatal_diagnostics:
        print("\n血缘提取完成, 但存在严重错误!")
    else:
        print("\n血缘提取完成!")
    for line in format_lineage_output_statistics(output):
        print(line)
    if STATS["parse_failures"]:
        print(f"  解析失败: {STATS['parse_failures']} 个文件")
    if STATS["lineage_failures"]:
        print(f"  lineage 未抽取: {STATS['lineage_failures']} 个目标表")
    print(f"  输出: {output_path}")
    if fatal_diagnostics and not args.force_overwrite_on_error:
        print("  存在严重错误, 已写出新输出文件但进程返回失败")
        sys.exit(1)
    if fatal_diagnostics and args.force_overwrite_on_error:
        print("  已按 --force-overwrite-on-error 覆盖写出")

    print()
    for line in format_layer_statistics(output["tables"]):
        print(line)

    return output


if __name__ == "__main__":
    main()
