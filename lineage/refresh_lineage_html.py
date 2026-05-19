#!/usr/bin/env python3
"""
血缘 HTML 刷新工具
读取 lineage_data.json, 注入到 lineage_job.html 中重新生成
支持: shop(默认) / olist 项目
"""

import json, re, argparse
from pathlib import Path
from collections import OrderedDict
import sqlglot
from sqlglot import exp

CURRENT_DB = "shop_dm"

LINEAGE_DIR = Path(__file__).parent

PROJECT_MAP = {
    "shop": {
        "tasks_dir": Path(__file__).parent.parent / "shop" / "tasks",
        "job_logic": {
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
        },
    },
    "olist": {
        "tasks_dir": Path(__file__).parent.parent / "olist" / "tasks",
        "job_logic": {
            "dwd_customer": "客户基本信息 → 地理区域划分 → 补全缺失值",
            "dwd_order_detail": "多表关联 → 品类翻译 → 配送天数计算 → 延迟判断",
            "dwd_product": "品类翻译 → 体积计算 → 重量分级",
            "dwd_seller": "地理区域划分 → 补全缺失值",
            "dws_seller_monthly": "按月+卖家汇总 → 修正空值",
            "dws_product_category_monthly": "按月+品类汇总 → 修正空值",
            "dws_customer_order_summary": "按客户+日期汇总 → 修正空值 → 删除异常",
            "dws_daily_orders": "按日汇总 → 计算延迟配送数 → 修正空值",
            "ads_seller_performance_ranking": "窗口排名 → 综合评分 → 修正空值",
            "ads_product_topn": "按日排名 → 关联品类 → 截取 Top N",
            "ads_payment_analysis": "按月+支付方式汇总 → 计算占比 → 修正异常",
            "ads_review_analysis": "按月+评分汇总 → 计算占比与配送天数",
            "ads_category_monthly_trend": "复用 DWS 月度汇总 → LAG 计算环比增长率",
            "ads_delivery_performance": "从 DWS 日汇总读取配送指标 → 计算准时率",
            "ads_customer_rfm": "RFM指标计算 → NTILE打分 → 客户分层",
            "ads_geographic_sales": "按月+州汇总 → 区域划分 → 修正空值",
        },
    },
}


def load_lineage_data(project="shop"):
    path = LINEAGE_DIR / f"lineage_data_{project}.json"
    with open(path, encoding="utf-8") as f:
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
    return name.replace(f"{CURRENT_DB}.", "")


def generate_jobs(data, cfg=None):
    if cfg is None:
        cfg = PROJECT_MAP["shop"]
    file_edges = {}
    for e in data["edges"]:
        fname = e.get("source_file", "")
        file_edges.setdefault(fname, []).append(e)

    tasks_dir = cfg["tasks_dir"]
    job_logic = cfg["job_logic"]
    jobs = []
    for f in sorted(tasks_dir.glob("*.sql")):
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
                    ("logic", job_logic.get(f.stem, "-")),
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


def update_lineage_html(data, lineage_json, output_html=None):
    """更新只含字段级视图的 lineage.html."""
    path = output_html or (LINEAGE_DIR / "lineage.html")
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
    parser = argparse.ArgumentParser(description="血缘 HTML 刷新工具")
    parser.add_argument("--project", default="shop", choices=list(PROJECT_MAP.keys()),
                        help="项目名称")
    args = parser.parse_args()

    global CURRENT_DB
    cfg = PROJECT_MAP[args.project]
    if args.project == "olist":
        CURRENT_DB = "olist_dm"

    data = load_lineage_data(project=args.project)
    jobs = generate_jobs(data, cfg=cfg)

    lineage_json = json.dumps(data, ensure_ascii=False, indent=2)
    jobs_json = json.dumps(jobs, ensure_ascii=False, indent=2)

    if args.project == "olist":
        olist_dir = LINEAGE_DIR.parent / "olist"
        olist_dir.mkdir(parents=True, exist_ok=True)
        template = olist_dir / "lineage_job.html"
        output_html = olist_dir / "lineage.html"
    else:
        template = LINEAGE_DIR / "lineage_job.html"
        output_html = LINEAGE_DIR / "lineage.html"

    if not template.exists():
        print(f"模板不存在: {template}")
        return

    inject_into_html(template, template, lineage_json, jobs_json)
    update_lineage_html(data, lineage_json, output_html=output_html)

    print("HTML 已刷新:", template)
    print(
        f"  表: {len(data['tables'])}, 边: {len(data['edges'])}, 节点: {len(data['nodes'])}"
    )
    print(f"  作业: {len(jobs)}")


if __name__ == "__main__":
    main()
