from pathlib import Path
from collections import defaultdict
from dataclasses import dataclass, field

import yaml


@dataclass
class TableContext:
    table_name: str
    layer: str
    ddl: str
    etl_sql: str
    upstream_tables: list[str]
    downstream_tables: list[str]
    depth_from_ods: int = 0
    upstream_metric_groups: dict[str, dict[str, list[str]]] = field(
        default_factory=dict)
    column_lineage: list[dict[str, str]] = field(default_factory=list)


def _metric_names(value) -> list[str]:
    names = []
    if isinstance(value, dict):
        iterable = value.values()
    elif isinstance(value, list):
        iterable = value
    else:
        iterable = []

    for item in iterable:
        if isinstance(item, list):
            for nested in item:
                name = _metric_name(nested)
                if name and name not in names:
                    names.append(name)
            continue
        name = _metric_name(item)
        if name and name not in names:
            names.append(name)
    return names


def _metric_name(item) -> str:
    if isinstance(item, dict):
        return str(item.get("name") or item.get("column") or "").strip()
    return str(item or "").strip()


def _load_model_metric_groups(models_dir: Path) -> dict[str, dict[str, list[str]]]:
    metric_groups = {}
    if not models_dir.exists():
        return metric_groups

    for model_path in models_dir.glob("*.yaml"):
        try:
            data = yaml.safe_load(model_path.read_text(encoding="utf-8")) or {}
        except Exception:
            continue
        if not isinstance(data, dict):
            continue
        table_name = str(data.get("name") or model_path.stem)
        groups = {
            "atomic_metrics": _metric_names(data.get("atomic_metrics")),
            "derived_metrics": _metric_names(data.get("derived_metrics")),
            "calculated_metrics": _metric_names(data.get("calculated_metrics")),
        }
        if any(groups.values()):
            metric_groups[table_name] = groups
    return metric_groups


def _table_from_node(node_id: str) -> str:
    return node_id.rsplit(".", 1)[0]


def extract_dependencies(lineage_data: dict) -> tuple[dict, dict]:
    """提取表级上下游关系"""
    upstream = defaultdict(set)
    downstream = defaultdict(set)

    for e in lineage_data.get("edges", []):
        src = _table_from_node(e["source"])
        tgt = _table_from_node(e["target"])
        if src != tgt:
            upstream[tgt].add(src)
            downstream[src].add(tgt)

    for ie in lineage_data.get("indirect_edges", []):
        src = _table_from_node(ie["source"])
        tgt = ie["target_table"]
        if src != tgt:
            upstream[tgt].add(src)
            downstream[src].add(tgt)

    return dict(upstream), dict(downstream)


def extract_column_lineage(lineage_data: dict,
                           table_name: str) -> list[dict[str, str]]:
    """提取目标表的字段级血缘表达式。"""
    lineage = []
    for edge in lineage_data.get("edges", []):
        target = str(edge.get("target") or "")
        if _table_from_node(target) != table_name:
            continue
        lineage.append({
            "source": str(edge.get("source") or ""),
            "target": target,
            "expression": str(edge.get("expression") or ""),
            "source_file": str(edge.get("source_file") or ""),
        })
    return lineage


def build_contexts(project: str,
                   lineage_data: dict,
                   ddl_dir: Path = None,
                   tasks_dir: Path = None) -> list[TableContext]:
    """为 DWD/DWS 层所有表构建分类上下文"""
    if not ddl_dir:
        ddl_dir = Path(__file__).resolve().parent.parent / project / "ddl"
    if not tasks_dir:
        tasks_dir = Path(__file__).resolve().parent.parent / project / "tasks"

    upstream, downstream = extract_dependencies(lineage_data)
    models_dir = Path(__file__).resolve().parent.parent / project / "models"
    metric_groups = _load_model_metric_groups(models_dir)
    contexts = []

    memo = {}
    def get_depth_from_ods(table_name: str, visiting: set = None) -> int:
        if visiting is None: visiting = set()
        if table_name in memo: return memo[table_name]
        if table_name in visiting: return 0
        visiting.add(table_name)
        
        parents = upstream.get(table_name, set())
        if not parents:
            result = 0 if table_name.startswith("ods_") else 1
        else:
            result = min(get_depth_from_ods(p, visiting) for p in parents) + 1
            
        visiting.remove(table_name)
        memo[table_name] = result
        return result

    for table in lineage_data.get("tables", []):
        layer = table.get("layer", "")
        if layer not in ("DWD", "DWS", "DIM"):
            continue

        name = table["name"]

        # Read DDL
        ddl_path = ddl_dir / f"{name}.sql"
        ddl_content = ddl_path.read_text(
            encoding="utf-8") if ddl_path.exists() else ""

        # Read ETL
        task_path = tasks_dir / f"{name}.sql"
        etl_content = task_path.read_text(
            encoding="utf-8") if task_path.exists() else ""
        upstream_tables = sorted(list(upstream.get(name, set())))
        upstream_metric_groups = {
            upstream_table: metric_groups[upstream_table]
            for upstream_table in upstream_tables
            if upstream_table in metric_groups
        }

        contexts.append(
            TableContext(table_name=name,
                         layer=layer,
                         ddl=ddl_content,
                         etl_sql=etl_content,
                         upstream_tables=upstream_tables,
                         downstream_tables=sorted(
                             list(downstream.get(name, set()))),
                         depth_from_ods=get_depth_from_ods(name),
                         upstream_metric_groups=upstream_metric_groups,
                         column_lineage=extract_column_lineage(
                             lineage_data, name)))

    return contexts
