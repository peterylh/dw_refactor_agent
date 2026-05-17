#!/usr/bin/env python3
"""
Olist 数据导入脚本
将 CSV 数据通过 Stream Load 导入 Doris ODS 表
前置条件: Olist DDL 已在 Doris 中执行完毕
"""

import csv, os, sys, time
from pathlib import Path

OLIST_DIR = Path(__file__).parent
DATA_DIR = OLIST_DIR / "data"

# Doris Stream Load 配置
DORIS_HOST = "172.16.0.90"
DORIS_PORT = 8030
DORIS_DB = "olist_dm"
DORIS_USER = "root"

# CSV -> ODS 表映射
CSV_TABLE_MAP = {
    "olist_customers_dataset.csv": "ods_customer",
    "olist_geolocation_dataset.csv": "ods_geolocation",
    "olist_order_items_dataset.csv": "ods_order_item",
    "olist_order_payments_dataset.csv": "ods_payment",
    "olist_order_reviews_dataset.csv": "ods_review",
    "olist_orders_dataset.csv": "ods_order",
    "olist_products_dataset.csv": "ods_product",
    "olist_sellers_dataset.csv": "ods_seller",
    "product_category_name_translation.csv": "ods_category_translation",
}


def stream_load(csv_path, table_name):
    """使用 Doris Stream Load 导入 CSV 数据"""
    url = f"http://{DORIS_HOST}:{DORIS_PORT}/api/{DORIS_DB}/{table_name}/_stream_load"
    header = f"label:import_{table_name}_{int(time.time())}"
    cmd = (
        f"curl -s --location-trusted -u {DORIS_USER}: "
        f"-H 'column_separator:,' "
        f"-H 'format:csv' "
        f"-H 'trim_double_quotes:true' "
        f"-H '{header}' "
        f"-T {csv_path} "
        f'"{url}"'
    )
    result = os.popen(cmd).read()
    return result


def main():
    if not DATA_DIR.exists():
        print(f"数据目录不存在: {DATA_DIR}")
        print("请先运行 python download_data.py 下载数据")
        return

    total = len(CSV_TABLE_MAP)
    ok = 0
    fail = 0

    for csv_name, table_name in sorted(CSV_TABLE_MAP.items()):
        csv_path = DATA_DIR / csv_name
        if not csv_path.exists():
            print(f"[跳过] 文件不存在: {csv_name}")
            continue

        print(f"[导入] {csv_name} -> {table_name} ... ", end="", flush=True)
        result = stream_load(csv_path, table_name)

        if '"Status":"Success"' in result or '"Status":"TxnMessage"' in result:
            print("OK")
            ok += 1
        else:
            print("失败")
            print(f"  {result[:200]}")
            fail += 1

    print(f"\n导入完成: {ok} 成功, {fail} 失败 (共 {total})")


if __name__ == "__main__":
    main()
