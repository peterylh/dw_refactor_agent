#!/usr/bin/env python3
"""
Olist 巴西电商数据集下载工具
来源: https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce
下载方式:
  1. 自动: pip install kagglehub && python download_data.py
  2. 手动: 从 Kaggle 下载后解压到 data/ 目录
"""

import os, zipfile, sys
from pathlib import Path

OLIST_DIR = Path(__file__).parent
DATA_DIR = OLIST_DIR / "data"

REQUIRED_FILES = [
    "olist_customers_dataset.csv",
    "olist_geolocation_dataset.csv",
    "olist_order_items_dataset.csv",
    "olist_order_payments_dataset.csv",
    "olist_order_reviews_dataset.csv",
    "olist_orders_dataset.csv",
    "olist_products_dataset.csv",
    "olist_sellers_dataset.csv",
    "product_category_name_translation.csv",
]


def check_existing():
    if not DATA_DIR.exists():
        return []
    return [f for f in REQUIRED_FILES if (DATA_DIR / f).exists()]


def try_kagglehub():
    try:
        import kagglehub
    except ImportError:
        print("kagglehub 未安装, 尝试 pip install kagglehub...")
        os.system(f"{sys.executable} -m pip install kagglehub -q")
        try:
            import kagglehub
        except ImportError:
            return False

    print("正在通过 kagglehub 下载 Olist 数据集...")
    path = kagglehub.dataset_download("olistbr/brazilian-ecommerce")
    print(f"下载完成: {path}")

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    for f in Path(path).iterdir():
        if f.suffix == ".csv":
            target = DATA_DIR / f.name
            f.rename(target)
            print(f"  移动: {f.name} -> {target}")
    return True


def manual_instructions():
    print()
    print("=" * 60)
    print("手动下载说明:")
    print("1. 访问 https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce")
    print("2. 点击 Download 下载 ZIP 文件")
    print(f"3. 解压所有 CSV 到 {DATA_DIR}/ 目录")
    print("需要以下文件:")
    for f in REQUIRED_FILES:
        print(f"  - {f}")
    print("=" * 60)


def main():
    existing = check_existing()
    if len(existing) == len(REQUIRED_FILES):
        print(f"所有数据文件已存在: {DATA_DIR}/")
        return

    if existing:
        print(f"已存在 {len(existing)}/{len(REQUIRED_FILES)} 个文件")
        missing = [f for f in REQUIRED_FILES if f not in existing]
        print(f"缺少: {', '.join(missing)}")

    if try_kagglehub():
        print("自动下载完成!")
        finalized = check_existing()
        print(f"已获取 {len(finalized)}/{len(REQUIRED_FILES)} 个文件")
    else:
        manual_instructions()


if __name__ == "__main__":
    main()
