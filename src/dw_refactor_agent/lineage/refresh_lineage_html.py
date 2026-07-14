#!/usr/bin/env python3
"""
血缘 HTML 刷新工具。

从 `PROJECT_CONFIG` 推导项目目录和数据库名，读取对应的
`warehouses/{project}/artifacts/lineage/lineage_data.json`，并刷新项目对应的血缘 HTML。
"""

import argparse
import json
import re
import sys
from collections import OrderedDict
from pathlib import Path

import sqlglot
from sqlglot import exp

_src_root = Path(__file__).resolve().parents[2]
if str(_src_root) not in sys.path:
    sys.path.insert(0, str(_src_root))
from dw_refactor_agent.config import (
    PROJECT_CONFIG,
    TEXT_ENCODING,
    determine_layer,
    iter_project_task_files,
    layer_rank,
    lineage_data_path,
    lineage_html_path,
    lineage_job_html_path,
    task_source_file,
)
from dw_refactor_agent.lineage.identifiers import (
    canonical_qualified_identifier,
    display_table_name,
    identifier_match_key,
    split_column_ref,
    table_identity_match_key,
)

LINEAGE_DIR = Path(__file__).parent

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
    return lineage_data_path(project)


def load_lineage_data(project):
    path = resolve_lineage_data_path(project)
    with open(path, encoding=TEXT_ENCODING) as f:
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


def build_frontend_lineage_data(data, project):
    """Build lineage payload compatible with the HTML field graph."""
    frontend_data = dict(data)
    if data.get("format_version") == 2:
        return frontend_data

    frontend_tables = []
    for table in data.get("tables") or []:
        normalized_table = dict(table)
        normalized_table.pop("layer", None)
        frontend_tables.append(normalized_table)
    frontend_data["tables"] = frontend_tables

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
        layer = determine_layer(table_name, project)
        for column in table.get("columns") or []:
            column_name = str(column.get("name") or "")
            if not column_name:
                continue
            node_id = f"{table_name}.{column_name}"
            if node_id in seen:
                continue
            seen.add(node_id)
            nodes.append(
                {
                    "id": node_id,
                    "table": table_name,
                    "column": column_name,
                    "layer": layer,
                    "type": str(column.get("type") or ""),
                }
            )

    if nodes:
        frontend_data["nodes"] = nodes
    elif "nodes" in data:
        frontend_nodes = []
        for node in data["nodes"]:
            normalized_node = dict(node)
            table_name = str(normalized_node.get("table") or "")
            normalized_node["layer"] = determine_layer(table_name, project)
            frontend_nodes.append(normalized_node)
        frontend_data["nodes"] = frontend_nodes

    return frontend_data


def generate_jobs(data, tasks_dir, current_db, job_logic=None, project="shop"):
    job_logic = job_logic or {}
    if data.get("format_version") == 2:
        jobs = []
        for job in data.get("jobs") or []:
            job_id = str(job.get("name") or "")
            source_file = str(job.get("source_file") or "")

            def dataset_displays(values):
                displays = {}
                for dataset in values or []:
                    display = display_table_name(
                        dataset,
                        default_db=current_db,
                        strip_current_db=True,
                    )
                    if display:
                        displays.setdefault(
                            table_identity_match_key(dataset), display
                        )
                return displays

            sources = dataset_displays(job.get("inputs"))
            targets = dataset_displays(job.get("outputs"))
            if targets:
                main_target_key = max(
                    targets,
                    key=lambda key: (
                        _layer_priority(targets[key], project),
                        identifier_match_key(targets[key]),
                    ),
                )
                main_target = targets[main_target_key]
                sources.pop(main_target_key, None)
            else:
                main_target = job_id
            jobs.append(
                OrderedDict(
                    [
                        ("id", job_id),
                        ("file", source_file),
                        ("name", job_id),
                        (
                            "source",
                            sorted(sources.values(), key=identifier_match_key),
                        ),
                        ("target", main_target),
                        ("layer", determine_layer(main_target, project)),
                        (
                            "logic",
                            job_logic.get(
                                job_id,
                                job_logic.get(Path(source_file).stem, "-"),
                            ),
                        ),
                    ]
                )
            )
        return jobs

    file_edges = {}
    for e in data["edges"]:
        fname = e.get("source_file", "")
        file_edges.setdefault(fname, []).append(e)

    jobs = []

    def _edge_ref_table(ref):
        if isinstance(ref, dict):
            if ref.get("type") == "column":
                return _edge_ref_table(ref.get("id"))
            if ref.get("type") == "table":
                return canonical_qualified_identifier(ref.get("id"))
            return ""
        split_ref = split_column_ref(ref)
        return split_ref[0] if split_ref is not None else ""

    task_entries = []
    if tasks_dir:
        explicit_task_files = iter_task_sql_files(Path(tasks_dir))
        task_entries = [
            (
                task_path,
                task_path.relative_to(tasks_dir).as_posix(),
            )
            for task_path in explicit_task_files
        ]
    if not task_entries:
        task_entries = [
            (task_path, task_source_file(project, task_path))
            for task_path in iter_project_task_files(project)
        ]

    for f, fname in task_entries:
        job_id = str(Path(fname).with_suffix(""))
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

        for stmt in sqlglot.parse(
            f.read_text(encoding=TEXT_ENCODING), dialect="doris"
        ):
            if stmt is None:
                continue
            if isinstance(stmt, (exp.Insert, exp.Create, exp.Update)):
                targets.add(
                    _strip_db(stmt.this.sql(dialect="doris"), current_db)
                )

        main_target = (
            max(targets, key=lambda t: _layer_priority(t, project))
            if targets
            else f.stem
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
                    (
                        "logic",
                        job_logic.get(job_id, job_logic.get(f.stem, "-")),
                    ),
                ]
            )
        )

    return jobs


def resolve_output_paths(project):
    job_template = LINEAGE_DIR / "lineage_job.html"
    lineage_template = LINEAGE_DIR / "lineage.html"
    return {
        "job_template": job_template,
        "job_output": lineage_job_html_path(project),
        "lineage_template": lineage_template,
        "lineage_output": lineage_html_path(project),
    }


def get_project_context(project):
    project_cfg = PROJECT_CONFIG[project]
    paths = resolve_output_paths(project)
    return {
        "project": project,
        "current_db": project_cfg["db"],
        "tasks_dir": None,
        "job_logic": JOB_LOGIC_MAP.get(project, {}),
        "lineage_data_path": resolve_lineage_data_path(project),
        **paths,
    }


def inject_into_html(template_path, output_path, lineage_json, jobs_json):
    with open(template_path, encoding=TEXT_ENCODING) as f:
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
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding=TEXT_ENCODING) as f:
        f.write(html)


def update_lineage_html(lineage_json, template_path, output_path):
    """更新只含字段级视图的 lineage.html."""
    if not template_path.exists():
        return
    with open(template_path, encoding=TEXT_ENCODING) as f:
        html = f.read()
    html = re.sub(
        r"(const LINEAGE_DATA\s*=\s*)\{.*?\};",
        lambda m: m.group(1) + lineage_json + ";",
        html,
        flags=re.DOTALL,
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding=TEXT_ENCODING) as f:
        f.write(html)
    print("  已更新:", output_path)


def count_column_nodes(data):
    return sum(
        len(table.get("columns") or []) for table in data.get("tables", [])
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

    frontend_data = build_frontend_lineage_data(data, args.project)
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
