#!/usr/bin/env python3
"""
重构分析: 检测 DDL / 作业变更, 血缘追踪下游, 锚点发现, 分区选择
输出 refact_metadata.json → 供 verify_run.py / verify_check.py 使用
"""

import json, argparse, subprocess, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import sqlglot
from sqlglot import exp
from sqlglot.errors import ErrorLevel

from lineage.job_dag import JobDAG

from ddl_deriver.ddl_deriver import (
    _find_git_root,
    _get_merge_base,
    _git_cmd,
    derive_ddl_changes,
    load_tables_from_dir,
    _load_git_tables,
    changes_to_json,
)

from config import PROJECT_CONFIG, DORIS_HOST, DORIS_PORT, DORIS_USER

# ============================================================
# 环境配置
# ============================================================

_LAYER_PREFIX = {"ods_": "ODS", "dwd_": "DWD", "dws_": "DWS", "ads_": "ADS"}

# ============================================================
# 辅助函数
# ============================================================

def determine_layer(table_name: str) -> str:
    for prefix, layer in _LAYER_PREFIX.items():
        if table_name.startswith(prefix):
            return layer
    return "OTHER"


def parse_partition_col_from_ddl(ddl_text: str) -> str:
    """从 CREATE TABLE DDL 文本中解析 PARTITION BY RANGE 列名。"""
    if not ddl_text:
        return ""
    for stmt in sqlglot.parse(ddl_text, dialect="doris",
                               error_level=ErrorLevel.IGNORE):
        if stmt is None:
            continue
        if isinstance(stmt, exp.Create):
            for prop in stmt.find_all(exp.PartitionByRangeProperty):
                for c in prop.find_all(exp.Column):
                    return c.name
    return ""


def get_partition_col(table_name: str, layer: str,
                      baseline_ddl: dict = None) -> str:
    """获取表的分区列。从基线 DDL 解析。"""
    if baseline_ddl:
        ddl_text = baseline_ddl.get(table_name)
        if ddl_text:
            col = parse_partition_col_from_ddl(ddl_text)
            if col:
                return col
    return ""


def strip_insert_data(ddl_text: str) -> str:
    lines = []
    for line in ddl_text.splitlines():
        if line.strip().upper().startswith("INSERT"):
            break
        lines.append(line)
    return "\n".join(lines)


def run_doris(sql: str, db: str = "") -> str:
    r = subprocess.run(
        ["mysql", f"-h{DORIS_HOST}", f"-P{DORIS_PORT}", f"-u{DORIS_USER}",
         db, "-N", "-B", "-e", sql],
        capture_output=True, text=True, timeout=30,
    )
    if r.returncode != 0:
        raise RuntimeError(f"Doris 错误: {r.stderr.strip()}")
    return r.stdout.strip()


# ============================================================
# 主流程
# ============================================================

