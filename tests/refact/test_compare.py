import json

from refact.compare import compare_shadow_results, fmt_val, run_checks


class FakeCursor:
    def __init__(self, results):
        self.results = list(results)
        self.executed = []

    def execute(self, sql):
        self.executed.append(sql)

    def fetchone(self):
        return self.results.pop(0)

    def fetchall(self):
        return self.results.pop(0)

    def close(self):
        pass


class FakeConn:
    def __init__(self, cursors):
        self.cursors = list(cursors)
        self.closed = False

    def cursor(self):
        return self.cursors.pop(0)

    def close(self):
        self.closed = True


def test_fmt_val_formats_supported_scalar_values():
    scenarios = [
        (None, "NULL"),
        (123, "123"),
        (3.14159, "3.141590"),
        ("hello", "hello"),
    ]

    for value, expected in scenarios:
        assert fmt_val(value) == expected


def test_run_checks_compares_count_self_contained(monkeypatch):
    prod_conn = FakeConn([FakeCursor([(12,)])])
    qa_conn = FakeConn([FakeCursor([(12,)])])

    def fake_conn(db_name, qa=False):
        return qa_conn if qa else prod_conn

    monkeypatch.setattr("refact.compare.get_pymysql_conn", fake_conn)

    result = run_checks(
        {
            "project_db": "shop_dm",
            "qa_db": "shop_dm_qa",
            "verification": {
                "checks": [{"table": "ads_sales_dashboard", "method": "count"}]
            },
        },
        method="count",
    )

    assert result["all_pass"] is True
    assert result["results"][0]["prod_count"] == 12
    assert result["results"][0]["qa_count"] == 12
    assert prod_conn.closed is True
    assert qa_conn.closed is True


def test_run_checks_ignores_legacy_top_level_checks(monkeypatch):
    def fail_if_called(db_name, qa=False):
        raise AssertionError("legacy top-level checks should be ignored")

    monkeypatch.setattr("refact.compare.get_pymysql_conn", fail_if_called)

    result = run_checks(
        {
            "project_db": "shop_dm",
            "qa_db": "shop_dm_qa",
            "checks": [{"table": "ads_sales_dashboard", "method": "count"}],
        },
        method="count",
    )

    assert result == {"all_pass": True, "results": []}


def test_compare_shadow_results_writes_compare_output(tmp_path, monkeypatch):
    plan_path = tmp_path / "verification" / "plan.json"
    output_path = tmp_path / "verification" / "compare_result.json"
    plan_path.parent.mkdir(parents=True)
    plan_path.write_text(
        json.dumps(
            {"project": "shop", "project_db": "shop_dm", "qa_db": "shop_dm_qa"}
        ),
        encoding="utf-8",
    )

    def fake_run_checks(meta, method="all", sample=0, precision=0.01):
        return {
            "all_pass": True,
            "results": [],
            "method": method,
            "sample": sample,
            "precision": precision,
        }

    monkeypatch.setattr("refact.compare.run_checks", fake_run_checks)

    result = compare_shadow_results(
        plan_path,
        output_path,
        method="count",
        sample=10,
        precision=0.1,
    )

    assert result["method"] == "count"
    assert result["sample"] == 10
    assert result["precision"] == 0.1
    assert json.loads(output_path.read_text(encoding="utf-8")) == result
