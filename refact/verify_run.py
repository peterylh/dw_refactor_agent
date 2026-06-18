#!/usr/bin/env python3
"""
验证执行: 根据元数据重建验证库 + SQL Glot 表映射执行作业

工作流程:
  Phase 0: DROP DATABASE / CREATE DATABASE (验证库)
  Phase 1: 基线建表 (baseline_ddl 还原到 merge_base 状态)
  Phase 2: 应用 DDL 变更 (ADD COLUMN / DROP TABLE / CREATE TABLE 等)
  Phase 3: 按依赖顺序执行 ETL 作业 (读取生产, 写入验证)

用法:
  python refact/verify_run.py --metadata refact/refact_metadata.json
  python refact/verify_run.py --metadata refact/refact_metadata.json --dry-run
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import sqlglot
from sqlglot import exp
from sqlglot.errors import ErrorLevel

from config import TEXT_ENCODING, get_mysql_cmd
from doris_sql import extract_create_table_name

# ============================================================
# SQL 执行
# ============================================================


def run_sql(sql: str, db: str = "", qa: bool = False) -> str:
    """执行单条 SQL, 返回 stdout."""
    cmd = get_mysql_cmd("prod", qa=qa)
    if db:
        cmd.append(db)
    cmd.extend(["-e", sql])
    r = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=300,
    )
    if r.returncode != 0:
        print(f"  ERROR: {r.stderr.strip()}")
        sys.exit(1)
    return r.stdout


def run_sql_text(sql_text: str, db: str = "", qa: bool = False) -> str:
    """通过 stdin 传入多语句 SQL 文本."""
    cmd = get_mysql_cmd("prod", qa=qa)
    if db:
        cmd.append(db)
    r = subprocess.run(
        cmd,
        input=sql_text,
        capture_output=True,
        text=True,
        timeout=300,
    )
    if r.returncode != 0:
        print(f"  ERROR: {r.stderr.strip()}")
        sys.exit(1)
    return r.stdout


# ============================================================
# SQL Glot 表映射重写
# ============================================================


def _get_dml_target(stmt):
    """返回当前语句的 DML 目标表名 (无 db 前缀), 非 DML 返回 None."""
    if isinstance(stmt, exp.Insert):
        target = stmt.this
        if isinstance(target, exp.Table):
            return target.name
        if isinstance(target, exp.Schema) and isinstance(
            target.this, exp.Table
        ):
            return target.this.name
    elif isinstance(stmt, (exp.Update, exp.Delete)):
        if isinstance(stmt.this, exp.Table):
            return stmt.this.name
    elif isinstance(stmt, exp.TruncateTable):
        # TruncateTable stores table in expressions, not this
        if stmt.expressions:
            tbl = stmt.expressions[0]
            if isinstance(tbl, exp.Table):
                return tbl.name
    elif isinstance(stmt, exp.Create):
        # CTAS: CREATE TABLE ... AS SELECT
        if isinstance(stmt.this, exp.Schema) and isinstance(
            stmt.this.this, exp.Table
        ):
            return stmt.this.this.name
    elif isinstance(stmt, exp.Command) and str(stmt.this).upper() == "CREATE":
        table_name = extract_create_table_name(stmt.sql(dialect="doris"))
        return table_name.split(".")[-1] if table_name else None
    return None


def rewrite_sql(
    sql_text: str, prod_db: str, qa_db: str, recalculated: set
) -> str:
    """
    表映射重写规则:
      表是 DML 目标                  → qa_db  (写入验证库)
      表在前序已执行作业的 target 中   → qa_db  (读刚算好的 QA 数据)
      其他 (ODS / 未修改中间表)       → prod_db (读生产)
    """
    statements = sqlglot.parse(
        sql_text, dialect="doris", error_level=ErrorLevel.IGNORE
    )
    rewritten = []
    for stmt in statements:
        if stmt is None:
            continue

        dml_target = _get_dml_target(stmt)

        # 收集所有表引用 → (节点, 目标库)
        todo = []
        for table in stmt.find_all(exp.Table):
            db_node = table.args.get("db")
            if db_node is None:
                continue
            tname = table.name
            # DML 目标 → QA
            if tname == dml_target or tname in recalculated:
                todo.append((table, qa_db))
            # 其余保持生产
            else:
                pass  # prod_db 不变

        for table, target_db in todo:
            table.args["db"] = exp.to_identifier(target_db)

        rewritten.append(stmt.sql(dialect="doris"))

    if not rewritten:
        return ""
    return ";\n".join(rewritten) + ";"


# ============================================================
# 主流程
# ============================================================


def main():
    parser = argparse.ArgumentParser(
        description="验证执行: 重建验证库 + SQL Glot 表映射执行"
    )
    parser.add_argument("--metadata", required=True, help="元数据 JSON 路径")
    parser.add_argument(
        "--dry-run", action="store_true", help="只输出执行计划, 不连接数据库"
    )
    args = parser.parse_args()

    meta = json.loads(Path(args.metadata).read_text(encoding=TEXT_ENCODING))
    prod_db = meta["project_db"]
    qa_db = meta["qa_db"]
    etl_date = meta.get("partition_info", {}).get("etl_date")
    baseline_ddl = meta.get("baseline_ddl", {})
    ddl_changes = meta.get("ddl_changes", [])
    jobs_to_run = meta.get("jobs_to_run", [])

    anchors = meta.get("anchors", [])
    checks = meta.get("verification", {}).get("checks", [])
    if not anchors and not checks:
        print("  ⚠ 警告: 无锚点表且无校验配置")
        print(
            "    作业会正常执行，但无法通过 verify_check.py 对比校验数据一致性"
        )
        print("    如果只是想确认作业不报错，可继续执行\n")

    if args.dry_run:
        _dry_run(meta)
        return

    # ── Phase 0: 重置验证库 ──
    print("=" * 60)
    print(f"Phase 0: 重置验证数据库 {qa_db}")
    run_sql(f"DROP DATABASE IF EXISTS {qa_db}", "information_schema", qa=True)
    run_sql(f"CREATE DATABASE {qa_db}", "information_schema", qa=True)
    print(f"  {qa_db} 已重建")

    # ── Phase 1: 基线建表 ──
    print(f"\n{'=' * 60}")
    print(f"Phase 1: 基线建表 ({len(baseline_ddl)} 张)")
    for tname in sorted(baseline_ddl):
        ddl_raw = baseline_ddl[tname]
        # 不处理空 DDL
        if not ddl_raw.strip():
            continue
        ddl_qa = ddl_raw.replace(f"{prod_db}.", f"{qa_db}.")
        try:
            run_sql(ddl_qa, qa_db, qa=True)
            print(f"  [CREATE] {qa_db}.{tname}")
        except Exception as e:
            print(f"  [FAIL] {qa_db}.{tname}: {e}")
            sys.exit(1)

    # ── Phase 2: 应用 DDL 变更 ──
    if ddl_changes:
        print(f"\n{'-' * 60}")
        print(f"Phase 2: 应用 DDL 变更 ({len(ddl_changes)} 条)")
        for ch in ddl_changes:
            sql = ch.get("sql", "")
            if not sql.strip():
                continue
            sql_qa = sql.replace(f"{prod_db}.", f"{qa_db}.")
            try:
                run_sql(sql_qa, qa_db, qa=True)
                print(
                    f"  [{ch.get('change_type')}] {ch.get('table_name', '?')}"
                )
            except Exception as e:
                print(f"  [SKIP] {ch.get('change_type')}: {e}")

    # ── Phase 3: 执行作业 ──
    print(f"\n{'=' * 60}")
    print(f"Phase 3: 执行作业 ({len(jobs_to_run)} 个)")
    recalculated = set()
    root = Path(__file__).resolve().parent.parent

    for idx, job in enumerate(jobs_to_run, 1):
        jname = job["job"]
        jfile = job["file"]
        layer = job.get("layer", "?")
        needs_ed = job.get("needs_etl_date", False)

        print(f"\n  --- {idx}/{len(jobs_to_run)}: [{layer}] {jname} ---")
        fpath = root / jfile
        if not fpath.exists():
            print(f"  [SKIP] 文件不存在: {fpath}")
            continue

        sql_text = fpath.read_text(encoding=TEXT_ENCODING)

        # SQL Glot 表映射重写
        rewritten = rewrite_sql(sql_text, prod_db, qa_db, recalculated)

        # 需要 @etl_date 的作业, 在执行前注入变量
        if needs_ed and etl_date:
            rewritten = f"SET @etl_date = '{etl_date}';\n" + rewritten

        try:
            run_sql_text(rewritten, qa_db, qa=True)
            print(f"  + {qa_db}.{jname}")
        except Exception as e:
            print(f"  [FAIL] {jname}: {e}")
            sys.exit(1)

        recalculated.add(jname)

    print(f"\n{'=' * 60}")
    print(f"验证执行完成! 共执行 {len(jobs_to_run)} 个作业, 目标库: {qa_db}")


# ============================================================
# Dry Run
# ============================================================


def _dry_run(meta):
    qa_db = meta["qa_db"]
    prod_db = meta["project_db"]
    etl_date = meta.get("partition_info", {}).get("etl_date")
    baseline_ddl = meta.get("baseline_ddl", {})
    ddl_changes = meta.get("ddl_changes", [])
    jobs_to_run = meta.get("jobs_to_run", [])
    root = Path(__file__).resolve().parent.parent

    print(f"{'=' * 60}")
    print("=== DRY RUN ===")
    print(f"  项目: {meta['project']}")
    print(f"  分支: {meta['git']['branch']}")
    print(f"  基线: {meta['git']['merge_base'][:12]}...")
    print(f"  生产库: {prod_db} → 验证库: {qa_db}")
    print(f"  锚点: {meta['anchors']}")
    print(f"  分区: {meta['partition_info'].get('partition', 'N/A')}")
    checks = meta.get("verification", {}).get("checks", [])
    if not meta.get("anchors") and not checks:
        print()
        print(
            "  ⚠ 警告: 无锚点表且无校验配置，verify_check.py 将无表可对比校验"
        )

    print("\n--- Phase 0: 重置验证库 ---")
    print(f"  DROP DATABASE IF EXISTS {qa_db}")
    print(f"  CREATE DATABASE {qa_db}")

    print(f"\n--- Phase 1: 基线建表 ({len(baseline_ddl)} 张) ---")
    for tname in sorted(baseline_ddl):
        print(f"  [CREATE] {qa_db}.{tname}")

    print(f"\n--- Phase 2: DDL 变更 ({len(ddl_changes)} 条) ---")
    for ch in ddl_changes:
        name = ch.get("table_name", ch.get("old_name", "?"))
        print(f"  [{ch['change_type']}] {name}")

    print(f"\n--- Phase 3: 作业 ({len(jobs_to_run)} 个) ---")
    recalculated = set()
    for idx, job in enumerate(jobs_to_run, 1):
        jname = job["job"]
        layer = job.get("layer", "?")
        jfile = job["file"]
        fpath = root / jfile

        print(f"\n  {idx}/{len(jobs_to_run)}: [{layer}] {jname}")
        if not fpath.exists():
            print("    [SKIP] 文件不存在")
            continue

        sql_text = fpath.read_text(encoding=TEXT_ENCODING)
        rewritten = rewrite_sql(sql_text, prod_db, qa_db, recalculated)
        needs_ed = job.get("needs_etl_date", False)

        if needs_ed and etl_date:
            print(f"    SET @etl_date = '{etl_date}';")

        for line in rewritten.splitlines()[:8]:
            print(f"    {line}")
        total = len(rewritten.splitlines())
        if total > 8:
            print(f"    ... ({total} 行)")

        recalculated.add(jname)

    checks = meta.get("verification", {}).get("checks", [])
    if checks:
        print(f"\n--- 校验检查 ({len(checks)} 项) ---")
        for ck in checks:
            print(
                f"  [{ck['method']}] {qa_db}.{ck['table']} "
                f"WHERE {ck['partition_col']} = '{ck['partition_value']}'"
            )


if __name__ == "__main__":
    main()