def main():
    parser = argparse.ArgumentParser(
        description="重构分析: 检测变更 + 血缘追踪 + 锚点发现 + 分区选择"
    )
    parser.add_argument("--project", default="shop", choices=list(PROJECT_CONFIG.keys()))
    parser.add_argument("--output", default=None,
                        help="元数据路径 (默认 refact/refact_metadata.json)")
    parser.add_argument("--partition", default=None, help="手工指定分区")
    parser.add_argument("--etl-date", default=None, help="手工指定 @etl_date")
    parser.add_argument("--anchor", nargs="*", default=None, help="手工指定锚点表")
    parser.add_argument("--base-branch", default="main", help="Git 基线分支")
    args = parser.parse_args()

    cfg = PROJECT_CONFIG[args.project]
    project_db = cfg["db"]
    qa_db = cfg["qa_db"]
    root = Path(__file__).resolve().parent.parent
    ddl_rel = f"{cfg['dir']}/ddl"
    tasks_dir = root / cfg["dir"] / "tasks"
    lineage_path = root / "lineage" / f"lineage_data_{args.project}.json"
    out_path = Path(args.output) if args.output else root / "refact" / "refact_metadata.json"

    # ── Git 信息 ──
    print("=== Git 变更检测 ===")
    repo = _find_git_root(root)
    base_ref = _get_merge_base(repo, args.base_branch)
    branch = _git_cmd(repo, "rev-parse", "--abbrev-ref", "HEAD")
    print(f"  分支: {branch}  基线: {base_ref[:12]}  ({args.base_branch})")

    # ── DDL 变更 ──
    print("\n--- DDL 变更 ---")
    old_tables = _load_git_tables(repo, ddl_rel, base_ref)
    new_tables = load_tables_from_dir(repo / ddl_rel)
    ddl_changes = derive_ddl_changes(old_tables, new_tables)

    ddl_table_names = set()
    lineage_search_names = set()
    for ch in ddl_changes:
        if ch.change_type == "RENAME":
            old_short = ch.old_name.split(".")[-1] if "." in ch.old_name else ch.old_name
            new_short = ch.new_name.split(".")[-1] if "." in ch.new_name else ch.new_name
            ddl_table_names.add(new_short)
            lineage_search_names.add(old_short)
            lineage_search_names.add(new_short)
        else:
            name = getattr(ch, "table_name", None) or getattr(ch, "old_name", None) or ""
            short = name.split(".")[-1] if "." in name else name
            ddl_table_names.add(short)
            lineage_search_names.add(short)
    print(f"  旧 DDL: {len(old_tables)} 张表  新 DDL: {len(new_tables)} 张表")
    print(f"  变更: {len(ddl_changes)} 条")
    for ch in ddl_changes:
        if ch.change_type == "RENAME":
            print(f"    [{ch.change_type}] {ch.old_name} → {ch.new_name}")
        else:
            name = getattr(ch, "table_name", None) or getattr(ch, "old_name", None) or ""
            print(f"    [{ch.change_type}] {name}")

    # ── 作业变更 ──
    print("\n--- 作业变更 ---")
    diff_raw = _git_cmd(repo, "diff", "--no-renames", "--name-only", f"{base_ref}...HEAD", "--",
                        f"{cfg['dir']}/tasks/*.sql")
    modified_jobs = set()
    for p in diff_raw.splitlines():
        p = p.strip()
        if p:
            modified_jobs.add(Path(p).stem)
    print(f"  修改作业: {len(modified_jobs)} 个")
    for j in sorted(modified_jobs):
        print(f"    {j}")

    # ── 血缘数据 ──
    print("\n=== 血缘追踪 ===")
    if not lineage_path.exists():
        print(f"  [WARN] 血缘文件不存在: {lineage_path}")
        print("  请先运行 python lineage/lineage_extractor.py --project {args.project}")
        sys.exit(1)
    with open(lineage_path, encoding="utf-8") as f:
        lineage = json.load(f)
    dag = JobDAG(lineage.get("edges", []))
    n = len(lineage.get("tables", []))
    e = len(lineage.get("edges", []))
    print(f"  血缘: {n} 表, {e} 边")

    # ── 变更表集合 ──
    table_to_job = {f.stem: f.stem for f in tasks_dir.glob("*.sql")}
    modified_tables = set(ddl_table_names) | modified_jobs

    # ── 下游追踪 ──
    downstream = dag.bfs_downstream(lineage_search_names)
    print(f"  修改表: {sorted(modified_tables)}")
    print(f"  表级下游表: {sorted(downstream)}")

    # ── 变更源: DDL 变更表 + 作业变更 ──
    changed_sources = set(modified_tables) | modified_jobs

    # ── 锚点: 变更源的直接下游作业产出的表 (不限层) ──
    if args.anchor:
        anchors = list(args.anchor)
    else:
        anchors = set()
        for s in changed_sources:
            anchors.update(dag._deps.get(s, set()))
        anchors = sorted(anchors)
    print(f"  锚点表: {anchors}")

    # ── 全部受影响 (用于 jobs_to_run + 基线 DDL) ──
    all_affected = changed_sources | set(anchors)

    # ── 基线 DDL (先加载, 分区选择需要它解析列名) ──
    print("\n=== 基线 DDL ===")
    baseline_ddl = {}
    ls_raw = _git_cmd(repo, "ls-tree", "-r", "--name-only", base_ref, "--",
                      ddl_rel)
    for rel_path in ls_raw.splitlines():
        rel_path = rel_path.strip()
        if not rel_path.endswith(".sql"):
            continue
        try:
            content = _git_cmd(repo, "show", f"{base_ref}:{rel_path}")
            baseline_ddl[Path(rel_path).stem] = strip_insert_data(content)
        except Exception as e:
            print(f"  [WARN] 无法获取基线 DDL {rel_path}: {e}")
    print(f"  基线 DDL: {len(baseline_ddl)} 张表")

    # ── 分区选择 ──
    print("\n=== 分区选择 ===")
    pinfo = {"partition": None, "etl_date": None, "per_table": {}}
    if anchors:
        per_table = {}
        for a in anchors:
            pc = get_partition_col(a, determine_layer(a), baseline_ddl)
            try:
                val = run_doris(
                    f"SELECT MAX({pc}) FROM {project_db}.{a}"
                )
                if val and val != "NULL":
                    per_table[a] = {"partition_col": pc, "value": val}
                    print(f"  {a}: MAX({pc}) = {val}")
                else:
                    print(f"  {a}: 无数据")
            except Exception as ex:
                print(f"  [WARN] 查询 {a} 分区失败: {ex}")

        if per_table:
            if args.partition:
                shared = args.partition
            else:
                values = [v["value"] for v in per_table.values()]
                shared = min(values) if values else None

            if shared:
                pinfo["partition"] = shared
                pinfo["etl_date"] = args.etl_date or shared
                for a in per_table:
                    pinfo["per_table"][a] = {
                        "partition_col": per_table[a]["partition_col"],
                        "value": shared,
                    }
                print(f"  选择分区: {shared}")

    # ── 需执行作业 ──
    print("\n=== 执行计划 ===")
    jobs_set = set()
    for t in all_affected:
        if t in table_to_job:
            jobs_set.add(t)

    try:
        jobs_sorted = dag.topological_sort(jobs_set)
    except ValueError:
        jobs_sorted = sorted(jobs_set, key=lambda j: {"dwd_": 1, "dws_": 2, "ads_": 3}.get(j[:4], 4))

    jobs_to_run = []
    for jn in jobs_sorted:
        fpath = tasks_dir / f"{jn}.sql"
        if not fpath.exists():
            continue
        sql_text = fpath.read_text(encoding="utf-8")
        jobs_to_run.append({
            "job": jn,
            "file": str(fpath.relative_to(root)),
            "layer": determine_layer(jn),
            "target": jn,
            "needs_etl_date": "@etl_date" in sql_text,
        })
    print(f"  需执行: {len(jobs_to_run)} 个作业")
    for j in jobs_to_run:
        ed = " [@etl_date]" if j["needs_etl_date"] else ""
        print(f"    [{j['layer']}] {j['job']}{ed}")

    # ── 过滤基线 DDL ──
    def _short_name(name: str) -> str:
        return name.split(".")[-1] if "." in name else name

    phase2_creates = set()
    for ch in ddl_changes:
        if ch.change_type == "CREATE":
            phase2_creates.add(_short_name(ch.table_name))
        elif ch.change_type == "RENAME":
            phase2_creates.add(_short_name(ch.new_name))

    needed_baseline = set()
    for ch in ddl_changes:
        if ch.change_type == "RENAME":
            needed_baseline.add(_short_name(ch.old_name))
        elif ch.change_type == "ALTER":
            needed_baseline.add(_short_name(ch.table_name))
    for j in jobs_to_run:
        if j["target"] not in phase2_creates:
            needed_baseline.add(j["target"])
    needed_baseline.update(anchors)
    baseline_ddl = {k: v for k, v in baseline_ddl.items() if k in needed_baseline}
    print(f"\n=== 基线 DDL (过滤后: {len(baseline_ddl)} 张) ===")

    # ── 校验配置 ──
    checks = []
    for a in anchors:
        if a in pinfo.get("per_table", {}):
            pi = pinfo["per_table"][a]
            checks.append({
                "table": a, "method": "count",
                "partition_col": pi["partition_col"],
                "partition_value": pi["value"],
            })
            checks.append({
                "table": a, "method": "row_compare",
                "partition_col": pi["partition_col"],
                "partition_value": pi["value"],
            })

    # ── 输出 ──
    meta = {
        "project": args.project,
        "project_db": project_db,
        "qa_db": qa_db,
        "host": DORIS_HOST,
        "port": int(DORIS_PORT),
        "git": {
            "branch": branch,
            "base_branch": args.base_branch,
            "merge_base": base_ref,
        },
        "baseline_ddl": baseline_ddl,
        "ddl_changes": changes_to_json(ddl_changes)["changes"],
        "modified_jobs": sorted(modified_jobs),
        "modified_tables": sorted(modified_tables),
        "downstream_tables": sorted(downstream),
        "anchors": anchors,
        "partition_info": pinfo,
        "jobs_to_run": jobs_to_run,
        "verification": {"checks": checks},
    }

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2),
                        encoding="utf-8")
    print(f"\n=== 元数据已写入: {out_path} ===")
    print(f"  DDL 变更: {len(ddl_changes)}")
    print(f"  改动作业: {len(modified_jobs)}")
    print(f"  执行作业: {len(jobs_to_run)}")
    print(f"  锚点表:   {anchors}")
    print(f"  分区:     {pinfo.get('partition', 'N/A')}")

    if not anchors:
        print()
        print("  ⚠ 警告: 无锚点表 (没有下游作业直接依赖变更结果)")
        print("    后续 verify_run.py 虽能执行作业，但 verify_check.py 将无表可对比校验")
        print("    数据一致性无法自动验证，请确认变更是否符合预期")


if __name__ == "__main__":
    main()
