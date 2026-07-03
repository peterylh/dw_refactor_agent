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
    TEXT_ENCODING,
)


def fmt_val(value):
    if value is None:
        return "NULL"
    if isinstance(value, float):
        return f"{value:.6f}"
    return str(value)


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


def check_count(prod_conn, qa_conn, check: dict, precision: float) -> dict:
    """Compare COUNT(*) between production and QA."""
    table = check["table"]
    partition_col = check.get("partition_col")
    partition_value = check.get("partition_value")

    cursor_prod = prod_conn.cursor()
    cursor_qa = qa_conn.cursor()

    if partition_col and partition_value is not None:
        sql = (
            f"SELECT COUNT(*) FROM {table} "
            f"WHERE {partition_col} = '{partition_value}'"
        )
    else:
        sql = f"SELECT COUNT(*) FROM {table}"
    cursor_prod.execute(sql)
    prod_count = cursor_prod.fetchone()[0]
    cursor_qa.execute(sql)
    qa_count = cursor_qa.fetchone()[0]

    cursor_prod.close()
    cursor_qa.close()

    match = prod_count == qa_count
    status = "pass" if match else "fail"
    print(f"  COUNT:  PROD={prod_count}  QA={qa_count}  {status}")

    return {
        "table": table,
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
    table = check["table"]
    partition_col = check.get("partition_col")
    partition_value = check.get("partition_value")

    cursor_prod = prod_conn.cursor()
    cursor_qa = qa_conn.cursor()

    cursor_prod.execute(f"DESC {table}")
    all_cols = [row[0] for row in cursor_prod.fetchall()]
    if not all_cols:
        cursor_prod.close()
        cursor_qa.close()
        return {"table": table, "method": "row_compare", "error": "无列信息"}

    col_list = ", ".join(all_cols)
    order_cols = ", ".join(all_cols[: min(3, len(all_cols))])
    limit_sql = f"LIMIT {sample}" if sample else ""
    where_sql = (
        f"WHERE {partition_col} = '{partition_value}' "
        if partition_col and partition_value is not None
        else ""
    )
    prod_sql = (
        f"SELECT {col_list} FROM {table} "
        f"{where_sql}ORDER BY {order_cols} {limit_sql}"
    )
    qa_sql = (
        f"SELECT {col_list} FROM {table} "
        f"{where_sql}ORDER BY {order_cols} {limit_sql}"
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
        for col_idx, col in enumerate(all_cols):
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

    if mismatches:
        for mismatch in mismatches[:5]:
            for diff in mismatch["diffs"]:
                print(
                    f"    row {mismatch['row']}  {diff['col']}: "
                    f"PROD={diff['prod']}  QA={diff['qa']}"
                )

    return {
        "table": table,
        "method": "row_compare",
        "partition": partition_value,
        "prod_rows": len(prod_rows),
        "qa_rows": len(qa_rows),
        "sampled": sample,
        "mismatches": len(mismatches),
        "match": match,
        "detail": mismatches[:20] if mismatches else [],
    }


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
    if verification.get("schema_anchor_status") == "blocked":
        reason = verification.get("schema_anchor_reason") or (
            "verification plan has blocked schema anchor changes"
        )
        print(f"表定义锚点校验被阻断: {reason}")
        return {
            "all_pass": False,
            "status": "schema_anchor_blocked",
            "reason": reason,
            "results": [],
        }
    if verification.get("data_anchor_status") == "blocked":
        reason = verification.get("data_anchor_reason") or (
            "verification plan has blocked data anchor changes"
        )
        print(f"数据锚点校验被阻断: {reason}")
        return {
            "all_pass": False,
            "status": "data_anchor_blocked",
            "reason": reason,
            "results": [],
        }

    filtered = [
        _check_with_compare_anchor(check, verification)
        for check in checks
        if method in ("all", check["method"])
    ]
    if not filtered:
        if not checks and verification.get("data_anchor_status") == "none":
            reason = verification.get("data_anchor_reason") or (
                "verification plan has affected work but no data anchor checks"
            )
            print(f"没有可校验的数据锚点: {reason}")
            return {
                "all_pass": False,
                "status": "no_data_anchor",
                "reason": reason,
                "results": [],
            }
        print(f"没有匹配的校验项 (method={method})")
        return {"all_pass": True, "results": []}

    print(f"{'=' * 60}")
    print(f"验证库: {qa_db}")
    print(f"方法:   {method}")
    if sample:
        print(f"抽样:   {sample} 行")
    print(f"容差:   {precision}")

    prod_conn = get_pymysql_conn(prod_db)
    qa_conn = get_pymysql_conn(qa_db, qa=True)

    results = []
    all_pass = True

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

            results.append(result)
            if not result["match"]:
                all_pass = False
    finally:
        prod_conn.close()
        qa_conn.close()

    total = len(results)
    passed = sum(1 for result in results if result["match"])
    failed = total - passed

    print(f"\n{'=' * 60}")
    print(f"{'全部通过!' if all_pass else '存在差异!'}")
    print(f"  校验项: {total}  通过: {passed}  失败: {failed}")
    return {"all_pass": all_pass, "results": results}


def compare_shadow_results(
    plan_path: Path,
    output_path: Path,
    *,
    method: str = "all",
    sample: int = 0,
    precision: float = 0.01,
) -> dict:
    """Compare production and QA results for a validation plan."""
    plan_path = Path(plan_path)
    output_path = Path(output_path)
    plan = json.loads(plan_path.read_text(encoding=TEXT_ENCODING))
    result = run_checks(
        plan,
        method=method,
        sample=sample,
        precision=precision,
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(result, ensure_ascii=False, indent=2),
        encoding=TEXT_ENCODING,
    )
    return result


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="对比 shadow-run 结果")
    parser.add_argument("--plan", required=True, help="验证计划 JSON 路径")
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
    result = compare_shadow_results(
        plan_path,
        output_path,
        method=args.method,
        sample=args.sample,
        precision=args.precision,
    )
    return 0 if result["all_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
