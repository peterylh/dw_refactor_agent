#!/usr/bin/env python3
"""
血缘 HTML 刷新工具。

从 `PROJECT_CONFIG` 推导项目目录和数据库名，读取对应的
`lineage_data_{project}.json`，并刷新项目对应的血缘 HTML。
"""

import argparse
import json
import re
import sys
from collections import OrderedDict
from pathlib import Path

import sqlglot
from sqlglot import exp

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import PROJECT_CONFIG, determine_layer, layer_rank

LINEAGE_DIR = Path(__file__).parent

PROJECT_DIR = Path(__file__).parent.parent

JOB_LOGIC_MAP = {
    "shop": {
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
}


def resolve_lineage_data_path(project):
    path = LINEAGE_DIR / f"lineage_data_{project}.json"
    if path.exists():
        return path
    if project == "shop":
        legacy_path = LINEAGE_DIR / "lineage_data.json"
        if legacy_path.exists():
            return legacy_path
    return path


def load_lineage_data(project):
    path = resolve_lineage_data_path(project)
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _layer_priority(tbl, project):
    layer = determine_layer(tbl, project)
    rank = layer_rank(layer)
    return rank + 1 if rank >= 0 else 0


def _strip_db(name, current_db):
    return name.replace(f"{current_db}.", "")


def iter_task_sql_files(tasks_dir):
    files = sorted(tasks_dir.glob("*.sql"))
    full_refresh_dir = tasks_dir / "full_refresh"
    if full_refresh_dir.exists():
        files.extend(sorted(full_refresh_dir.glob("*.sql")))
    return files


def _edge_ref_id(ref):
    if isinstance(ref, dict):
        ref_type = str(ref.get("type") or "")
        if ref_type in ("column", "table"):
            return str(ref.get("id") or "")
        return ""
    return str(ref or "")


def build_frontend_lineage_data(data):
    """Build lineage payload compatible with the HTML field graph."""
    frontend_data = dict(data)
    frontend_edges = []
    for edge in data.get("edges") or []:
        normalized = dict(edge)
        normalized["source"] = _edge_ref_id(edge.get("source"))
        normalized["target"] = _edge_ref_id(edge.get("target"))
        frontend_edges.append(normalized)
    frontend_data["edges"] = frontend_edges

    nodes = []
    seen = set()
    for table in data.get("tables") or []:
        table_name = str(table.get("name") or "")
        if not table_name:
            continue
        layer = str(table.get("layer") or "")
        for column in table.get("columns") or []:
            column_name = str(column.get("name") or "")
            if not column_name:
                continue
            node_id = f"{table_name}.{column_name}"
            if node_id in seen:
                continue
            seen.add(node_id)
            nodes.append({
                "id": node_id,
                "table": table_name,
                "column": column_name,
                "layer": layer,
                "type": str(column.get("type") or ""),
            })

    if nodes:
        frontend_data["nodes"] = nodes
    elif "nodes" in data:
        frontend_data["nodes"] = list(data["nodes"])

    return frontend_data


def generate_jobs(data, tasks_dir, current_db, job_logic=None, project="shop"):
    file_edges = {}
    for e in data["edges"]:
        fname = e.get("source_file", "")
        file_edges.setdefault(fname, []).append(e)

    job_logic = job_logic or {}
    jobs = []

    def _edge_ref_table(ref):
        if isinstance(ref, dict):
            if ref.get("type") == "column":
                return str(ref.get("id") or "").rsplit(".", 1)[0]
            if ref.get("type") == "table":
                return str(ref.get("id") or "")
            return ""
        return str(ref or "").rsplit(".", 1)[0]

    for f in iter_task_sql_files(tasks_dir):
        fname = f.relative_to(tasks_dir).as_posix()
        job_id = f.with_suffix("").relative_to(tasks_dir).as_posix()
        edges = file_edges.get(fname, [])

        sources = set()
        targets = set()
        for e in edges:
            source_table = _edge_ref_table(e.get("source"))
            target_table = _edge_ref_table(e.get("target"))
            if source_table:
                sources.add(_strip_db(source_table, current_db))
            if target_table:
                targets.add(_strip_db(target_table, current_db))

        for stmt in sqlglot.parse(f.read_text(encoding="utf-8"), dialect="doris"):
            if stmt is None:
                continue
            if isinstance(stmt, (exp.Insert, exp.Create)):
                targets.add(_strip_db(stmt.this.sql(dialect="doris"), current_db))
            elif isinstance(stmt, exp.Update):
                targets.add(_strip_db(stmt.this.sql(dialect="doris"), current_db))

        main_target = (
            max(targets, key=lambda t: _layer_priority(t, project))
            if targets else f.stem
        )
        sources.discard(main_target)

        short = _strip_db(main_target, current_db)
        layer = determine_layer(short, project)

        jobs.append(
            OrderedDict(
                [
                    ("id", job_id),
                    ("file", fname),
                    ("name", job_id),
                    ("source", sorted(sources)),
                    ("target", short),
                    ("layer", layer),
                    ("logic", job_logic.get(job_id, job_logic.get(f.stem, "-"))),
                ]
            )
        )

    return jobs


def resolve_output_paths(project):
    job_template = LINEAGE_DIR / "lineage_job.html"
    lineage_template = LINEAGE_DIR / "lineage.html"
    if project == "shop":
        return {
            "job_template": job_template,
            "job_output": job_template,
            "lineage_template": lineage_template,
            "lineage_output": lineage_template,
        }
    return {
        "job_template": job_template,
        "job_output": LINEAGE_DIR / f"lineage_job_{project}.html",
        "lineage_template": lineage_template,
        "lineage_output": LINEAGE_DIR / f"lineage_{project}.html",
    }


def get_project_context(project):
    project_cfg = PROJECT_CONFIG[project]
    paths = resolve_output_paths(project)
    return {
        "project": project,
        "current_db": project_cfg["db"],
        "tasks_dir": PROJECT_DIR / project_cfg["dir"] / "tasks",
        "job_logic": JOB_LOGIC_MAP.get(project, {}),
        "lineage_data_path": resolve_lineage_data_path(project),
        **paths,
    }


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


def update_lineage_html(lineage_json, template_path, output_path):
    """更新只含字段级视图的 lineage.html."""
    if not template_path.exists():
        return
    with open(template_path, encoding="utf-8") as f:
        html = f.read()
    html = re.sub(
        r"(const LINEAGE_DATA\s*=\s*)\{.*?\};",
        lambda m: m.group(1) + lineage_json + ";",
        html,
        flags=re.DOTALL,
    )
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)
    print("  已更新:", output_path)


