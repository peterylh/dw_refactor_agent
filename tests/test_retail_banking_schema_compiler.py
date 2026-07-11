import pytest

from warehouses.retail_banking.tools import build_assets


def _write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value, encoding="utf-8")


def _database_changelog(children):
    return "<databaseChangeLog>{}</databaseChangeLog>".format(children)


def _fineract_fixture(tmp_path, *, raw_sql=False):
    provider = tmp_path / "fineract-provider/src/main/resources/db/changelog"
    savings_resource = (
        tmp_path
        / "fineract-savings/src/main/resources/db/changelog/tenant/module/"
        "savings/parts"
    )
    _write(
        provider / "db.changelog-master.xml",
        _database_changelog(
            '<include file="tenant/initial-switch-changelog-tenant.xml" '
            'relativeToChangelogFile="true" '
            'context="tenant_db AND initial_switch"/>'
            '<include file="tenant/changelog-tenant.xml" '
            'relativeToChangelogFile="true" '
            'context="tenant_db AND !initial_switch"/>'
            '<include file="db/changelog/tenant/module/savings/parts/'
            'module-changelog-master.xml" '
            'context="tenant_db AND !initial_switch"/>'
            '<include file="tenant/final-changelog-tenant.xml" '
            'relativeToChangelogFile="true" '
            'context="tenant_db AND !initial_switch"/>'
        ),
    )
    _write(
        provider / "tenant/initial-switch-changelog-tenant.xml",
        _database_changelog(
            '<include file="parts/0001_initial_schema.xml" '
            'relativeToChangelogFile="true"/>'
        ),
    )
    _write(
        provider / "tenant/parts/0001_initial_schema.xml",
        _database_changelog(
            '<changeSet id="1" author="test">'
            '<createTable tableName="m_savings_account">'
            '<column name="id" type="BIGINT"/>'
            '<column name="status_enum" type="INT" defaultValueNumeric="1"/>'
            "</createTable>"
            '<createTable tableName="m_savings_account_transaction">'
            '<column name="id" type="BIGINT"/>'
            '<column name="savings_account_id" type="BIGINT"/>'
            '<column name="legacy_code" type="VARCHAR(10)" '
            'defaultValue="legacy"><constraints nullable="false"/></column>'
            "</createTable>"
            "</changeSet>"
        ),
    )
    raw_change = (
        '<changeSet id="raw" author="test">'
        "<sql>ALTER TABLE m_savings_account ADD COLUMN raw_only TEXT</sql>"
        "</changeSet>"
        if raw_sql
        else ""
    )
    _write(
        provider / "tenant/changelog-tenant.xml",
        _database_changelog(raw_change),
    )
    _write(
        savings_resource / "module-changelog-master.xml",
        _database_changelog(
            '<include file="parts/2003_add_accrued.xml" '
            'relativeToChangelogFile="true"/>'
            '<include file="parts/2005_add_external_id.xml" '
            'relativeToChangelogFile="true"/>'
        ),
    )
    _write(
        savings_resource / "parts/2003_add_accrued.xml",
        _database_changelog(
            '<changeSet id="2003" author="test">'
            '<addColumn tableName="m_savings_account">'
            '<column name="accrued_till_date" type="DATE" '
            'defaultValueComputed="NULL"/>'
            "</addColumn>"
            "</changeSet>"
        ),
    )
    _write(
        savings_resource / "parts/2005_add_external_id.xml",
        _database_changelog(
            '<changeSet id="2005" author="test">'
            '<addColumn tableName="m_savings_account_transaction">'
            '<column name="external_id" type="VARCHAR(100)"/>'
            "</addColumn>"
            '<addUniqueConstraint tableName="m_savings_account_transaction" '
            'columnNames="external_id" constraintName="uk_savings_external"/>'
            "</changeSet>"
        ),
    )
    _write(
        provider / "tenant/final-changelog-tenant.xml",
        _database_changelog(
            '<include file="parts/9999_constraints.xml" '
            'relativeToChangelogFile="true"/>'
        ),
    )
    _write(
        provider / "tenant/parts/9999_constraints.xml",
        _database_changelog(
            '<changeSet id="9999" author="test">'
            '<addPrimaryKey tableName="m_savings_account" '
            'columnNames="id" constraintName="pk_savings"/>'
            '<addPrimaryKey tableName="m_savings_account_transaction" '
            'columnNames="id" constraintName="pk_savings_transaction"/>'
            "<addForeignKeyConstraint "
            'baseTableName="m_savings_account_transaction" '
            'baseColumnNames="savings_account_id" '
            'referencedTableName="m_savings_account" '
            'referencedColumnNames="id" constraintName="fk_transaction_account"/>'
            '<addNotNullConstraint tableName="m_savings_account_transaction" '
            'columnName="external_id" columnDataType="VARCHAR(100)"/>'
            '<addDefaultValue tableName="m_savings_account_transaction" '
            'columnName="external_id" defaultValueComputed="uuid_generate_v4()"/>'
            '<dropNotNullConstraint tableName="m_savings_account_transaction" '
            'columnName="legacy_code" columnDataType="VARCHAR(10)"/>'
            '<dropDefaultValue tableName="m_savings_account_transaction" '
            'columnName="legacy_code"/>'
            "</changeSet>"
        ),
    )
    return tmp_path


