#!/usr/bin/env python3
"""将 lineage_data.json 导入 Doris lineage 库"""

import json
import os
from pathlib import Path
import pymysql

PROJECT_DIR = Path(__file__).parent.parent
JSON_PATH = Path(__file__).parent / "lineage_data.json"
TASKS_DIR = PROJECT_DIR / "shop" / "tasks"

conn = pymysql.connect(
    host="172.16.0.90",
    port=9030,
    user="root",
    database="lineage",
    charset="utf8mb4",
)
cursor = conn.cursor()

# ==================== 0. 创建 indirect_lineage 表（如不存在） ====================
cursor.execute(
    """
CREATE TABLE IF NOT EXISTS indirect_lineage (
    id BIGINT NOT NULL COMMENT '记录ID',
    source_table_id BIGINT NOT NULL COMMENT '来源表ID(被引用的字段所属表)',
    source_column_id BIGINT NOT NULL COMMENT '来源字段ID',
    target_table_id BIGINT NOT NULL COMMENT '受影响的目标表ID',
    job_id BIGINT NOT NULL COMMENT '加工作业ID',
    condition_type VARCHAR(20) NOT NULL COMMENT '条件类型: WHERE/JOIN_ON/GROUP_BY/HAVING',
    condition_expression TEXT COMMENT '原始条件片段'
) ENGINE=OLAP
DUPLICATE KEY(id)
DISTRIBUTED BY HASH(id) BUCKETS 10
PROPERTIES ("replication_num" = "1")
"""
)
conn.commit()

# ==================== 0. 清空所有表（保证幂等性） ====================
print("0. 清空历史数据...")
for tbl in [
    "indirect_lineage",
    "column_lineage",
    "table_lineage",
    "job",
    "column_info",
    "table_info",
    "datasource",
]:
    cursor.execute(f"TRUNCATE TABLE {tbl}")
conn.commit()
print("   已清空 7 张表")

with open(JSON_PATH, encoding="utf-8") as f:
    data = json.load(f)

tables_list = data[
    "tables"
]  # list of {name, full_name, layer, columns: [{name, type, comment}]}
edges = data["edges"]  # list of {source, target, expression, source_file}
indirect_edges = data.get("indirect_edges", [])  # list of indirect lineage edges

# ==================== 1. 插入数据源 ====================
print("1. 插入数据源...")
cursor.execute(
    "INSERT INTO datasource (id, name, db_type, host) VALUES (1, %s, %s, %s)",
    ("shop_dm", "starrocks", "172.16.0.90:9030"),
)
conn.commit()

# ==================== 2. 插入表元数据 ====================
print(f"2. 插入 {len(tables_list)} 张表...")
table_id_map = {}  # table_name -> table_id
for idx, t in enumerate(tables_list, start=1):
    cursor.execute(
        "INSERT INTO table_info (id, datasource_id, table_name, full_name, layer) VALUES (%s, %s, %s, %s, %s)",
        (idx, 1, t["name"], t["full_name"], t["layer"]),
    )
    table_id_map[t["name"]] = idx
conn.commit()

# ==================== 3. 插入列元数据 ====================
print("3. 插入列元数据...")
col_id = 1
col_id_map = {}  # "table.column" -> column_info.id
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

# ==================== 4. 插入作业 ====================
print("4. 插入作业...")
unique_files = sorted(
    set(e["source_file"] for e in edges)
    | set(e.get("source_file", "") for e in indirect_edges)
)
job_id_map = {}
for idx, fname in enumerate(unique_files, start=1):
    # 尝试读取原始 SQL
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
table_lineage_set = set()  # (src_table_id, tgt_table_id, job_id)

for idx, e in enumerate(edges, start=1):
    # source/target 格式: "table.column"
    src_table, src_col = e["source"].split(".", 1)
    tgt_table, tgt_col = e["target"].split(".", 1)

    src_table_id = table_id_map.get(src_table)
    tgt_table_id = table_id_map.get(tgt_table)
    src_col_id = col_id_map.get(e["source"])
    tgt_col_id = col_id_map.get(e["target"])
    job_id = job_id_map.get(e["source_file"])

    if not all([src_table_id, tgt_table_id, src_col_id, tgt_col_id]):
        print(f"   跳过 (找不到映射): {e['source']} -> {e['target']}")
        continue

    cursor.execute(
        "INSERT INTO column_lineage (id, source_table_id, source_column_id, target_table_id, target_column_id, job_id, expression) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s)",
        (
            idx,
            src_table_id,
            src_col_id,
            tgt_table_id,
            tgt_col_id,
            job_id,
            e["expression"],
        ),
    )

    # 收集表级血缘
    table_lineage_set.add((src_table_id, tgt_table_id, job_id))

conn.commit()

# ==================== 6. 插入间接血缘 ====================
print(f"6. 插入 {len(indirect_edges)} 条间接血缘...")
indirect_id_start = len(edges) + 1
for idx, ie in enumerate(indirect_edges, start=indirect_id_start):
    src = ie["source"]  # "table.column"
    src_table, src_col = src.split(".", 1)
    tgt_table = ie["target_table"]
    src_table_id = table_id_map.get(src_table)
    src_col_id = col_id_map.get(src)
    tgt_table_id = table_id_map.get(tgt_table)
    job_id = job_id_map.get(ie.get("source_file", ""))

    if not all([src_table_id, src_col_id, tgt_table_id, job_id]):
        print(f"   跳过 (找不到映射): {src} -> {tgt_table}")
        continue

    cursor.execute(
        "INSERT INTO indirect_lineage (id, source_table_id, source_column_id, target_table_id, job_id, condition_type, condition_expression) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s)",
        (
            idx,
            src_table_id,
            src_col_id,
            tgt_table_id,
            job_id,
            ie["condition_type"],
            ie.get("condition_expression", ""),
        ),
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
print("\n=== 导入完成，验证 ===")
for tbl in [
    "datasource",
    "table_info",
    "column_info",
    "job",
    "column_lineage",
    "indirect_lineage",
    "table_lineage",
]:
    cursor.execute(f"SELECT COUNT(*) FROM {tbl}")
    cnt = cursor.fetchone()[0]
    print(f"  {tbl}: {cnt} 行")

cursor.close()
conn.close()
print("\n完成!")
