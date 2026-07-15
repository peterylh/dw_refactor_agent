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
from tests.case_matrix import case_matrix

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


def test_init_project_preflights_duplicate_ids_before_writing(
    tmp_path, monkeypatch
):
    ddl_dir = _configure_project(tmp_path, monkeypatch)
    missing_path = ddl_dir / "a_missing.sql"
    missing_text = _ddl("demo_dm.a_missing")
    missing_path.write_text(missing_text, encoding="utf-8")
    (ddl_dir / "b_identified.sql").write_text(
        _ddl(
            "demo_dm.b_identified",
            table_id=TABLE_ID,
            first_column_id=FIRST_COLUMN_ID,
            second_column_id=SECOND_COLUMN_ID,
        ),
        encoding="utf-8",
    )
    (ddl_dir / "c_duplicate.sql").write_text(
        _ddl(
            "demo_dm.c_duplicate",
            table_id=TABLE_ID,
            first_column_id="3d8b5422-027b-4d15-9db3-2d50e83bbef8",
            second_column_id="ffdf6876-6258-46b3-a35a-2f49718260df",
        ),
        encoding="utf-8",
    )

    with pytest.raises(SchemaIdentityError, match="duplicate_table_id"):
        init_project("demo")

    assert missing_path.read_text(encoding="utf-8") == missing_text


def test_init_project_replaces_invalid_table_ids_only_when_explicit(
    tmp_path, monkeypatch
):
    ddl_dir = _configure_project(tmp_path, monkeypatch)
    invalid_id = "not a uuid"
    path = ddl_dir / "dwd_order.sql"
    path.write_text(_ddl(table_id=invalid_id), encoding="utf-8")

    with pytest.raises(SchemaIdentityError, match="invalid_table_id"):
        init_project("demo")

    assignments = init_project("demo", replace_invalid_table_ids=True)

    table = parse_create_table(path.read_text(encoding="utf-8"))
    assert table is not None
    assert table.table_id != invalid_id
    _assert_uuid4(table.table_id)
    assert path.read_text(encoding="utf-8").count("table_id:") == 1
    assert validate_project("demo") == []
    assert [assignment.kind for assignment in assignments] == [
        "table",
        "column",
        "column",
    ]


def test_validate_project_rejects_table_id_after_create(tmp_path, monkeypatch):
    ddl_dir = _configure_project(tmp_path, monkeypatch)
    text = _ddl(
        table_id=TABLE_ID,
        first_column_id=FIRST_COLUMN_ID,
        second_column_id=SECOND_COLUMN_ID,
    )
    text = text.replace(f"-- table_id: {TABLE_ID}\n", "")
    path = ddl_dir / "dwd_order.sql"
    path.write_text(f"{text}\n-- table_id: {TABLE_ID}\n", encoding="utf-8")

    issues = validate_project("demo")

    assert "orphan_table_id" in {issue.code for issue in issues}


def test_validate_project_rejects_multiple_create_tables(
    tmp_path, monkeypatch
):
    ddl_dir = _configure_project(tmp_path, monkeypatch)
    first = _ddl(
        table_id=TABLE_ID,
        first_column_id=FIRST_COLUMN_ID,
        second_column_id=SECOND_COLUMN_ID,
    )
    second = _ddl(
        "demo_dm.dwd_payment",
        table_id="1db7309f-1f9e-4393-807c-7d836ea25727",
        first_column_id="3d8b5422-027b-4d15-9db3-2d50e83bbef8",
        second_column_id="ffdf6876-6258-46b3-a35a-2f49718260df",
    ).replace("CREATE TABLE", "CREATE /* second table */ TABLE")
    (ddl_dir / "combined.sql").write_text(
        first + "\n" + second, encoding="utf-8"
    )

    issues = validate_project("demo")

    assert "multiple_create_tables" in {issue.code for issue in issues}


def test_validate_project_scans_nonrequired_projects_for_duplicate_ids(
    tmp_path, monkeypatch
):
    ddl_dir = _configure_project(tmp_path, monkeypatch)
    ddl = _ddl(
        table_id=TABLE_ID,
        first_column_id=FIRST_COLUMN_ID,
        second_column_id=SECOND_COLUMN_ID,
    )
    (ddl_dir / "dwd_order.sql").write_text(ddl, encoding="utf-8")
    other_dir = tmp_path / "other" / "mid" / "ddl"
    other_dir.mkdir(parents=True)
    (other_dir / "dwd_order_copy.sql").write_text(
        ddl.replace("demo_dm.dwd_order", "other_dm.dwd_order_copy"),
        encoding="utf-8",
    )
    monkeypatch.setitem(
        config.PROJECT_CONFIG,
        "other",
        {
            "dir": "other",
            "db": "other_dm",
            "qa_db": "other_dm_qa",
            "catalog": "internal",
        },
    )

    issues = validate_project("demo")

    assert [issue.code for issue in issues].count("duplicate_table_id") == 2
    assert [issue.code for issue in issues].count("duplicate_column_id") == 4


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


@case_matrix("project", ["shop", "finance_analytics"])
def test_migrated_managed_projects_have_complete_schema_ids(project):
    assert validate_project(project) == []
