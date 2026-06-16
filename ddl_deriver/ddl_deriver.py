#!/usr/bin/env python3
"""
DDL 变更自动推导工具。

支持两种模式:

  dir 模式 (默认):
    接受 old/new 两套 DDL 目录,自动推导出对应的 Doris DDL 变更语句:
    - 表重命名: 文件删除 + 新增,内容结构高度相似 → RENAME TABLE
    - 新增表:  仅新目录有 → CREATE TABLE
    - 删除表:  仅旧目录有 → DROP TABLE
    - 修改表:  同名文件内容变化 → ALTER TABLE (列级 ADD/DROP/MODIFY)

  git 模式:
    对比 Git 分支与工作区的 DDL 文件差异,自动推导变更:
    - 以 merge-base(当前分支与 main 的分叉点)为基线
    - 读取工作区文件为当前版本
    - 推导结果同上
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import List, Optional, Tuple

import sqlglot
from sqlglot import exp
from sqlglot.errors import ErrorLevel

from doris_sql import (
    extract_doris_distribution_column,
    extract_doris_key,
    normalize_create_table_for_sqlglot,
)

# ============================================================
# 数据模型
# ============================================================


@dataclass
class ColumnDef:
    name: str
    data_type: str
    nullable: bool = True
    default: Optional[str] = None
    comment: Optional[str] = None
    is_key: bool = False

    def signature(self) -> str:
        """用于结构比对的签名(排除 comment)."""
        return f"{self.name}:{self.data_type}:{self.nullable}:{self.default or 'N/A'}"


@dataclass
class TableDef:
    full_name: str  # shop_dm.ods_order
    short_name: str  # ods_order
    columns: List[ColumnDef] = field(default_factory=list)
    engine: str = "OLAP"
    key_type: str = "DUPLICATE"
    key_columns: List[str] = field(default_factory=list)
    distribution_col: str = ""
    raw_ddl: str = ""  # 完整的 CREATE TABLE 语句
    table_id: str = ""  # UUID,同一逻辑表跨重命名保持不变

    def column_names(self) -> set:
        return {c.name for c in self.columns}

    def column_map(self):
        return {c.name: c for c in self.columns}


# ============================================================
# 变更类型
# ============================================================


@dataclass
class DDLChange:
    change_type: str  # CREATE | DROP | RENAME | ALTER


@dataclass
class CreateTable(DDLChange):
    table_def: TableDef

    def __init__(self, table_def: TableDef):
        super().__init__("CREATE")
        self.table_def = table_def

    def to_sql(self) -> str:
        return self.table_def.raw_ddl


@dataclass
class DropTable(DDLChange):
    table_name: str

    def __init__(self, table_name: str):
        super().__init__("DROP")
        self.table_name = table_name

    def to_sql(self) -> str:
        return f"DROP TABLE IF EXISTS {self.table_name};"


@dataclass
class RenameTable(DDLChange):
    old_name: str
    new_name: str
    old_short: str = ""
    new_short: str = ""

    def __init__(self, old_table: TableDef, new_table: TableDef):
        super().__init__("RENAME")
        self.old_name = old_table.full_name
        self.new_name = new_table.full_name
        self.old_short = old_table.short_name
        self.new_short = new_table.short_name

    def to_sql(self) -> str:
        db_prefix = ""
        if "." in self.old_name:
            db_prefix = self.old_name.split(".")[0] + "."
        return (
            f"ALTER TABLE {db_prefix}{self.old_short} RENAME {self.new_short};"
        )


@dataclass
class AlterTable(DDLChange):
    table_name: str
    old_def: TableDef
    new_def: TableDef
    adds: List[ColumnDef] = field(default_factory=list)
    drops: List[ColumnDef] = field(default_factory=list)
    modifies: List[Tuple[ColumnDef, ColumnDef]] = field(
        default_factory=list
    )  # (old, new)
    renames: List[Tuple[str, str]] = field(
        default_factory=list
    )  # (old_name, new_name)

    def __init__(
        self,
        table_name: str,
        old_def: TableDef,
        new_def: TableDef,
        adds=None,
        drops=None,
        modifies=None,
        renames=None,
    ):
        super().__init__("ALTER")
        self.table_name = table_name
        self.old_def = old_def
        self.new_def = new_def
        self.adds = adds or []
        self.drops = drops or []
        self.modifies = modifies or []
        self.renames = renames or []

    def to_sql(self) -> str:
        parts = []
        for col in self.drops:
            parts.append(f"DROP COLUMN {col.name}")
        for old_name, new_name in self.renames:
            parts.append(f"RENAME COLUMN {old_name} {new_name}")
        for col in self.adds:
            nullable = "NULL" if col.nullable else "NOT NULL"
            default = f"DEFAULT {col.default}" if col.default else ""
            comment = f"COMMENT '{col.comment}'" if col.comment else ""
            parts.append(
                f"ADD COLUMN {col.name} {col.data_type} {nullable} {default} {comment}".strip()
            )
        for _old, new in self.modifies:
            nullable = "NULL" if new.nullable else "NOT NULL"
            default = f"DEFAULT {new.default}" if new.default else ""
            comment = f"COMMENT '{new.comment}'" if new.comment else ""
            parts.append(
                f"MODIFY COLUMN {new.name} {new.data_type} {nullable} {default} {comment}".strip()
            )
        if not parts:
            return (
                f"-- ALTER TABLE {self.table_name}: 无结构化变更(仅注释变更)"
            )
        alter_body = ",\n    ".join(parts)
        return f"ALTER TABLE {self.table_name}\n    {alter_body};"


# ============================================================
# DDL 解析
# ============================================================

# 正则: 匹配 -- table_id: <uuid>
TABLE_ID_RE = re.compile(r"--\s*table_id:\s*([0-9a-fA-F\-]{36})\s*")


def extract_table_id(sql_text: str) -> str:
    """从 DDL 文本中提取 table_id UUID."""
    m = TABLE_ID_RE.search(sql_text)
    return m.group(1) if m else ""


def inject_table_id(sql_text: str, table_id: str) -> str:
    """在 DDL 文本中注入或替换 table_id 注释行。"""
    line = f"-- table_id: {table_id}"
    if TABLE_ID_RE.search(sql_text):
        return TABLE_ID_RE.sub(line, sql_text)
    # 插在第一行之后
    idx = sql_text.find("\n")
    if idx == -1:
        return line + "\n" + sql_text
    return sql_text[: idx + 1] + line + "\n" + sql_text[idx + 1 :]


def generate_table_id() -> str:
    return str(uuid.uuid4())


def parse_column_def(col_node: exp.ColumnDef) -> Optional[ColumnDef]:
    kind = col_node.args.get("kind")
    data_type = kind.sql(dialect="doris") if kind else "UNKNOWN"

    nullable = True
    default = None
    comment = None

    constraints = col_node.args.get("constraints") or []
    for c in constraints:
        kind = c.args.get("kind") if isinstance(c, exp.ColumnConstraint) else c
        if isinstance(kind, exp.NotNullColumnConstraint):
            nullable = bool(kind.args.get("allow_null"))
        elif isinstance(kind, exp.DefaultColumnConstraint):
            default = kind.this.sql(dialect="doris") if kind.this else None
        elif isinstance(kind, exp.CommentColumnConstraint):
            comment = (
                kind.this.sql(dialect="doris").strip("'\"")
                if kind.this
                else None
            )

    return ColumnDef(
        name=col_node.this.name,
        data_type=data_type,
        nullable=nullable,
        default=default,
        comment=comment,
    )


def parse_create_table(sql_text: str) -> Optional[TableDef]:
    try:
        statements = sqlglot.parse(
            normalize_create_table_for_sqlglot(sql_text),
            dialect="doris",
            error_level=ErrorLevel.IGNORE,
        )
    except Exception:
        return None

    for stmt in statements:
        if stmt is None:
            continue
        if not isinstance(stmt, exp.Create):
            continue
        schema = stmt.this
        if not isinstance(schema, exp.Schema):
            continue

        full_name = schema.this.sql(dialect="doris")
        short_name = (
            full_name.split(".")[-1] if "." in full_name else full_name
        )

        columns = []
        key_columns = []
        for col_node in schema.expressions:
            if isinstance(col_node, exp.ColumnDef):
                col_def = parse_column_def(col_node)
                if col_def:
                    columns.append(col_def)

        key_type, key_columns = extract_doris_key(sql_text)
        distribution_col = extract_doris_distribution_column(sql_text)

        # 用原始文本作为 raw_ddl,避免 sqlglot 再生 bug(如 UNIQUE KEY)
        raw_ddl = (
            sql_text
            if isinstance(sql_text, str)
            else stmt.sql(dialect="doris")
        )
        table_id = extract_table_id(raw_ddl)

        return TableDef(
            full_name=full_name,
            short_name=short_name,
            columns=columns,
            key_type=key_type,
            key_columns=key_columns or ([columns[0].name] if columns else []),
            distribution_col=distribution_col
            or (columns[0].name if columns else ""),
            raw_ddl=raw_ddl,
            table_id=table_id,
        )

    return None


def parse_ddl_file(filepath: Path) -> Optional[TableDef]:
    text = filepath.read_text(encoding="utf-8")
    return parse_create_table(text)


def load_tables_from_dir(ddl_dir: Path) -> dict:
    """加载目录下所有 DDL 文件,返回 {table_name: TableDef}."""
    tables = {}
    for f in sorted(ddl_dir.glob("*.sql")):
        t = parse_ddl_file(f)
        if t:
            tables[t.short_name] = t
    return tables


# ============================================================
# Git 集成: 从分支基线加载 DDL
# ============================================================


def _find_git_root(path: Path) -> Path:
    """向上查找包含 .git 的目录."""
    for p in [path] + list(path.parents):
        if (p / ".git").exists():
            return p.resolve()
    raise FileNotFoundError(f"未找到 .git 目录(从 {path} 向上查找)")


def _git_cmd(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        check=True,
        timeout=15,
    ).stdout.strip()


def _get_merge_base(repo: Path, branch: str = "main") -> str:
    return _git_cmd(repo, "merge-base", "--all", branch, "HEAD").split("\n")[0]


def _load_git_tables(repo: Path, ddl_dir_rel: str, ref: str) -> dict:
    """从 git ref 加载 DDL 文件并解析为 {short_name: TableDef}."""
    raw = _git_cmd(
        repo, "ls-tree", "-r", "--name-only", ref, "--", ddl_dir_rel
    )
    tables = {}
    for rel_path in raw.split("\n"):
        if not rel_path.endswith(".sql"):
            continue
        content = _git_cmd(repo, "show", f"{ref}:{rel_path}")
        t = parse_create_table(content)
        if t:
            tables[t.short_name] = t
    return tables


def derive_from_git(
    ddl_dir_rel: str = "shop/ddl",
    repo: Optional[Path] = None,
    base_branch: str = "main",
) -> List[DDLChange]:
    """
    对比 Git merge-base 与工作区的 DDL 差异,返回变更列表。

    参数:
        ddl_dir_rel: DDL 目录在 repo 中的相对路径 (如 "shop/ddl")
        repo:        Git 仓库根目录 (默认自动查找)
        base_branch: 基线分支 (默认 main)

    返回:
        List[DDLChange]
    """
    if repo is None:
        repo = _find_git_root(Path.cwd())
    base_ref = _get_merge_base(repo, base_branch)
    old_tables = _load_git_tables(repo, ddl_dir_rel, base_ref)
    new_tables = load_tables_from_dir(repo / ddl_dir_rel)
    return derive_ddl_changes(old_tables, new_tables)


# ============================================================
# 变更推导核心
# ============================================================


def _jaccard_similarity(
    cols_a: List[ColumnDef], cols_b: List[ColumnDef]
) -> float:
    sigs_a = {c.signature() for c in cols_a}
    sigs_b = {c.signature() for c in cols_b}
    if not sigs_a and not sigs_b:
        return 1.0
    intersection = sigs_a & sigs_b
    union = sigs_a | sigs_b
    return len(intersection) / len(union)


def derive_ddl_changes(old_tables: dict, new_tables: dict) -> List[DDLChange]:
    """
    核心方法: 对比 old/new 两套表定义,返回变更列表。

    重命名检测策略:
      1. UUID 精准匹配(优先): old.table_id == new.table_id → RENAME
      2. Jaccard 相似度(回退): 仅当 UUID 缺失或不同时使用

    参数:
        old_tables: {short_name: TableDef}
        new_tables: {short_name: TableDef}

    返回:
        List[DDLChange], 按 RENAME → ALTER → DROP → CREATE 排序
    """
    old_names = set(old_tables.keys())
    new_names = set(new_tables.keys())

    common_names = old_names & new_names
    dropped_names = set(old_names - new_names)
    created_names = set(new_names - old_names)

    changes: List[DDLChange] = []

    # ---- Phase 1: UUID-based rename detection (identity-based, no threshold) ----
    old_by_uuid = {}
    for name in dropped_names:
        tid = old_tables[name].table_id
        if tid:
            if tid in old_by_uuid:
                print(
                    f"警告: 旧表 {old_by_uuid[tid]} 与 {name} 的 table_id 重复({tid}),跳过"
                )
                continue
            old_by_uuid[tid] = name

    rename_pairs = []
    for name in list(created_names):
        tid = new_tables[name].table_id
        if tid and tid in old_by_uuid:
            rename_pairs.append((old_by_uuid[tid], name))
            created_names.discard(name)
            dropped_names.discard(old_by_uuid[tid])
            del old_by_uuid[tid]

    # ---- Phase 2: Jaccard similarity matching (fallback for tables without UUID) ----
    if dropped_names and created_names:
        similarity_scores = []
        for d in dropped_names:
            for c in created_names:
                score = _jaccard_similarity(
                    old_tables[d].columns, new_tables[c].columns
                )
                similarity_scores.append((score, d, c))
        similarity_scores.sort(reverse=True, key=lambda x: x[0])
        used_drops = set()
        used_creates = set()
        for score, d, c in similarity_scores:
            if score < 0.5:
                break
            if d in used_drops or c in used_creates:
                continue
            rename_pairs.append((d, c))
            used_drops.add(d)
            used_creates.add(c)

    # ---- Process all RENAMEs (UUID + Jaccard) ----
    for d, c in rename_pairs:
        old_t = old_tables[d]
        new_t = new_tables[c]
        changes.append(RenameTable(old_t, new_t))
        alters = _derive_alter_columns(old_t, new_t)
        if any(alters.values()):
            alter = alter_to_change(c, old_t, new_t, alters)
            alter.table_name = new_t.full_name
            changes.append(alter)
        dropped_names.discard(d)
        created_names.discard(c)

    # ---- Remaining DROPs ----
    for name in sorted(dropped_names):
        changes.append(DropTable(old_tables[name].full_name))

    # ---- Remaining CREATEs ----
    for name in sorted(created_names):
        t = new_tables[name]
        if not t.table_id:
            t.table_id = generate_table_id()
            t.raw_ddl = inject_table_id(t.raw_ddl, t.table_id)
        changes.append(CreateTable(t))

    # ---- ALTER TABLE: same-name tables ----
    for name in sorted(common_names):
        old_t = old_tables[name]
        new_t = new_tables[name]
        alters = _derive_alter_columns(old_t, new_t)
        if any(alters.values()):
            changes.append(alter_to_change(name, old_t, new_t, alters))

    return changes


def _derive_alter_columns(old: TableDef, new: TableDef) -> dict:
    """逐列对比 old/new 同名 table,返回 {adds, drops, modifies, renames}.

    列重命名检测: 配对 data_type + nullable 均相同的 drop/add 列为 rename。
    """
    old_cols = {c.name: c for c in old.columns}
    new_cols = {c.name: c for c in new.columns}

    old_names = set(old_cols.keys())
    new_names = set(new_cols.keys())

    dropped = [old_cols[n] for n in sorted(old_names - new_names)]
    added = [new_cols[n] for n in sorted(new_names - old_names)]

    # 检测列重命名: 按 data_type + nullable 配对
    renames = []
    matched_drops = set()
    matched_adds = set()
    for di, drop_col in enumerate(dropped):
        for ai, add_col in enumerate(added):
            if ai in matched_adds:
                continue
            if (
                drop_col.data_type == add_col.data_type
                and drop_col.nullable == add_col.nullable
            ):
                renames.append((drop_col.name, add_col.name))
                matched_drops.add(di)
                matched_adds.add(ai)
                break

    if renames:
        dropped = [c for i, c in enumerate(dropped) if i not in matched_drops]
        added = [c for i, c in enumerate(added) if i not in matched_adds]

    modified = []
    for name in sorted(old_names & new_names):
        old_c = old_cols[name]
        new_c = new_cols[name]
        if (
            old_c.data_type != new_c.data_type
            or old_c.nullable != new_c.nullable
            or old_c.default != new_c.default
            or (old_c.comment or "") != (new_c.comment or "")
        ):
            modified.append((old_c, new_c))

    return {
        "adds": added,
        "drops": dropped,
        "modifies": modified,
        "renames": renames,
    }


def alter_to_change(
    name: str, old: TableDef, new: TableDef, alters: dict
) -> AlterTable:
    return AlterTable(
        table_name=old.full_name,
        old_def=old,
        new_def=new,
        adds=alters["adds"],
        drops=alters["drops"],
        modifies=alters["modifies"],
        renames=alters.get("renames", []),
    )


# ============================================================
# 输出工具
# ============================================================


def format_changes(changes: List[DDLChange]) -> str:
    """将变更列表格式化为可执行的 SQL 语句(含注释)."""
    lines = []
    for ch in changes:
        if isinstance(ch, CreateTable):
            lines.append(f"-- 新增表: {ch.table_def.full_name}")
        elif isinstance(ch, DropTable):
            lines.append(f"-- 删除表: {ch.table_name}")
        elif isinstance(ch, RenameTable):
            lines.append(f"-- 重命名: {ch.old_name} → {ch.new_name}")
        elif isinstance(ch, AlterTable):
            lines.append(f"-- 修改表: {ch.table_name}")
            if ch.renames:
                lines.append(
                    f"--   重命名列: {', '.join(f'{o}→{n}' for o, n in ch.renames)}"
                )
            if ch.drops:
                lines.append(
                    f"--   删列: {', '.join(c.name for c in ch.drops)}"
                )
            if ch.adds:
                lines.append(
                    f"--   增列: {', '.join(c.name for c in ch.adds)}"
                )
            if ch.modifies:
                lines.append(
                    f"--   改列: {', '.join(o.name for o, _ in ch.modifies)}"
                )
        lines.append(ch.to_sql())
        lines.append("")
    return "\n".join(lines)


def changes_to_json(changes: List[DDLChange]) -> dict:
    """将变更列表序列化为 JSON."""
    result = []
    for ch in changes:
        entry = {"change_type": ch.change_type, "sql": ch.to_sql()}
        if isinstance(ch, CreateTable):
            entry["table_name"] = ch.table_def.full_name
            entry["short_name"] = ch.table_def.short_name
        elif isinstance(ch, DropTable):
            entry["table_name"] = ch.table_name
        elif isinstance(ch, RenameTable):
            entry["old_name"] = ch.old_name
            entry["new_name"] = ch.new_name
        elif isinstance(ch, AlterTable):
            entry["table_name"] = ch.table_name
            entry["adds"] = [asdict(c) for c in ch.adds]
            entry["drops"] = [asdict(c) for c in ch.drops]
            entry["renames"] = [{"old": o, "new": n} for o, n in ch.renames]
            entry["modifies"] = [
                {"old": asdict(o), "new": asdict(n)} for o, n in ch.modifies
            ]
        result.append(entry)
    return {"changes": result}


# ============================================================
# CLI 入口
# ============================================================


def _emit_output(
    changes: List[DDLChange], fmt: str, output_path: Optional[Path]
):
    """统一输出逻辑."""
    stats = {
        c.change_type: sum(
            1 for cc in changes if cc.change_type == c.change_type
        )
        for c in changes
    }
    if fmt == "json":
        output = json.dumps(
            changes_to_json(changes), ensure_ascii=False, indent=2
        )
    else:
        header = f"-- DDL 自动推导结果: {dict(stats)}\n--\n\n"
        output = header + format_changes(changes)

    if output_path:
        output_path.write_text(output, encoding="utf-8")
        print(f"输出已写入: {output_path}")
        print(f"共 {len(changes)} 条变更: {dict(stats)}")
    else:
        print(output)


def inject_uuid_to_dir(ddl_dir: Path, dry_run: bool = False) -> int:
    """
    扫描 DDL 目录,为缺少 table_id 的 .sql 文件注入随机 UUID。
    返回修改的文件数。
    """
    count = 0
    for f in sorted(ddl_dir.glob("*.sql")):
        text = f.read_text(encoding="utf-8")
        if extract_table_id(text):
            continue
        tid = generate_table_id()
        new_text = inject_table_id(text, tid)
        if dry_run:
            print(f"[DRY RUN] {f.name} → table_id: {tid}")
        else:
            f.write_text(new_text, encoding="utf-8")
            print(f"{f.name} → table_id: {tid}")
        count += 1
    return count


def main():
    import argparse

    parser = argparse.ArgumentParser(description="DDL 变更自动推导工具")
    sub = parser.add_subparsers(dest="mode", help="运行模式")

    # ---- dir 模式 (双目录对比) ----
    dir_p = sub.add_parser("dir", help="对比两个 DDL 目录")
    dir_p.add_argument("old_dir", type=str, help="旧 DDL 目录")
    dir_p.add_argument("new_dir", type=str, help="新 DDL 目录")

    # ---- git 模式 (对比分支与工作区) ----
    git_p = sub.add_parser("git", help="对比 Git 分支与工作区的 DDL")
    git_p.add_argument(
        "ddl_dir",
        type=str,
        nargs="?",
        default="shop/ddl",
        help="DDL 目录相对路径 (默认 shop/ddl)",
    )
    git_p.add_argument(
        "--base", type=str, default="main", help="基线分支 (默认 main)"
    )

    # ---- inject-uuid 模式 (批量注入 UUID) ----
    inject_p = sub.add_parser(
        "inject-uuid", help="为 DDL 目录中缺少 table_id 的文件注入 UUID"
    )
    inject_p.add_argument("ddl_dir", type=str, help="DDL 目录路径")
    inject_p.add_argument(
        "--dry-run",
        action="store_true",
        help="仅预览,不实际写入文件",
    )

    # 通用参数
    for p in (dir_p, git_p):
        p.add_argument(
            "--format",
            choices=["sql", "json"],
            default="sql",
            help="输出格式 (默认 sql)",
        )
        p.add_argument(
            "--output",
            "-o",
            type=str,
            default=None,
            help="输出文件路径 (默认 stdout)",
        )

    # 向后兼容: 无子命令且首参数是目录时,自动插入"dir"
    if len(sys.argv) >= 2 and not sys.argv[1].startswith("-"):
        first = sys.argv[1]
        if first not in ("dir", "git", "inject-uuid") and Path(first).is_dir():
            sys.argv.insert(1, "dir")

    args = parser.parse_args()

    if args.mode == "inject-uuid":
        ddl_dir = Path(args.ddl_dir)
        if not ddl_dir.is_dir():
            print(f"错误: 目录不存在: {ddl_dir}")
            return 1
        count = inject_uuid_to_dir(ddl_dir, dry_run=args.dry_run)
        action = "预览" if args.dry_run else "注入"
        print(f"完成: {action} {count} 个文件")
        return 0

    if args.mode == "git":
        try:
            changes = derive_from_git(
                ddl_dir_rel=args.ddl_dir,
                base_branch=args.base,
            )
        except FileNotFoundError as e:
            print(f"错误: {e}")
            return 1
        except subprocess.CalledProcessError as e:
            print(f"Git 错误: {e.stderr.strip()}")
            return 1
    else:
        old_dir = Path(args.old_dir)
        new_dir = Path(args.new_dir)
        if not old_dir.is_dir():
            print(f"错误: 旧目录不存在: {old_dir}")
            return 1
        if not new_dir.is_dir():
            print(f"错误: 新目录不存在: {new_dir}")
            return 1
        old_tables = load_tables_from_dir(old_dir)
        new_tables = load_tables_from_dir(new_dir)
        changes = derive_ddl_changes(old_tables, new_tables)

    output_path = Path(args.output) if args.output else None
    _emit_output(changes, args.format, output_path)
    return 0


if __name__ == "__main__":
    exit(main())
