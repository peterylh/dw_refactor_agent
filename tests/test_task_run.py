import importlib.util
import subprocess
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parent.parent / "exec" / "task_run.py"
SPEC = importlib.util.spec_from_file_location("task_run_module", MODULE_PATH)
task_run = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(task_run)


def _completed(stdout: str = "", stderr: str = "", returncode: int = 0):
    return subprocess.CompletedProcess(
        args=["mysql"],
        returncode=returncode,
        stdout=stdout,
        stderr=stderr,
    )


def test_is_partitioned_table_uses_show_create_cache(monkeypatch):
    calls = []

    def fake_run(*args, **kwargs):
        input = kwargs.get("input", args[1] if len(args) > 1 else "")
        calls.append(input.strip())
        return _completed(
            stdout=(
                "Table\tCreate Table\n"
                "ads_sales_dashboard\tCREATE TABLE `ads_sales_dashboard` (\n"
                "  `stat_date` date NOT NULL\n"
                ") ENGINE=OLAP\n"
                "PARTITION BY RANGE(`stat_date`) ()\n"
                "DISTRIBUTED BY HASH(`stat_date`) BUCKETS 1"
            )
        )

    monkeypatch.setattr(task_run.subprocess, "run", fake_run)
    task_run._TABLE_PARTITIONED_CACHE.clear()

    assert task_run._is_partitioned_table("shop_dm", "ads_sales_dashboard", ["mysql"]) is True
    assert task_run._is_partitioned_table("shop_dm", "ads_sales_dashboard", ["mysql"]) is True
    assert calls == ["SHOW CREATE TABLE shop_dm.ads_sales_dashboard;"]


def test_ensure_partition_skips_non_partitioned_table(monkeypatch):
    calls = []

    def fake_run(*args, **kwargs):
        input = kwargs.get("input", args[1] if len(args) > 1 else "")
        calls.append(input.strip())
        return _completed(
            stdout=(
                "Table\tCreate Table\n"
                "ads_sales_dashboard\tCREATE TABLE `ads_sales_dashboard` (\n"
                "  `stat_date` date NOT NULL\n"
                ") ENGINE=OLAP\n"
                "DISTRIBUTED BY HASH(`stat_date`) BUCKETS 1"
            )
        )

    monkeypatch.setattr(task_run.subprocess, "run", fake_run)
    task_run._TABLE_PARTITIONED_CACHE.clear()
    task_run._TABLE_PARTITION_UNITS = {}

    task_run._ensure_partition("shop_dm", "ads_sales_dashboard", "2025-01-01", ["mysql"])

    assert calls == ["SHOW CREATE TABLE shop_dm.ads_sales_dashboard;"]


def test_ensure_full_refresh_partitions_skips_non_partitioned_table(monkeypatch):
    calls = []

    def fake_run(*args, **kwargs):
        input = kwargs.get("input", args[1] if len(args) > 1 else "")
        calls.append(input.strip())
        return _completed(
            stdout=(
                "Table\tCreate Table\n"
                "ads_sales_dashboard\tCREATE TABLE `ads_sales_dashboard` (\n"
                "  `stat_date` date NOT NULL\n"
                ") ENGINE=OLAP\n"
                "DISTRIBUTED BY HASH(`stat_date`) BUCKETS 1"
            )
        )

    monkeypatch.setattr(task_run.subprocess, "run", fake_run)
    task_run._TABLE_PARTITIONED_CACHE.clear()

    task_run._ensure_full_refresh_partitions(
        "shop_dm",
        "ads_sales_dashboard",
        ["2025-01-01"],
        ["mysql"],
    )

    assert calls == ["SHOW CREATE TABLE shop_dm.ads_sales_dashboard;"]
