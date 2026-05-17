#!/usr/bin/env python3
"""
将 lineage_data_{project}.json 导入对应该项目的 lineage 库
shop  → shop_lineage
olist → olist_lineage

DDL 执行 (首次) 需要先跑 lineage/ddl/*.sql
"""

import json, argparse
from pathlib import Path
import pymysql

PROJECT_DIR = Path(__file__).parent.parent
PROJECT_MAP = {
    "shop": {"dir": "shop", "db": "shop_dm", "lineage_db": "shop_lineage"},
    "olist": {"dir": "olist", "db": "olist_dm", "lineage_db": "olist_lineage"},
}

parser = argparse.ArgumentParser(
    description="将 lineage_data_{project}.json 导入对应该项目的 lineage 库"
)
parser.add_argument("--project", default="shop", choices=list(PROJECT_MAP.keys()),
                    help="项目名称")
args = parser.parse_args()

cfg = PROJECT_MAP[args.project]
TASKS_DIR = PROJECT_DIR / cfg["dir"] / "tasks"
JSON_PATH = Path(__file__).parent / f"lineage_data_{args.project}.json"

conn = pymysql.connect(
    host="172.16.0.90",
    port=9030,
    user="root",
    database=cfg["lineage_db"],
    charset="utf8mb4",
)
cursor = conn.cursor()

# ==================== 0. 确保 indirect_lineage 表存在 ====================
cursor.execute("""
CREATE TABLE IF NOT EXISTS indirect_lineage (
    id BIGINT NOT NULL,
    source_table_id BIGINT NOT NULL,
    source_column_id BIGINT NOT NULL,
    target_table_id BIGINT NOT NULL,
    job_id BIGINT NOT NULL,
    condition_type VARCHAR(20) NOT NULL,
    condition_expression TEXT
) ENGINE=OLAP DUPLICATE KEY(id) DISTRIBUTED BY HASH(id) BUCKETS 10 PROPERTIES ("replication_num" = "1")
""")
conn.commit()

# ==================== 0. 清空所有表(每个 lineage 库独立, 放心 truncate) ====================
print("0. 清空历史数据...")
for tbl in ["indirect_lineage", "column_lineage", "table_lineage", "job", "column_info", "table_info", "datasource"]:
    cursor.execute(f"TRUNCATE TABLE {tbl}")
conn.commit()
print("   已清空 7 张表")

# ==================== 1. 插入数据源 ====================
print("1. 插入数据源...")
cursor.execute(
    "INSERT INTO datasource (id, name, db_type, host) VALUES (1, %s, %s, %s)",
    (cfg["db"], "starrocks", "172.16.0.90:9030"),
)
conn.commit()

with open(JSON_PATH, encoding="utf-8") as f:
    data = json.load(f)

tables_list = data["tables"]
edges = data["edges"]
indirect_edges = data.get("indirect_edges", [])

# ==================== 2. 插入表元数据 ====================
print(f"2. 插入 {len(tables_list)} 张表...")
table_id_map = {}
for idx, t in enumerate(tables_list, start=1):
    cursor.execute(
        "INSERT INTO table_info (id, datasource_id, table_name, full_name, layer) VALUES (%s, 1, %s, %s, %s)",
        (idx, t["name"], t["full_name"], t["layer"]),
    )
    table_id_map[t["name"]] = idx
conn.commit()

# ==================== 3. 插入列元数据 ====================
print("3. 插入列元数据...")
col_id = 1
col_id_map = {}
for t in tables_list:
    tid = table_id_map[t["name"]]
    for ord_, c in enumerate(t["columns"]):
        cursor.execute(
            "INSERT INTO column_info (id, table_id, column_name, data_type, comment, ordinal) VALUES (%s, %s, %s, %s, %s, %s)",
            (col_id, tid, c["name"], c["type"], c.get("comment", ""), ord_),
        )
        col_id_map[f"{t['name']}.{c['name']}"] = col_id
        col_id += 1
