import uuid

import pytest

import dw_refactor_agent.config as config
from dw_refactor_agent.ddl_deriver.ddl_deriver import parse_create_table
from dw_refactor_agent.ddl_deriver.schema_ids import (
    SchemaIdentityError,
    assign_column,
    init_file,
    init_project,
    main,
    validate_project,
)

TABLE_ID = "91ed8f6a-736d-4896-888e-f9225741b7fa"
FIRST_COLUMN_ID = "6bfa89c0-1e30-4f92-a25e-b5a39ab94880"
SECOND_COLUMN_ID = "77eb791d-9856-4cc2-a77c-89f46ee626b2"


def _ddl(
    table_name="demo_dm.dwd_order",
    *,
    table_id="",
    first_column_id="",
    second_column_id="",
):
    table_marker = f"-- table_id: {table_id}\n" if table_id else ""
    first_marker = (
        f"    -- column_id: {first_column_id}\n" if first_column_id else ""
    )
    second_marker = (
        f"    -- column_id: {second_column_id}\n" if second_column_id else ""
    )
    return f"""\
-- DWD order
{table_marker}CREATE TABLE {table_name} (
{first_marker}    order_id BIGINT NOT NULL COMMENT 'Order ID',
{second_marker}    amount DECIMAL(12,2) NOT NULL COMMENT 'Amount'
) ENGINE=OLAP
DUPLICATE KEY(order_id)
DISTRIBUTED BY HASH(order_id) BUCKETS 10;
"""


def _assert_uuid4(value):
    parsed = uuid.UUID(value)
    assert parsed.version == 4
    assert str(parsed) == value


def test_init_file_assigns_table_and_column_ids_idempotently(tmp_path):
    path = tmp_path / "dwd_order.sql"
    original = _ddl()
    path.write_text(original, encoding="utf-8")

    assignments = init_file(path)

    table = parse_create_table(path.read_text(encoding="utf-8"))
    assert table is not None
    assert len(assignments) == 3
    _assert_uuid4(table.table_id)
    assert len(table.columns) == 2
    for column in table.columns:
        _assert_uuid4(column.column_id)
    generated = path.read_text(encoding="utf-8")
    assert (
        generated.replace(f"-- table_id: {table.table_id}\n", "")
        .replace(f"    -- column_id: {table.columns[0].column_id}\n", "")
        .replace(f"    -- column_id: {table.columns[1].column_id}\n", "")
        == original
    )

    assert init_file(path) == []
    assert path.read_text(encoding="utf-8") == generated


def test_assign_column_only_identifies_explicit_new_column(tmp_path):
    path = tmp_path / "dwd_order.sql"
    path.write_text(
        _ddl(table_id=TABLE_ID, first_column_id=FIRST_COLUMN_ID),
        encoding="utf-8",
    )

    assignment = assign_column(path, "amount")

    table = parse_create_table(path.read_text(encoding="utf-8"))
    assert table is not None
    assert assignment.kind == "column"
    assert assignment.column_name == "amount"
    assert table.table_id == TABLE_ID
    assert table.columns[0].column_id == FIRST_COLUMN_ID
    assert table.columns[1].column_id == assignment.value
    _assert_uuid4(assignment.value)

    with pytest.raises(ValueError, match="已有 column_id"):
        assign_column(path, "amount")


def _configure_project(tmp_path, monkeypatch, project="demo"):
    project_dir = tmp_path / project
    ddl_dir = project_dir / "mid" / "ddl"
    ddl_dir.mkdir(parents=True)
    monkeypatch.setattr(config.core, "PROJECT_ROOT", tmp_path)
    monkeypatch.setitem(
        config.PROJECT_CONFIG,
        project,
        {
            "dir": project,
            "db": f"{project}_dm",
            "qa_db": f"{project}_dm_qa",
            "catalog": "internal",
        },
    )
    return ddl_dir


def test_validate_project_reports_missing_schema_ids(tmp_path, monkeypatch):
    ddl_dir = _configure_project(tmp_path, monkeypatch)
    (ddl_dir / "dwd_order.sql").write_text(_ddl(), encoding="utf-8")

    issues = validate_project("demo")

    assert [issue.code for issue in issues] == [
        "missing_table_id",
        "missing_column_id",
        "missing_column_id",
    ]
    assert [issue.column_name for issue in issues[1:]] == [
        "order_id",
        "amount",
    ]


