import json
import re
import sys
import types

try:
    import sqlglot  # noqa: F401
except ModuleNotFoundError:
    fake_sqlglot = types.ModuleType("sqlglot")
    fake_sqlglot_errors = types.ModuleType("sqlglot.errors")

    class _FakeTable:
        def __init__(self, sql_text):
            self._sql_text = sql_text

        def sql(self, dialect="doris"):
            return self._sql_text

    class _FakeInsert:
        def __init__(self, target):
            self.this = _FakeTable(target)

    class _FakeCreate:
        def __init__(self, target):
            self.this = _FakeTable(target)

    class _FakeUpdate:
        def __init__(self, target):
            self.this = _FakeTable(target)

    def _fake_parse(sql_text, dialect="doris", **_kwargs):
        statements = []
        insert_match = re.search(r"INSERT\s+INTO\s+([^\s(]+)", sql_text, re.IGNORECASE)
        if insert_match:
            statements.append(_FakeInsert(insert_match.group(1)))
        create_match = re.search(r"CREATE\s+TABLE\s+([^\s(]+)", sql_text, re.IGNORECASE)
        if create_match:
            statements.append(_FakeCreate(create_match.group(1)))
        update_match = re.search(r"UPDATE\s+([^\s(]+)", sql_text, re.IGNORECASE)
        if update_match:
            statements.append(_FakeUpdate(update_match.group(1)))
        return statements

    fake_sqlglot.parse = _fake_parse
    fake_sqlglot.exp = types.SimpleNamespace(
        Insert=_FakeInsert,
        Create=_FakeCreate,
        Update=_FakeUpdate,
    )
    fake_sqlglot_errors.ErrorLevel = types.SimpleNamespace(IGNORE="IGNORE")
    sys.modules["sqlglot"] = fake_sqlglot
    sys.modules["sqlglot.errors"] = fake_sqlglot_errors

try:
    import yaml  # noqa: F401
except ModuleNotFoundError:
    fake_yaml = types.ModuleType("yaml")
    fake_yaml.safe_load = lambda _: {}
    sys.modules["yaml"] = fake_yaml

import lineage.refresh_lineage_html as refresh_html


def test_resolve_lineage_data_path_prefers_project_specific(monkeypatch, tmp_path):
    monkeypatch.setattr(refresh_html, "LINEAGE_DIR", tmp_path)
    project_file = tmp_path / "lineage_data_shop.json"
    legacy_file = tmp_path / "lineage_data.json"
    project_file.write_text('{"source": "project"}', encoding="utf-8")
    legacy_file.write_text('{"source": "legacy"}', encoding="utf-8")

    assert refresh_html.resolve_lineage_data_path("shop") == project_file


def test_resolve_lineage_data_path_shop_falls_back_to_legacy(monkeypatch, tmp_path):
    monkeypatch.setattr(refresh_html, "LINEAGE_DIR", tmp_path)
    legacy_file = tmp_path / "lineage_data.json"
    legacy_file.write_text('{"source": "legacy"}', encoding="utf-8")

    assert refresh_html.resolve_lineage_data_path("shop") == legacy_file


def test_resolve_output_paths_uses_project_isolation_for_non_shop(monkeypatch, tmp_path):
    monkeypatch.setattr(refresh_html, "LINEAGE_DIR", tmp_path)

    paths = refresh_html.resolve_output_paths("finance_analytics")

    assert paths["job_template"] == tmp_path / "lineage_job.html"
    assert paths["lineage_template"] == tmp_path / "lineage.html"
    assert paths["job_output"] == tmp_path / "lineage_job_finance_analytics.html"
    assert paths["lineage_output"] == tmp_path / "lineage_finance_analytics.html"


def test_generate_jobs_strips_project_db_and_defaults_logic(tmp_path, monkeypatch):
    monkeypatch.setattr(
        refresh_html,
        "determine_layer",
        lambda table_name, project: (
            "DWD" if table_name.startswith("dwd_") else "OTHER"
        ),
    )

    tasks_dir = tmp_path / "tasks"
    tasks_dir.mkdir()
    (tasks_dir / "dwd_accounts.sql").write_text(
        """
        INSERT INTO finance_analytics_dm.dwd_accounts
        SELECT account_id
        FROM finance_analytics_dm.ods_accounts;
        """,
        encoding="utf-8",
    )
    data = {
        "edges": [
            {
                "source": "finance_analytics_dm.ods_accounts.account_id",
                "target": "finance_analytics_dm.dwd_accounts.account_id",
                "source_file": "dwd_accounts.sql",
            }
        ]
    }

    jobs = refresh_html.generate_jobs(
        data,
        tasks_dir=tasks_dir,
        current_db="finance_analytics_dm",
        project="finance_analytics",
    )

    assert len(jobs) == 1
    job = jobs[0]
    assert job["id"] == "dwd_accounts"
    assert job["source"] == ["ods_accounts"]
    assert job["target"] == "dwd_accounts"
    assert job["layer"] == "DWD"
    assert job["logic"] == "-"


def test_generate_jobs_includes_full_refresh_tasks(tmp_path, monkeypatch):
    monkeypatch.setattr(
        refresh_html,
        "determine_layer",
        lambda table_name, project: "DWD",
    )

    tasks_dir = tmp_path / "tasks"
    full_refresh_dir = tasks_dir / "full_refresh"
    full_refresh_dir.mkdir(parents=True)
    (tasks_dir / "dwd_product.sql").write_text(
        """
        INSERT INTO shop_dm.dwd_product
        SELECT product_id
        FROM shop_dm.ods_product;
        """,
        encoding="utf-8",
    )
    (full_refresh_dir / "dwd_product_full_refresh.sql").write_text(
        """
        INSERT INTO shop_dm.dwd_product
        SELECT product_id
        FROM shop_dm.ods_product;
        """,
        encoding="utf-8",
    )
    data = {
        "edges": [
            {
                "source": "ods_product.product_id",
                "target": "dwd_product.product_id",
                "source_file": "dwd_product.sql",
            },
            {
                "source": "ods_product.product_id",
                "target": "dwd_product.product_id",
                "source_file": "full_refresh/dwd_product_full_refresh.sql",
            },
        ]
    }

    jobs = refresh_html.generate_jobs(
        data,
        tasks_dir=tasks_dir,
        current_db="shop_dm",
        project="shop",
    )

    assert [job["id"] for job in jobs] == [
        "dwd_product",
        "full_refresh/dwd_product_full_refresh",
    ]
    assert jobs[1]["file"] == "full_refresh/dwd_product_full_refresh.sql"
    assert jobs[1]["target"] == "dwd_product"


def test_update_lineage_html_writes_new_output_from_template(tmp_path):
    template = tmp_path / "lineage.html"
    output = tmp_path / "lineage_finance_analytics.html"
    template.write_text(
        '<script>const LINEAGE_DATA = {"old": true};</script>',
        encoding="utf-8",
    )
    payload = json.dumps({"nodes": [{"id": 1}]}, ensure_ascii=False)

    refresh_html.update_lineage_html(payload, template_path=template, output_path=output)

    assert '{"nodes": [{"id": 1}]}' in output.read_text(encoding="utf-8")
    assert '{"old": true}' in template.read_text(encoding="utf-8")
