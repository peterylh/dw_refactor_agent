from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SHOP_DDL_DIR = ROOT / "shop" / "ddl"


def _shop_ddls():
    return sorted(SHOP_DDL_DIR.glob("*.sql"))


def test_shop_ddls_do_not_use_dynamic_partitions():
    offenders = []
    for path in _shop_ddls():
        text = path.read_text(encoding="utf-8")
        if "dynamic_partition." in text:
            offenders.append(path.name)

    assert offenders == []


def test_shop_static_partitions_cover_ods_data_range():
    missing = {}
    for path in _shop_ddls():
        text = path.read_text(encoding="utf-8")
        if "PARTITION BY RANGE" not in text:
            continue

        if "stat_month_date" in text:
            expected = (
                'PARTITION p202406 VALUES LESS THAN ("2024-07-01")',
                'PARTITION p202501 VALUES LESS THAN ("2025-02-01")',
            )
        else:
            expected = (
                'PARTITION p20240601 VALUES LESS THAN ("2024-06-02")',
                'PARTITION p20250103 VALUES LESS THAN ("2025-01-04")',
            )
        absent = [partition for partition in expected if partition not in text]
        if absent:
            missing[path.name] = absent

    assert missing == {}