conn.commit()
print(f"   共 {col_id - 1} 列")

# ==================== 4. 插入作业(库隔离,不用前缀) ====================
print("4. 插入作业...")
unique_files = sorted(
    set(e["source_file"] for e in edges)
    | set(e.get("source_file", "") for e in indirect_edges)
)
job_id_map = {}
for idx, fname in enumerate(unique_files, start=1):
    raw_sql = None
    sql_file = TASKS_DIR / fname
    if sql_file.exists():
        raw_sql = sql_file.read_text(encoding="utf-8")
    job_name = fname.replace(".sql", "")
    cursor.execute(
        "INSERT INTO job (id, job_name, job_type, raw_sql) VALUES (%s, %s, %s, %s)",
        (idx, job_name, "SQL", raw_sql),
    )
    job_id_map[fname] = idx
conn.commit()
print(f"   共 {len(unique_files)} 个作业")

# ==================== 5. 插入字段血缘 ====================
print(f"5. 插入 {len(edges)} 条字段血缘...")
table_lineage_set = set()
for idx, e in enumerate(edges, start=1):
    src_table, src_col = e["source"].split(".", 1)
    tgt_table, tgt_col = e["target"].split(".", 1)
    src_table_id = table_id_map.get(src_table)
    tgt_table_id = table_id_map.get(tgt_table)
    src_col_id = col_id_map.get(e["source"])
    tgt_col_id = col_id_map.get(e["target"])
    job_id = job_id_map.get(e["source_file"])

    if not all([src_table_id, tgt_table_id, src_col_id, tgt_col_id]):
        print(f"   跳过: {e['source']} -> {e['target']}")
        continue

    cursor.execute(
        "INSERT INTO column_lineage (id, source_table_id, source_column_id, target_table_id, target_column_id, job_id, expression) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s)",
        (idx, src_table_id, src_col_id, tgt_table_id, tgt_col_id, job_id, e["expression"]),
    )
    table_lineage_set.add((src_table_id, tgt_table_id, job_id))
conn.commit()

# ==================== 6. 插入间接血缘 ====================
print(f"6. 插入 {len(indirect_edges)} 条间接血缘...")
for idx, ie in enumerate(indirect_edges, start=1):
    src = ie["source"]
    src_table, src_col = src.split(".", 1)
    tgt_table = ie["target_table"]
    src_table_id = table_id_map.get(src_table)
    src_col_id = col_id_map.get(src)
    tgt_table_id = table_id_map.get(tgt_table)
    job_id = job_id_map.get(ie.get("source_file", ""))

    if not all([src_table_id, src_col_id, tgt_table_id, job_id]):
        print(f"   跳过: {src} -> {tgt_table}")
        continue

    cursor.execute(
        "INSERT INTO indirect_lineage (id, source_table_id, source_column_id, target_table_id, job_id, condition_type, condition_expression) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s)",
        (idx, src_table_id, src_col_id, tgt_table_id, job_id,
         ie["condition_type"], ie.get("condition_expression", "")),
    )
conn.commit()

# ==================== 7. 插入表级血缘 ====================
print(f"7. 插入 {len(table_lineage_set)} 条表级血缘...")
for idx, (src_tid, tgt_tid, jid) in enumerate(table_lineage_set, start=1):
    cursor.execute(
        "INSERT INTO table_lineage (id, source_table_id, target_table_id, job_id) VALUES (%s, %s, %s, %s)",
        (idx, src_tid, tgt_tid, jid),
    )
conn.commit()

# ==================== 验证 ====================
print("\n=== 验证 ===")
for tbl in ["datasource", "table_info", "column_info", "job", "column_lineage", "indirect_lineage", "table_lineage"]:
    cursor.execute(f"SELECT COUNT(*) FROM {tbl}")
    cnt = cursor.fetchone()[0]
    print(f"  {tbl}: {cnt} 行")

cursor.close()
conn.close()
print(f"\n{cfg['lineage_db']} 导入完成!")
