#!/usr/bin/env python3
"""DDL \u81ea\u52a8\u63a8\u5bfc\u529f\u80fd\u9a8c\u8bc1: Doris A \u73af\u5883\u7aef\u5230\u7aef\u6d4b\u8bd5"""

import json, shutil, subprocess, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from ddl_deriver.ddl_deriver import (
    load_tables_from_dir,
    derive_ddl_changes,
    changes_to_json,
)

DORIS = ["mysql", "-h172.16.0.90", "-P9030", "-uroot"]
DB_A, DB_PROD = "shop_dm_a", "shop_dm"


def run_doris(sql, db=None):
    if db is None:
        db = DB_A
    r = subprocess.run(
        DORIS + [db, "-e", sql], capture_output=True, text=True, timeout=30
    )
    if r.returncode != 0:
        print(f"DORIS ERROR (db={db}): {r.stderr.strip()}")
        r.check_returncode()
    return r.stdout


def run_doris_file(sql_path, db=None):
    if db is None:
        db = DB_A
    with open(sql_path) as f:
        r = subprocess.run(
            DORIS + [db], stdin=f, capture_output=True, text=True, timeout=120
        )
    if r.returncode != 0:
        print(f"DORIS FILE ERROR (db={db}): {r.stderr.strip()}")
        r.check_returncode()
    return r.stdout


# Step 0: new_dir was prepared by previous script
old_dir = Path("shop/ddl")
new_dir = Path("/tmp/ddl_new_verify")
assert new_dir.exists(), "Run the prep script first"

# Step 1: Derive changes
print("=" * 60)
print("[Step 1] Loading DDL and deriving changes...")
old_tables = load_tables_from_dir(old_dir)
new_tables = load_tables_from_dir(new_dir)
changes = derive_ddl_changes(old_tables, new_tables)
print(f"Derived {len(changes)} changes:")
for c in changes:
    name = getattr(c, "table_name", getattr(c, "old_name", ""))
    print(f"  [{c.change_type}] {name} -> {c.to_sql()[:70]}...")

# Step 2: Reset shop_dm_a and init with all DDL tables
print(f"\n[Step 2] Resetting {DB_A} and initializing...")
run_doris(f"DROP DATABASE IF EXISTS {DB_A};", db="information_schema")
run_doris(f"CREATE DATABASE {DB_A};", db="information_schema")

# Build init SQL (DDL only, no INSERT)
init_parts = []
for f in sorted(old_dir.glob("*.sql")):
    text = f.read_text(encoding="utf-8")
    lines = []
    for line in text.split("\n"):
        if line.strip().upper().startswith("INSERT"):
            break
        lines.append(line)
    init_parts.append("\n".join(lines))
init_sql = "\n\n".join(init_parts).replace(f"{DB_PROD}.", f"{DB_A}.")
init_path = Path("/tmp/shop_dm_a_init_full.sql")
init_path.write_text(init_sql, encoding="utf-8")
run_doris_file(init_path)
print("  Tables created:", len(list(old_dir.glob("*.sql"))))

# Step 3: Apply derived DDL changes to A env
print(f"\n[Step 3] Applying derived DDL to {DB_A}...")
apply_parts = []
for c in changes:
    sql = c.to_sql().replace(f"{DB_PROD}.", f"{DB_A}.")
    apply_parts.append(sql)
apply_sql = "\n\n".join(apply_parts)
print(f"  SQL to execute:\n{apply_sql}\n")
apply_path = Path("/tmp/ddl_derive_apply.sql")
apply_path.write_text(apply_sql, encoding="utf-8")
run_doris_file(apply_path)
print("  Done!")

# Step 4: Verify
print(f"\n[Step 4] Verifying {DB_A}...")
tables_raw = run_doris("SHOW TABLES;")
tables = {
    t.strip() for t in tables_raw.split("\n") if t.strip() and "Tables_in" not in t
}
print(f"  Tables ({len(tables)}): {sorted(tables)}")

checks = []
# 4a. Rename: ods_customer -> ods_customer_v2
checks.append(("ods_customer not exists", "ods_customer" not in tables))
checks.append(("ods_customer_v2 exists", "ods_customer_v2" in tables))

# 4b. Drop: ods_product deleted
checks.append(("ods_product not exists", "ods_product" not in tables))

# 4c. Create: ods_feedback added
checks.append(("ods_feedback exists", "ods_feedback" in tables))

# 4d. ods_order still exists (modified)
checks.append(("ods_order exists", "ods_order" in tables))

# 4e. ods_customer_v2 has email column
desc_v2 = run_doris("DESC ods_customer_v2;")
checks.append(("ods_customer_v2 has email", "email" in desc_v2))

# 4f. ods_order total_amount type check
desc_order = run_doris("DESC ods_order;")
total_amount_line = ""
for line in desc_order.split("\n"):
    if "total_amount" in line:
        total_amount_line = line.strip()
        break
checks.append(
    ("total_amount DECIMAL(12,2)->DECIMAL(14,2)", "14" in total_amount_line[:50])
)

# 4g. ods_feedback structure
desc_fb = run_doris("DESC ods_feedback;")
checks.append(("ods_feedback has feedback_id", "feedback_id" in desc_fb))
checks.append(("ods_feedback has content", "content" in desc_fb))

print("\n  Verification results:")
all_pass = True
for name, ok in checks:
    status = "\u2714" if ok else "\u2716"
    if not ok:
        all_pass = False
    print(f"    {status} {name}")

# Summary
print(f"\n{'=' * 60}")
if all_pass:
    print("  \u2705 ALL VERIFICATIONS PASSED!")
    print(f"  \u251c\u2500 ods_product \u2716 DROP TABLE")
    print(
        f"  \u251c\u2500 ods_customer -> ods_customer_v2 \u2714 RENAME TABLE + ADD COLUMN email"
    )
    print(
        f"  \u251c\u2500 ods_order.total_amount DECIMAL(12,2)->DECIMAL(14,2) \u2714 ALTER TABLE"
    )
    print(f"  \u2514\u2500 ods_feedback (new) \u2714 CREATE TABLE")
else:
    print("  \u2716 SOME VERIFICATIONS FAILED!")

# Save result
result = changes_to_json(changes)
result["verification"] = {
    "env": DB_A,
    "status": "PASSED" if all_pass else "FAILED",
    "checks": [{"name": n, "passed": ok} for n, ok in checks],
    "tables_after": sorted(tables),
}
Path("/tmp/ddl_derive_verify_result.json").write_text(
    json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
)
print(f"\nResult saved to /tmp/ddl_derive_verify_result.json")
sys.exit(0 if all_pass else 1)