def test_validate_project_reports_invalid_or_orphan_markers(
    tmp_path, monkeypatch
):
    ddl_dir = _configure_project(tmp_path, monkeypatch)
    text = _ddl(
        table_id="not-a-uuid",
        first_column_id="also-not-a-uuid",
        second_column_id=SECOND_COLUMN_ID,
    )
    text = text.replace(
        "CREATE TABLE",
        "-- column_id: 1db7309f-1f9e-4393-807c-7d836ea25727\nCREATE TABLE",
    )
    (ddl_dir / "dwd_order.sql").write_text(text, encoding="utf-8")

    issues = validate_project("demo")

    assert {issue.code for issue in issues} == {
        "invalid_table_id",
        "invalid_column_id",
        "orphan_column_id",
    }


def test_validate_project_reports_duplicate_ids_across_files(
    tmp_path, monkeypatch
):
    ddl_dir = _configure_project(tmp_path, monkeypatch)
    (ddl_dir / "dwd_order.sql").write_text(
        _ddl(
            table_id=TABLE_ID,
            first_column_id=FIRST_COLUMN_ID,
            second_column_id=SECOND_COLUMN_ID,
        ),
        encoding="utf-8",
    )
    (ddl_dir / "dwd_payment.sql").write_text(
        _ddl(
            "demo_dm.dwd_payment",
            table_id=TABLE_ID,
            first_column_id=FIRST_COLUMN_ID,
            second_column_id="1db7309f-1f9e-4393-807c-7d836ea25727",
        ),
        encoding="utf-8",
    )

    issues = validate_project("demo")

    assert [issue.code for issue in issues].count("duplicate_table_id") == 2
    assert [issue.code for issue in issues].count("duplicate_column_id") == 2


def test_validate_project_accepts_complete_unique_ids(tmp_path, monkeypatch):
    ddl_dir = _configure_project(tmp_path, monkeypatch)
    (ddl_dir / "dwd_order.sql").write_text(
        _ddl(
            table_id=TABLE_ID,
            first_column_id=FIRST_COLUMN_ID,
            second_column_id=SECOND_COLUMN_ID,
        ),
        encoding="utf-8",
    )

    assert validate_project("demo") == []


def test_init_project_identifies_every_managed_ddl_file(tmp_path, monkeypatch):
    ddl_dir = _configure_project(tmp_path, monkeypatch)
    (ddl_dir / "dwd_order.sql").write_text(_ddl(), encoding="utf-8")

    assignments = init_project("demo")

    assert len(assignments) == 3
    assert init_project("demo") == []
    assert validate_project("demo") == []


def test_init_project_preflights_all_files_before_writing(
    tmp_path, monkeypatch
):
    ddl_dir = _configure_project(tmp_path, monkeypatch)
    first_path = ddl_dir / "dwd_order.sql"
    first_text = _ddl()
    first_path.write_text(first_text, encoding="utf-8")
    invalid_path = ddl_dir / "dwd_payment.sql"
    invalid_path.write_text(
        _ddl("demo_dm.dwd_payment").replace(
            "CREATE TABLE",
            f"-- column_id: {SECOND_COLUMN_ID}\nCREATE TABLE",
        ),
        encoding="utf-8",
    )

    with pytest.raises(SchemaIdentityError, match="orphan_column_id"):
        init_project("demo")

    assert first_path.read_text(encoding="utf-8") == first_text


def test_init_project_replaces_invalid_table_ids_only_when_explicit(
    tmp_path, monkeypatch
):
    ddl_dir = _configure_project(tmp_path, monkeypatch)
    invalid_id = "c4d5e6f7-a8b9-4c0d-1e2f-3a4b5c6d7e8f"
    path = ddl_dir / "dwd_order.sql"
    path.write_text(_ddl(table_id=invalid_id), encoding="utf-8")

    with pytest.raises(SchemaIdentityError, match="invalid_table_id"):
        init_project("demo")

    assignments = init_project("demo", replace_invalid_table_ids=True)

    table = parse_create_table(path.read_text(encoding="utf-8"))
    assert table is not None
    assert table.table_id != invalid_id
    _assert_uuid4(table.table_id)
    assert [assignment.kind for assignment in assignments] == [
        "table",
        "column",
        "column",
    ]


def test_cli_validate_returns_nonzero_for_identity_issues(
    tmp_path, monkeypatch, capsys
):
    ddl_dir = _configure_project(tmp_path, monkeypatch)
    (ddl_dir / "dwd_order.sql").write_text(_ddl(), encoding="utf-8")

    exit_code = main(["validate", "--project", "demo"])

    assert exit_code == 1
    output = capsys.readouterr().out
    assert "missing_table_id" in output
    assert "校验失败: 3 个问题" in output


@pytest.mark.parametrize("project", ["shop", "finance_analytics"])
def test_migrated_managed_projects_have_complete_schema_ids(project):
    assert validate_project(project) == []
