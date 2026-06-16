from pathlib import Path
from dataclasses import dataclass, field

import yaml

import config
from config import get_business_domain_config, load_model_metadata
from assess.project_facts.business_semantics import load_business_semantics_catalog
from lineage.view import LineageView

DATA_DOMAIN_LAYERS = {"DWD"}
BUSINESS_AREA_LAYERS = {"DWD", "DWS"}


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
    column_lineage: list[dict] = field(default_factory=list)
    declared_data_domain: str = ""
    declared_business_area: str = ""
    project_context: str = ""
    business_domain_options: dict = field(default_factory=dict)
    business_semantics_options: dict = field(default_factory=dict)


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


def _catalog_option_entries(raw_entries) -> list[dict]:
    entries = []
    if not isinstance(raw_entries, list):
        return entries
    for entry in raw_entries:
        if not isinstance(entry, dict):
            continue
        code = str(entry.get("code") or "").strip()
        if not code:
            continue
        item = {
            "code": code,
            "name": str(entry.get("name") or "").strip(),
        }
        data_domain = str(entry.get("data_domain") or "").strip()
        business_area = str(entry.get("business_area") or "").strip()
        if data_domain:
            item["data_domain"] = data_domain
        if business_area:
            item["business_area"] = business_area
        entries.append(item)
    return entries


def _business_semantics_prompt_options(project: str) -> dict:
    catalog = load_business_semantics_catalog(project)
    if not catalog:
        return {}
    options = {}
    processes = _catalog_option_entries(catalog.get("business_processes") or [])
    subjects = _catalog_option_entries(catalog.get("semantic_subjects") or [])
    if processes:
        options["business_processes"] = processes
    if subjects:
        options["semantic_subjects"] = subjects
    return options


def _project_context(project: str) -> str:
    catalog = load_business_semantics_catalog(project)
    if not catalog:
        return ""
    return str(catalog.get("project_context") or "").strip()


def extract_dependencies(lineage_data: dict) -> tuple[dict, dict]:
    """提取正式资产表级上下游关系，过滤并穿透临时表。"""
    return LineageView.from_data("", lineage_data).table_graph()


def extract_column_lineage(lineage_data: dict,
                           table_name: str) -> list[dict]:
    """提取正式资产字段血缘，过滤并穿透临时字段。"""
    return LineageView.from_data("", lineage_data).column_lineage_for_table(
        table_name
    )


def _project_dir(project: str) -> Path:
    project_cfg = config.PROJECT_CONFIG.get(project) or {}
    if project_cfg.get("dir"):
        return config.PROJECT_ROOT / project_cfg["dir"]
    return Path(__file__).resolve().parent.parent / project


def build_contexts(project: str,
                   lineage_data: dict,
                   ddl_dir: Path = None,
                   tasks_dir: Path = None,
                   layers: set[str] | None = None) -> list[TableContext]:
    """为 DWD/DWS/DIM 层所有表构建分类上下文"""
    project_dir = _project_dir(project)
    if not ddl_dir:
        ddl_dir = project_dir / "ddl"
    if not tasks_dir:
        tasks_dir = project_dir / "tasks"

    lineage_view = LineageView.from_data(project, lineage_data)
    upstream, downstream = lineage_view.table_graph()
    target_layers = set(layers or ("DWD", "DWS", "DIM"))
    models_dir = project_dir / "models"
    metric_groups = _load_model_metric_groups(models_dir)
    model_metadata = load_model_metadata(project)
    business_domain_config = get_business_domain_config(project)
    business_domain_options = (
        business_domain_config.prompt_options()
        if business_domain_config
        else {}
    )
    business_semantics_options = _business_semantics_prompt_options(project)
    project_context = _project_context(project)
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
        if layer not in target_layers:
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
        metadata = model_metadata.get(name, {})

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
                         column_lineage=(
                             lineage_view.column_lineage_for_table(name)
                         ),
                         declared_data_domain=(
                             str(metadata.get("data_domain") or "")
                             if layer in DATA_DOMAIN_LAYERS
                             else ""
                         ),
                         declared_business_area=(
                             str(metadata.get("business_area") or "")
                             if layer in BUSINESS_AREA_LAYERS
                             else ""
                         ),
                         project_context=project_context,
                         business_domain_options=business_domain_options,
                         business_semantics_options=business_semantics_options))

    return contexts