def test_schema_compiler_recurses_nested_clean_install_changelogs(tmp_path):
    root = _fineract_fixture(tmp_path)

    files = build_assets.discover_changelog_files(root)
    tables = build_assets.parse_fineract_schema(root)

    assert any(
        "parts/parts/2003_add_accrued.xml" in str(path) for path in files
    )
    assert "accrued_till_date" in tables["m_savings_account"].columns
    assert (
        tables["m_savings_account"].columns["accrued_till_date"].default_value
        == "NULL"
    )
    transaction = tables["m_savings_account_transaction"]
    assert "external_id" in transaction.columns
    assert transaction.columns["external_id"].nullable is False
    assert (
        transaction.columns["external_id"].default_value
        == "uuid_generate_v4()"
    )
    assert transaction.columns["legacy_code"].nullable is True
    assert transaction.columns["legacy_code"].default_value is None
    assert transaction.primary_key == ["id"]
    assert transaction.unique_constraints == [
        {"name": "uk_savings_external", "columns": ["external_id"]}
    ]
    assert transaction.foreign_keys[0]["base_columns"] == [
        "savings_account_id"
    ]
    assert (
        transaction.foreign_keys[0]["referenced_table"] == "m_savings_account"
    )


def test_schema_compiler_fails_closed_until_raw_sql_is_overridden(tmp_path):
    root = _fineract_fixture(tmp_path, raw_sql=True)

    with pytest.raises(ValueError, match="Unresolved Liquibase SQL"):
        build_assets.parse_fineract_schema(root)

    tables = build_assets.parse_fineract_schema(
        root,
        unresolved_overrides=[
            {
                "table": "m_savings_account",
                "pattern": "*raw SQL migration requires review",
                "rationale": "Fixture SQL was reviewed explicitly.",
            }
        ],
    )
    payload = build_assets._schema_payload(tables["m_savings_account"])
    assert payload["unresolved_changes"] == [
        {
            "operation": "sql",
            "source": (
                "fineract-provider/src/main/resources/db/changelog/tenant/"
                "changelog-tenant.xml"
            ),
            "description": (
                "fineract-provider/src/main/resources/db/changelog/tenant/"
                "changelog-tenant.xml: raw SQL migration requires review"
            ),
            "status": "overridden",
            "override_rationale": "Fixture SQL was reviewed explicitly.",
        }
    ]


def test_schema_compiler_ignores_non_postgresql_operations(tmp_path):
    root = _fineract_fixture(tmp_path)
    changelog = (
        root / "fineract-provider/src/main/resources/db/changelog/tenant/"
        "changelog-tenant.xml"
    )
    _write(
        changelog,
        _database_changelog(
            '<changeSet id="mysql-context" author="test" context="mysql">'
            "<sql>ALTER TABLE m_savings_account "
            "ADD COLUMN mysql_context_only TEXT</sql>"
            "</changeSet>"
            '<changeSet id="dbms" author="test">'
            '<sql dbms="mysql">ALTER TABLE m_savings_account '
            "ADD COLUMN mysql_only TEXT</sql>"
            '<sql dbms="postgresql">UPDATE m_savings_account SET id = id</sql>'
            "</changeSet>"
        ),
    )

    tables = build_assets.parse_fineract_schema(
        root,
        unresolved_overrides=[
            {
                "table": "m_savings_account",
                "pattern": "*raw SQL migration requires review",
                "rationale": "PostgreSQL fixture data update was reviewed.",
            }
        ],
    )

    changes = tables["m_savings_account"].unresolved_changes
    assert len(changes) == 1
    assert changes[0]["status"] == "overridden"
