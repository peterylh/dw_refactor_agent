#!/usr/bin/env python3
"""Compare production and QA data for refactor shadow-run plans."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_src_root = Path(__file__).resolve().parents[2]
if str(_src_root) not in sys.path:
    sys.path.insert(0, str(_src_root))

import pymysql

from dw_refactor_agent.config import (
    DORIS_HOST,
    DORIS_PORT,
    DORIS_QA_USER,
    DORIS_USER,
    PROJECT_ROOT,
    TEXT_ENCODING,
)
from dw_refactor_agent.refactor.artifact_contract import (
    FORMAT_VERSION,
    ArtifactFormatError,
    atomic_write_json,
    require_format_version,
)
from dw_refactor_agent.refactor.plan_artifact import (
    load_persisted_verification_plan,
    load_verification_plan,
    require_fresh_plan,
)

DEFAULT_ROW_COMPARE_EXCLUDE_COLUMNS = ["etl_time"]


def fmt_val(value):
    if value is None:
        return "NULL"
    if isinstance(value, float):
        return f"{value:.6f}"
    return str(value)


def _exclude_columns_for_check(check: dict) -> list[str]:
    raw_columns = (
        check.get("exclude_columns")
        if "exclude_columns" in check
        else DEFAULT_ROW_COMPARE_EXCLUDE_COLUMNS
    )
    if raw_columns is None:
        return []
    if isinstance(raw_columns, str):
        raw_columns = [raw_columns]
    return [
        str(column).strip() for column in raw_columns if str(column).strip()
    ]


def _row_compare_columns(
    all_cols: list[str], check: dict
) -> tuple[list[str], list[str]]:
    excluded = {
        column.casefold() for column in _exclude_columns_for_check(check)
    }
    compared_cols = []
    ignored_cols = []
    for column in all_cols:
        if str(column).casefold() in excluded:
            ignored_cols.append(column)
        else:
            compared_cols.append(column)
    return compared_cols, ignored_cols


def _check_tables(check: dict) -> tuple[str, str, str]:
    logical_table = check["table"]
    return (
        logical_table,
        check.get("prod_table") or logical_table,
        check.get("qa_table") or logical_table,
    )


def _mapped_partition_columns(
    check: dict, partition_col: str | None
) -> tuple[str | None, str | None]:
    if not partition_col:
        return None, None
    for mapping in check.get("column_mapping") or []:
        qa_column = str(mapping.get("qa") or "")
        if qa_column.casefold() == str(partition_col).casefold():
            return str(mapping.get("prod") or partition_col), qa_column
    return partition_col, partition_col


def get_pymysql_conn(db_name: str, qa: bool = False):
    return pymysql.connect(
        host=DORIS_HOST,
        port=DORIS_PORT,
        user=DORIS_QA_USER if qa else DORIS_USER,
        database=db_name,
        charset="utf8mb4",
    )


def _check_with_compare_anchor(check: dict, verification: dict) -> dict:
    if check.get("partition_col") or check.get("partition_value") is not None:
        return dict(check)

    table = check.get("table")
    anchor = (verification.get("compare_anchors") or {}).get(table) or {}
    time_column = anchor.get("time_column")
    anchor_value = anchor.get("anchor_time_value")
    if not time_column or anchor_value is None:
        return dict(check)

    resolved = dict(check)
    resolved["partition_col"] = time_column
    resolved["partition_value"] = anchor_value
    return resolved


def _check_with_target_semantics(check: dict, verification: dict) -> dict:
    resolved = dict(check)
    semantics = (verification.get("target_semantics") or {}).get(
        check.get("table")
    ) or {}
    if "column_mapping" not in resolved and semantics.get("column_mapping"):
        resolved["column_mapping"] = list(semantics["column_mapping"])
    return resolved


def check_count(prod_conn, qa_conn, check: dict, precision: float) -> dict:
    """Compare COUNT(*) between production and QA."""
    table, prod_table, qa_table = _check_tables(check)
    partition_col = check.get("partition_col")
    partition_value = check.get("partition_value")
    prod_partition_col, qa_partition_col = _mapped_partition_columns(
        check, partition_col
    )

    cursor_prod = prod_conn.cursor()
    cursor_qa = qa_conn.cursor()

    if prod_partition_col and partition_value is not None:
        prod_sql = (
            f"SELECT COUNT(*) FROM {prod_table} "
            f"WHERE {prod_partition_col} = '{partition_value}'"
        )
        qa_sql = (
            f"SELECT COUNT(*) FROM {qa_table} "
            f"WHERE {qa_partition_col} = '{partition_value}'"
        )
    else:
        prod_sql = f"SELECT COUNT(*) FROM {prod_table}"
        qa_sql = f"SELECT COUNT(*) FROM {qa_table}"
    cursor_prod.execute(prod_sql)
    prod_count = cursor_prod.fetchone()[0]
    cursor_qa.execute(qa_sql)
    qa_count = cursor_qa.fetchone()[0]

    cursor_prod.close()
    cursor_qa.close()

    match = prod_count == qa_count
    status = "pass" if match else "fail"
    print(f"  COUNT:  PROD={prod_count}  QA={qa_count}  {status}")

    return {
        "table": table,
        "prod_table": prod_table,
        "qa_table": qa_table,
        "method": "count",
        "partition": partition_value,
        "prod_count": prod_count,
        "qa_count": qa_count,
        "match": match,
    }


def check_row_compare(
    prod_conn, qa_conn, check: dict, sample: int, precision: float
) -> dict:
    """Compare rows and columns between production and QA."""
    table, prod_table, qa_table = _check_tables(check)
    partition_col = check.get("partition_col")
    partition_value = check.get("partition_value")
    prod_partition_col, qa_partition_col = _mapped_partition_columns(
        check, partition_col
    )

    cursor_prod = prod_conn.cursor()
    cursor_qa = qa_conn.cursor()

    column_mapping = check.get("column_mapping") or []
    if column_mapping:
        column_pairs = []
        for mapping in column_mapping:
            prod_column = str(mapping.get("prod") or "").strip()
            qa_column = str(mapping.get("qa") or "").strip()
            if not prod_column or not qa_column:
                cursor_prod.close()
                cursor_qa.close()
                return {
                    "table": table,
                    "method": "row_compare",
                    "error": "列映射不完整",
                    "match": False,
                    "compared_columns": [],
                    "ignored_columns": [],
                }
            column_pairs.append((prod_column, qa_column))
        excluded = {
            column.casefold() for column in _exclude_columns_for_check(check)
        }
        compared_pairs = [
            pair for pair in column_pairs if pair[1].casefold() not in excluded
        ]
        ignored_cols = [
            qa_column
            for _, qa_column in column_pairs
            if qa_column.casefold() in excluded
        ]
    else:
        cursor_prod.execute(f"DESC {prod_table}")
        all_cols = [row[0] for row in cursor_prod.fetchall()]
        if not all_cols:
            cursor_prod.close()
            cursor_qa.close()
            return {
                "table": table,
                "method": "row_compare",
                "error": "无列信息",
                "match": False,
                "compared_columns": [],
                "ignored_columns": [],
            }
        compared_cols, ignored_cols = _row_compare_columns(all_cols, check)
        compared_pairs = [(column, column) for column in compared_cols]

    if not compared_pairs:
        cursor_prod.close()
        cursor_qa.close()
        return {
            "table": table,
            "method": "row_compare",
            "error": "无可比较列",
            "match": False,
            "compared_columns": [],
            "ignored_columns": ignored_cols,
        }

    prod_columns = [pair[0] for pair in compared_pairs]
    qa_columns = [pair[1] for pair in compared_pairs]
    compared_cols = qa_columns
    prod_col_list = ", ".join(prod_columns)
    qa_col_list = ", ".join(qa_columns)
    prod_order_cols = ", ".join(prod_columns[: min(3, len(prod_columns))])
    qa_order_cols = ", ".join(qa_columns[: min(3, len(qa_columns))])
    limit_sql = f"LIMIT {sample}" if sample else ""
    prod_where_sql = (
        f"WHERE {prod_partition_col} = '{partition_value}' "
        if prod_partition_col and partition_value is not None
        else ""
    )
    qa_where_sql = (
        f"WHERE {qa_partition_col} = '{partition_value}' "
        if qa_partition_col and partition_value is not None
        else ""
    )
    prod_sql = (
        f"SELECT {prod_col_list} FROM {prod_table} "
        f"{prod_where_sql}ORDER BY {prod_order_cols} {limit_sql}"
    )
    qa_sql = (
        f"SELECT {qa_col_list} FROM {qa_table} "
        f"{qa_where_sql}ORDER BY {qa_order_cols} {limit_sql}"
    )

    cursor_prod.execute(prod_sql)
    prod_rows = cursor_prod.fetchall()
    cursor_qa.execute(qa_sql)
    qa_rows = cursor_qa.fetchall()

    cursor_prod.close()
    cursor_qa.close()

    mismatches = []
    min_len = min(len(prod_rows), len(qa_rows))

    for idx in range(min_len):
        prod_row = prod_rows[idx]
        qa_row = qa_rows[idx]
        row_diffs = []
        for col_idx, col in enumerate(compared_cols):
            prod_value = prod_row[col_idx]
            qa_value = qa_row[col_idx]
            if prod_value == qa_value:
                continue
            if (
                isinstance(prod_value, (int, float))
                and isinstance(qa_value, (int, float))
                and abs(float(prod_value) - float(qa_value)) <= precision
            ):
                continue
            row_diffs.append(
                {
                    "col": col,
                    "prod": fmt_val(prod_value),
                    "qa": fmt_val(qa_value),
                }
            )
        if row_diffs:
            mismatches.append({"row": idx, "diffs": row_diffs})

    match = (not mismatches) and (len(prod_rows) == len(qa_rows))
    status = "pass" if match else "fail"
    sampled = sample and len(prod_rows) == sample
    sample_note = f" (抽样 {sample})" if sampled else ""
    print(
        f"  ROW:  PROD={len(prod_rows)}  QA={len(qa_rows)}  "
        f"差异={len(mismatches)}{sample_note}  {status}"
    )
    if ignored_cols:
        print(f"  忽略列: {', '.join(ignored_cols)}")

    if mismatches:
        for mismatch in mismatches[:5]:
            for diff in mismatch["diffs"]:
                print(
                    f"    row {mismatch['row']}  {diff['col']}: "
                    f"PROD={diff['prod']}  QA={diff['qa']}"
                )

    return {
        "table": table,
        "prod_table": prod_table,
        "qa_table": qa_table,
        "method": "row_compare",
        "partition": partition_value,
        "prod_rows": len(prod_rows),
        "qa_rows": len(qa_rows),
        "sampled": sample,
        "mismatches": len(mismatches),
        "match": match,
        "compared_columns": compared_cols,
        "ignored_columns": ignored_cols,
        "detail": mismatches[:20] if mismatches else [],
    }


def _terminal_result(
    status: str, warnings: list[dict], reason: str | None = None
) -> dict:
    result = {
        "verification_status": status,
        "warnings": warnings,
        "results": [],
    }
    if reason:
        result["reason"] = reason
    return result


def _check_semantic_modes(
    checks: list[dict], verification: dict
) -> tuple[dict[str, str], str | None]:
    target_semantics = verification.get("target_semantics")
    if not isinstance(target_semantics, dict):
        return {}, "verification.target_semantics is required"
    modes = {}
    for check in checks:
        table = check.get("table")
        semantics = target_semantics.get(table)
        if not isinstance(semantics, dict):
            return {}, f"verification check has no target semantics: {table}"
        mode = semantics.get("resolved_mode")
        if mode not in {"equivalent", "unknown"}:
            return {}, (
                f"verification check for {table} has invalid resolved mode: "
                f"{mode}"
            )
        modes[table] = mode
    return modes, None


def _ensure_unknown_warnings(
    warnings: list[dict], modes: dict[str, str]
) -> list[dict]:
    resolved = list(warnings)
    warned_tables = {
        warning.get("table")
        for warning in resolved
        if isinstance(warning, dict)
    }
    for table, mode in sorted(modes.items()):
        if mode == "unknown" and table not in warned_tables:
            resolved.append(
                {
                    "type": "unknown_table_semantics",
                    "table": table,
                    "message": (
                        "Only observational anchors are compared; passing "
                        "checks does not prove this table is equivalent."
                    ),
                }
            )
    return resolved


def _print_warnings(warnings: list[dict]) -> None:
    if not warnings:
        return
    print("Warnings:")
    for warning in warnings:
        table = warning.get("table")
        if table is None:
            table = ", ".join(warning.get("tables") or []) or "-"
        message = warning.get("message") or warning.get("type") or "warning"
        print(f"  - {table}: {message}")


def run_checks(
    plan: dict,
    *,
    method: str = "all",
    sample: int = 0,
    precision: float = 0.01,
) -> dict:
    """Run configured production-vs-QA checks."""
    prod_db = plan["project_db"]
    qa_db = plan["qa_db"]
    verification = plan.get("verification", {})
    checks = verification.get("checks", [])
    warnings = list(verification.get("warnings") or [])
    if verification.get("schema_anchor_status") == "blocked":
        reason = verification.get("schema_anchor_reason") or (
            "verification plan has blocked schema anchor changes"
        )
        print(f"表定义锚点校验被阻断: {reason}")
        return _terminal_result("blocked", warnings, reason)
    if verification.get("data_anchor_status") == "blocked":
        reason = verification.get("data_anchor_reason") or (
            "verification plan has blocked data anchor changes"
        )
        print(f"数据锚点校验被阻断: {reason}")
        return _terminal_result("blocked", warnings, reason)

    semantic_modes, semantic_error = _check_semantic_modes(
        checks, verification
    )
    if semantic_error:
        print(f"语义校验计划被阻断: {semantic_error}")
        return _terminal_result("blocked", warnings, semantic_error)
    warnings = _ensure_unknown_warnings(warnings, semantic_modes)

    filtered = [
        _check_with_compare_anchor(
            _check_with_target_semantics(check, verification), verification
        )
        for check in checks
        if method in ("all", check["method"])
    ]
    if not filtered:
        if not checks and verification.get("data_anchor_status") == "none":
            reason = verification.get("data_anchor_reason") or (
                "verification plan has affected work but no data anchor checks"
            )
            print(f"没有可校验的数据锚点: {reason}")
            return _terminal_result("inconclusive", warnings, reason)
        print(f"没有匹配的校验项 (method={method})")
        return _terminal_result(
            "inconclusive",
            warnings,
            f"no executable verification checks for method={method}",
        )

    print(f"{'=' * 60}")
    print(f"验证库: {qa_db}")
    print(f"方法:   {method}")
    if sample:
        print(f"抽样:   {sample} 行")
    print(f"容差:   {precision}")

    prod_conn = get_pymysql_conn(prod_db)
    qa_conn = get_pymysql_conn(qa_db, qa=True)

    results = []
    try:
        for check in filtered:
            table = check["table"]
            check_method = check["method"]
            partition_col = check.get("partition_col")
            partition_value = check.get("partition_value")

            if partition_col and partition_value is not None:
                print(
                    f"\n--- [{check_method}] {table} "
                    f"WHERE {partition_col} = '{partition_value}' ---"
                )
            else:
                print(f"\n--- [{check_method}] {table} ---")

            if check_method == "count":
                result = check_count(prod_conn, qa_conn, check, precision)
            elif check_method == "row_compare":
                result = check_row_compare(
                    prod_conn, qa_conn, check, sample, precision
                )
            else:
                continue

            result["semantic_mode"] = semantic_modes[table]
            results.append(result)
    finally:
        prod_conn.close()
        qa_conn.close()

    equivalent_failed = any(
        not result["match"] and result["semantic_mode"] == "equivalent"
        for result in results
    )
    observational_failed = any(
        not result["match"] and result["semantic_mode"] == "unknown"
        for result in results
    )
    unknown_present = any(
        result["semantic_mode"] == "unknown" for result in results
    )
    if equivalent_failed:
        verification_status = "failed"
    elif observational_failed:
        verification_status = "inconclusive"
    elif unknown_present or warnings:
        verification_status = "passed_with_warnings"
    else:
        verification_status = "passed"

    total = len(results)
    passed = sum(1 for result in results if result["match"])
    failed = total - passed

    print(f"\n{'=' * 60}")
    print(f"验证状态: {verification_status}")
    print(f"  校验项: {total}  通过: {passed}  失败: {failed}")
    return {
        "verification_status": verification_status,
        "warnings": warnings,
        "results": results,
    }


def require_matching_shadow_result(
    plan_path: Path, shadow_result_path: Path
) -> dict:
    """Require completed QA execution from the exact persisted plan."""
    persisted_plan = load_persisted_verification_plan(plan_path)
    shadow_result_path = Path(shadow_result_path)
    try:
        shadow_result = json.loads(
            shadow_result_path.read_text(encoding=TEXT_ENCODING)
        )
    except (OSError, ValueError) as exc:
        raise ArtifactFormatError(
            f"cannot read shadow-run result: {shadow_result_path}: {exc}"
        ) from exc
    if not isinstance(shadow_result, dict):
        raise ArtifactFormatError("shadow-run result must be a JSON object")
    require_format_version(shadow_result, "shadow-run result")
    if shadow_result.get("mode") != "execute":
        raise ArtifactFormatError(
            "shadow-run result must come from execute mode; run shadow-run"
        )
    if shadow_result.get("status") != "completed":
        raise ArtifactFormatError(
            "shadow-run result must have status=completed; run shadow-run"
        )

    snapshot = persisted_plan.get("analysis_snapshot") or {}
    expected_workspace = snapshot.get("workspace_fingerprint")
    if not isinstance(
        expected_workspace, str
    ) or not expected_workspace.startswith("sha256:"):
        raise ArtifactFormatError(
            "verification plan analysis snapshot fingerprint is invalid; "
            "run analyze again"
        )
    if shadow_result.get("workspace_fingerprint") != expected_workspace:
        raise ArtifactFormatError(
            "shadow-run workspace fingerprint does not match the current "
            "plan; run analyze and shadow-run again"
        )
    expected_plan = persisted_plan.get("plan_fingerprint")
    if not isinstance(expected_plan, str) or not expected_plan.startswith(
        "sha256:"
    ):
        raise ArtifactFormatError(
            "verification plan fingerprint is invalid; run analyze again"
        )
    if shadow_result.get("plan_fingerprint") != expected_plan:
        raise ArtifactFormatError(
            "shadow-run plan fingerprint does not match the current plan; "
            "run shadow-run again"
        )
    return shadow_result


def compare_shadow_results(
    plan_path: Path,
    shadow_result_path: Path,
    output_path: Path,
    *,
    method: str = "all",
    sample: int = 0,
    precision: float = 0.01,
) -> dict:
    """Compare production and QA results for a validation plan."""
    plan_path = Path(plan_path)
    shadow_result_path = Path(shadow_result_path)
    output_path = Path(output_path)
    require_matching_shadow_result(plan_path, shadow_result_path)
    plan = load_verification_plan(plan_path)
    result = run_checks(
        plan,
        method=method,
        sample=sample,
        precision=precision,
    )
    _print_warnings(result.get("warnings") or [])
    result["format_version"] = FORMAT_VERSION
    atomic_write_json(output_path, result)
    return result


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="对比 shadow-run 结果")
    parser.add_argument("--plan", required=True, help="验证计划 JSON 路径")
    parser.add_argument(
        "--shadow-result",
        default=None,
        help=(
            "shadow-run 结果 JSON 路径，默认读取 plan 同目录的 "
            "shadow_run_result.json"
        ),
    )
    parser.add_argument(
        "--method", default="all", choices=["count", "row_compare", "all"]
    )
    parser.add_argument(
        "--sample", type=int, default=0, help="row_compare 抽样行数 (0=全量)"
    )
    parser.add_argument(
        "--precision", type=float, default=0.01, help="DECIMAL 比较容差"
    )
    parser.add_argument(
        "--output",
        default=None,
        help="结果 JSON 路径，默认写入 plan 同目录 compare_result.json",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    plan_path = Path(args.plan)
    output_path = (
        Path(args.output)
        if args.output
        else plan_path.parent / "compare_result.json"
    )
    shadow_result_path = (
        Path(args.shadow_result)
        if args.shadow_result
        else plan_path.parent / "shadow_run_result.json"
    )
    persisted_plan = load_persisted_verification_plan(plan_path)
    try:
        require_fresh_plan(
            plan_path,
            root=PROJECT_ROOT,
            project=persisted_plan["project"],
        )
        result = compare_shadow_results(
            plan_path,
            shadow_result_path,
            output_path,
            method=args.method,
            sample=args.sample,
            precision=args.precision,
        )
    except ArtifactFormatError as exc:
        raise SystemExit(str(exc)) from None
    status = result["verification_status"]
    if status in {"passed", "passed_with_warnings"}:
        return 0
    if status == "inconclusive":
        return 2
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
