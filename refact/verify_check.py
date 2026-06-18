#!/usr/bin/env python3
"""
验证校验: 对锚点表执行可配置的数据校验。

支持方法:
  count        行数对比
  row_compare  逐行逐列对比 (支持抽样 + 精度容差)

用法:
  python refact/verify_check.py --metadata refact/refact_metadata.json
  python refact/verify_check.py --metadata refact/refact_metadata.json --method count
  python refact/verify_check.py --metadata refact/refact_metadata.json --method row_compare --sample 1000
  python refact/verify_check.py --metadata refact/refact_metadata.json --precision 0.001
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import pymysql

from config import (
    DORIS_HOST,
    DORIS_PORT,
    DORIS_QA_USER,
    DORIS_USER,
    TEXT_ENCODING,
)

# ============================================================
# 连接配置
# ============================================================

# ============================================================
# 辅助
# ============================================================


def fmt_val(v):
    if v is None:
        return "NULL"
    if isinstance(v, float):
        return f"{v:.6f}"
    return str(v)


def get_pymysql_conn(db_name: str, qa: bool = False):
    return pymysql.connect(
        host=DORIS_HOST,
        port=DORIS_PORT,
        user=DORIS_QA_USER if qa else DORIS_USER,
        database=db_name,
        charset="utf8mb4",
    )


# ============================================================
# 校验器
# ============================================================


def check_count(prod_conn, qa_conn, ck: dict, precision: float) -> dict:
    """COUNT(*) 对比."""
    table = ck["table"]
    pc = ck["partition_col"]
    pv = ck["partition_value"]

    cursor_p = prod_conn.cursor()
    cursor_q = qa_conn.cursor()

    sql = f"SELECT COUNT(*) FROM {table} WHERE {pc} = '{pv}'"
    cursor_p.execute(sql)
    prod_cnt = cursor_p.fetchone()[0]
    cursor_q.execute(sql)
    qa_cnt = cursor_q.fetchone()[0]

    cursor_p.close()
    cursor_q.close()

    match = prod_cnt == qa_cnt
    status = "\u2714" if match else "\u2716"
    print(f"  COUNT:  PROD={prod_cnt}  QA={qa_cnt}  {status}")

    return {
        "table": table,
        "method": "count",
        "partition": pv,
        "prod_count": prod_cnt,
        "qa_count": qa_cnt,
        "match": match,
    }


def check_row_compare(
    prod_conn, qa_conn, ck: dict, sample: int, precision: float
) -> dict:
    """逐行逐列对比."""
    table = ck["table"]
    pc = ck["partition_col"]
    pv = ck["partition_value"]

    cursor_p = prod_conn.cursor()
    cursor_q = qa_conn.cursor()

    # 获取列信息
    cursor_p.execute(f"DESC {table}")
    all_cols = [row[0] for row in cursor_p.fetchall()]
    if not all_cols:
        cursor_p.close()
        cursor_q.close()
        return {"table": table, "method": "row_compare", "error": "无列信息"}

    col_list = ", ".join(all_cols)

    # 用前 3 列作为 ORDER BY 保证确定性顺序
    order_cols = ", ".join(all_cols[: min(3, len(all_cols))])

    limit_sql = f"LIMIT {sample}" if sample else ""

    prod_sql = (
        f"SELECT {col_list} FROM {table} "
        f"WHERE {pc} = '{pv}' ORDER BY {order_cols} {limit_sql}"
    )
    qa_sql = (
        f"SELECT {col_list} FROM {table} "
        f"WHERE {pc} = '{pv}' ORDER BY {order_cols} {limit_sql}"
    )

    cursor_p.execute(prod_sql)
    prod_rows = cursor_p.fetchall()
    cursor_q.execute(qa_sql)
    qa_rows = cursor_q.fetchall()

    cursor_p.close()
    cursor_q.close()

    mismatches = []
    min_len = min(len(prod_rows), len(qa_rows))

    for i in range(min_len):
        prow = prod_rows[i]
        qrow = qa_rows[i]
        row_diffs = []
        for j, col in enumerate(all_cols):
            pv_col = prow[j]
            qv_col = qrow[j]
            if pv_col == qv_col:
                continue
            # DECIMAL / 浮点容差
            if (
                isinstance(pv_col, (int, float))
                and isinstance(qv_col, (int, float))
                and abs(float(pv_col) - float(qv_col)) <= precision
            ):
                continue
            row_diffs.append(
                {
                    "col": col,
                    "prod": fmt_val(pv_col),
                    "qa": fmt_val(qv_col),
                }
            )
        if row_diffs:
            mismatches.append({"row": i, "diffs": row_diffs})

    match = (not mismatches) and (len(prod_rows) == len(qa_rows))
    status = "\u2714" if match else "\u2716"
    sampled = sample and len(prod_rows) == sample
    sample_note = f" (抽样 {sample})" if sampled else ""
    print(
        f"  ROW:  PROD={len(prod_rows)}  QA={len(qa_rows)}  "
        f"差异={len(mismatches)}{sample_note}  {status}"
    )

    if mismatches:
        for m in mismatches[:5]:
            for d in m["diffs"]:
                print(
                    f"    row {m['row']}  {d['col']}: "
                    f"PROD={d['prod']}  QA={d['qa']}"
                )

    return {
        "table": table,
        "method": "row_compare",
        "partition": pv,
        "prod_rows": len(prod_rows),
        "qa_rows": len(qa_rows),
        "sampled": sample,
        "mismatches": len(mismatches),
        "match": match,
        "detail": mismatches[:20] if mismatches else [],
    }


# ============================================================
# 主流程
# ============================================================


def main():
    parser = argparse.ArgumentParser(description="验证校验")
    parser.add_argument("--metadata", required=True, help="元数据 JSON 路径")
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
        help="结果 JSON 路径 (默认 refact/verify_result.json)",
    )
    args = parser.parse_args()

    meta = json.loads(Path(args.metadata).read_text(encoding=TEXT_ENCODING))
    prod_db = meta["project_db"]
    qa_db = meta["qa_db"]
    checks = meta.get("verification", {}).get("checks", [])

    # 过滤
    filtered = [c for c in checks if args.method in ("all", c["method"])]
    if not filtered:
        print(f"没有匹配的校验项 (method={args.method})")
        return

    print(f"{'=' * 60}")
    print(f"验证库: {qa_db}")
    print(f"方法:   {args.method}")
    if args.sample:
        print(f"抽样:   {args.sample} 行")
    print(f"容差:   {args.precision}")

    prod_conn = get_pymysql_conn(prod_db)
    qa_conn = get_pymysql_conn(qa_db, qa=True)

    results = []
    all_pass = True

    for ck in filtered:
        table = ck["table"]
        method = ck["method"]
        pc = ck["partition_col"]
        pv = ck["partition_value"]

        print(f"\n--- [{method}] {table} WHERE {pc} = '{pv}' ---")

        if method == "count":
            r = check_count(prod_conn, qa_conn, ck, args.precision)
        elif method == "row_compare":
            r = check_row_compare(
                prod_conn, qa_conn, ck, args.sample, args.precision
            )
        else:
            continue

        results.append(r)
        if not r["match"]:
            all_pass = False

    prod_conn.close()
    qa_conn.close()

    total = len(results)
    passed = sum(1 for r in results if r["match"])
    failed = total - passed

    print(f"\n{'=' * 60}")
    print(f"{'全部通过!' if all_pass else '存在差异!'}")
    print(f"  校验项: {total}  通过: {passed}  失败: {failed}")

    out_path = (
        Path(args.output)
        if args.output
        else (Path(args.metadata).parent / "verify_result.json")
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(
            {"all_pass": all_pass, "results": results},
            ensure_ascii=False,
            indent=2,
        ),
        encoding=TEXT_ENCODING,
    )
    print(f"结果已写入: {out_path}")

    sys.exit(0 if all_pass else 1)


if __name__ == "__main__":
    main()