def count_column_nodes(data):
    return sum(
        len(table.get("columns") or [])
        for table in data.get("tables", [])
    )


def main():
    parser = argparse.ArgumentParser(description="血缘 HTML 刷新工具")
    parser.add_argument(
        "--project",
        default="shop",
        choices=list(PROJECT_CONFIG.keys()),
        help="项目名称",
    )
    args = parser.parse_args()
    ctx = get_project_context(args.project)

    data = load_lineage_data(project=args.project)
    jobs = generate_jobs(
        data,
        tasks_dir=ctx["tasks_dir"],
        current_db=ctx["current_db"],
        job_logic=ctx["job_logic"],
        project=args.project,
    )

    frontend_data = build_frontend_lineage_data(data)
    lineage_json = json.dumps(frontend_data, ensure_ascii=False, indent=2)
    jobs_json = json.dumps(jobs, ensure_ascii=False, indent=2)

    template = ctx["job_template"]
    if not template.exists():
        print(f"模板不存在: {template}")
        return

    inject_into_html(template, ctx["job_output"], lineage_json, jobs_json)
    update_lineage_html(
        lineage_json,
        template_path=ctx["lineage_template"],
        output_path=ctx["lineage_output"],
    )

    print("HTML 已刷新:", ctx["job_output"])
    print(
        f"  表: {len(data['tables'])}, 边: {len(data['edges'])}, 节点: {count_column_nodes(data)}"
    )
    print(f"  作业: {len(jobs)}")


if __name__ == "__main__":
    main()
