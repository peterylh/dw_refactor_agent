#!/usr/bin/env python3
"""
血缘 HTML 刷新工具
读取 lineage_data.json, 注入到 lineage_job.html 中重新生成
"""

import json, re
from pathlib import Path
from collections import OrderedDict
import sqlglot
from sqlglot import exp

LINEAGE_DIR = Path(__file__).parent
TASKS_DIR = Path(__file__).parent.parent / "shop" / "tasks"
JOB_LOGIC = {
    "dwd_customer": "清洗客户数据 → 划分年龄段 → 补全缺失值",
    "dwd_order_detail": "多表关联 → 计算毛利 → 回填成本 → 剔除无效订单",
    "dwd_product": "关联品类维表 → 计算毛利率 → 清理异常值",
    "dwd_store": "门店分级 → 计算开业年限 → 补全缺失值",
    "dws_category_sales_monthly": "按品类+月份汇总 → 清理空值 → 剔除无效数据",
    "dws_customer_order_summary": "按客户+日期汇总 → 修正异常值 → 剔除无效记录",
    "dws_product_sales_daily": "按商品+日期汇总 → 清理空值 → 剔除异常数据",
    "dws_store_sales_daily": "按门店+日期汇总 → 清理空值 → 剔除异常数据",
    "ads_customer_rfm": "计算RFM指标 → NTILE打分 → 客户分层 → 填充默认值",
    "ads_product_topn_daily": "每日排名 → 关联商品维表 → 剔除超出TOP10的数据",
    "ads_sales_dashboard": "多店日汇总 → 计算环比增长率 → 填充空值",
    "ads_store_performance": "按月汇总门店KPI → 归一化评分 → 填充空值",
}


def load_lineage_data():
    with open(LINEAGE_DIR / "lineage_data.json", encoding="utf-8") as f:
        return json.load(f)


def _layer_priority(tbl):
    if tbl.startswith("ads_"):
        return 4
    if tbl.startswith("dws_"):
        return 3
    if tbl.startswith("dwd_"):
        return 2
    if tbl.startswith("ods_"):
        return 1
    return 0


def _strip_db(name):
    return name.replace("shop_dm.", "")


def generate_jobs(data):
    file_edges = {}
    for e in data["edges"]:
        fname = e.get("source_file", "")
        file_edges.setdefault(fname, []).append(e)

    jobs = []
    for f in sorted(TASKS_DIR.glob("*.sql")):
        fname = f.name
        edges = file_edges.get(fname, [])

        sources = set()
        targets = set()
        for e in edges:
            sources.add(_strip_db(e["source"].rsplit(".", 1)[0]))
            targets.add(_strip_db(e["target"].rsplit(".", 1)[0]))

        for stmt in sqlglot.parse(f.read_text(encoding="utf-8"), dialect="doris"):
            if stmt is None:
                continue
            if isinstance(stmt, (exp.Insert, exp.Create)):
                targets.add(_strip_db(stmt.this.sql(dialect="doris")))
            elif isinstance(stmt, exp.Update):
                targets.add(_strip_db(stmt.this.sql(dialect="doris")))

        main_target = max(targets, key=_layer_priority) if targets else f.stem
        sources.discard(main_target)

        short = _strip_db(main_target)
        layer = "OTHER"
        if short.startswith("ods_"):
            layer = "ODS"
        elif short.startswith("dwd_"):
            layer = "DWD"
        elif short.startswith("dws_"):
            layer = "DWS"
        elif short.startswith("ads_"):
            layer = "ADS"

        jobs.append(
            OrderedDict(
                [
                    ("id", f.stem),
                    ("file", fname),
                    ("name", f.stem),
                    ("source", sorted(sources)),
                    ("target", short),
                    ("layer", layer),
                    ("logic", JOB_LOGIC.get(f.stem, "-")),
                ]
            )
        )

    return jobs


def inject_into_html(template_path, output_path, lineage_json, jobs_json):
    with open(template_path, encoding="utf-8") as f:
        html = f.read()
    html = re.sub(
        r"(const LD\s*=\s*)\{.*?\};",
        lambda m: m.group(1) + lineage_json + ";",
        html,
        flags=re.DOTALL,
    )
    html = re.sub(
        r"(const JOBS\s*=\s*)\[.*?\];",
        lambda m: m.group(1) + jobs_json + ";",
        html,
        flags=re.DOTALL,
    )
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)


def update_lineage_html(data, lineage_json):
    """更新只含字段级视图的 lineage.html."""
    path = LINEAGE_DIR / "lineage.html"
    if not path.exists():
        return
    with open(path, encoding="utf-8") as f:
        html = f.read()
    html = re.sub(
        r"(const LINEAGE_DATA\s*=\s*)\{.*?\};",
        lambda m: m.group(1) + lineage_json + ";",
        html,
        flags=re.DOTALL,
    )
    with open(path, "w", encoding="utf-8") as f:
        f.write(html)
    print("  已更新:", path)


def main():
    data = load_lineage_data()
    jobs = generate_jobs(data)

    lineage_json = json.dumps(data, ensure_ascii=False, indent=2)
    jobs_json = json.dumps(jobs, ensure_ascii=False, indent=2)

    template = LINEAGE_DIR / "lineage_job.html"
    if not template.exists():
        print(f"模板不存在: {template}")
        return

    inject_into_html(template, template, lineage_json, jobs_json)
    update_lineage_html(data, lineage_json)

    print("HTML 已刷新:", template)
    print(
        f"  表: {len(data['tables'])}, 边: {len(data['edges'])}, 节点: {len(data['nodes'])}"
    )
    print(f"  作业: {len(jobs)}")


if __name__ == "__main__":
    main()
