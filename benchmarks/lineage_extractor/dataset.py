from dataclasses import dataclass
from pathlib import Path

PROJECT_NAME = "lineage_benchmark"
CATALOG = "internal"
DATABASE = "lineage_benchmark_dm"


@dataclass(frozen=True)
class BenchmarkProfile:
    name: str
    ods_tables: int
    dwd_tables: int
    dws_tables: int
    ads_tables: int

    @property
    def table_count(self):
        return (
            self.ods_tables
            + self.dwd_tables
            + self.dws_tables
            + self.ads_tables
        )

    @property
    def task_count(self):
        return self.dwd_tables + self.dws_tables + self.ads_tables


@dataclass(frozen=True)
class BenchmarkDataset:
    profile: BenchmarkProfile
    root_dir: Path
    ddl_dir: Path
    tasks_dir: Path
    ddl_files: tuple
    task_files: tuple
    table_count: int
    task_count: int
    column_count: int
    expected_min_edges: int
    project_name: str = PROJECT_NAME
    catalog: str = CATALOG
    database: str = DATABASE


PROFILES = {
    "small": BenchmarkProfile("small", 10, 20, 15, 5),
    "medium": BenchmarkProfile("medium", 60, 120, 80, 40),
    "large": BenchmarkProfile("large", 200, 400, 260, 140),
}


def generate_dataset(size, root_dir):
    profile = _profile(size)
    root = Path(root_dir)
    ddl_dir = root / "ddl"
    tasks_dir = root / "tasks"
    ddl_dir.mkdir(parents=True, exist_ok=True)
    tasks_dir.mkdir(parents=True, exist_ok=True)

    ddl_files = []
    task_files = []
    column_count = 0

    for index in range(profile.ods_tables):
        columns = _ods_columns()
        ddl_files.append(
            _write_table_ddl(
                ddl_dir,
                _ods_table(index),
                columns,
                "DUPLICATE KEY(id)",
            )
        )
        column_count += len(columns)

    for index in range(profile.dwd_tables):
        columns = _dwd_columns()
        table_name = _dwd_table(index)
        ddl_files.append(
            _write_table_ddl(
                ddl_dir,
                table_name,
                columns,
                "UNIQUE KEY(id)",
            )
        )
        task_files.append(
            _write_task(tasks_dir, table_name, _dwd_task_sql(index, profile))
        )
        column_count += len(columns)

    for index in range(profile.dws_tables):
        columns = _dws_columns()
        table_name = _dws_table(index)
        ddl_files.append(
            _write_table_ddl(
                ddl_dir,
                table_name,
                columns,
                "DUPLICATE KEY(stat_date, customer_id, product_id)",
            )
        )
        task_files.append(
            _write_task(tasks_dir, table_name, _dws_task_sql(index, profile))
        )
        column_count += len(columns)

    for index in range(profile.ads_tables):
        columns = _ads_columns()
        table_name = _ads_table(index)
        ddl_files.append(
            _write_table_ddl(
                ddl_dir,
                table_name,
                columns,
                "DUPLICATE KEY(report_date, customer_id, product_id)",
            )
        )
        task_files.append(
            _write_task(tasks_dir, table_name, _ads_task_sql(index, profile))
        )
        column_count += len(columns)

    return BenchmarkDataset(
        profile=profile,
        root_dir=root,
        ddl_dir=ddl_dir,
        tasks_dir=tasks_dir,
        ddl_files=tuple(sorted(ddl_files)),
        task_files=tuple(task_files),
        table_count=profile.table_count,
        task_count=profile.task_count,
        column_count=column_count,
        expected_min_edges=profile.task_count * 8,
    )


def _profile(size):
    try:
        return PROFILES[size]
    except KeyError:
        choices = ", ".join(sorted(PROFILES))
        raise ValueError(
            "unknown benchmark size: {} ({})".format(size, choices)
        ) from None


def _ods_columns():
    return [
        ("id", "BIGINT"),
        ("event_date", "DATE"),
        ("customer_id", "BIGINT"),
        ("product_id", "BIGINT"),
        ("store_id", "BIGINT"),
        ("category_id", "BIGINT"),
        ("campaign_id", "BIGINT"),
        ("region_id", "BIGINT"),
        ("amount", "DECIMAL(18,2)"),
        ("quantity", "INT"),
        ("discount_amount", "DECIMAL(18,2)"),
        ("tax_amount", "DECIMAL(18,2)"),
        ("status", "VARCHAR(16)"),
        ("channel", "VARCHAR(16)"),
        ("source_system", "VARCHAR(32)"),
        ("create_time", "DATETIME"),
        ("update_time", "DATETIME"),
        ("attr_01", "VARCHAR(64)"),
        ("attr_02", "VARCHAR(64)"),
        ("attr_03", "VARCHAR(64)"),
        ("attr_04", "VARCHAR(64)"),
        ("attr_05", "VARCHAR(64)"),
        ("attr_06", "VARCHAR(64)"),
        ("attr_07", "VARCHAR(64)"),
    ]


def _dwd_columns():
    return [
        ("id", "BIGINT"),
        ("event_date", "DATE"),
        ("customer_id", "BIGINT"),
        ("product_id", "BIGINT"),
        ("store_id", "BIGINT"),
        ("category_id", "BIGINT"),
        ("campaign_id", "BIGINT"),
        ("region_id", "BIGINT"),
        ("amount", "DECIMAL(18,2)"),
        ("quantity", "INT"),
        ("discount_amount", "DECIMAL(18,2)"),
        ("tax_amount", "DECIMAL(18,2)"),
        ("status", "VARCHAR(16)"),
        ("channel", "VARCHAR(16)"),
        ("source_system", "VARCHAR(32)"),
        ("net_amount", "DECIMAL(18,2)"),
        ("gross_amount", "DECIMAL(18,2)"),
        ("is_valid", "INT"),
        ("attr_01", "VARCHAR(64)"),
        ("attr_02", "VARCHAR(64)"),
        ("attr_03", "VARCHAR(64)"),
        ("attr_04", "VARCHAR(64)"),
        ("attr_05", "VARCHAR(64)"),
        ("etl_time", "DATETIME"),
    ]


def _dws_columns():
    return [
        ("stat_date", "DATE"),
        ("customer_id", "BIGINT"),
        ("product_id", "BIGINT"),
        ("store_id", "BIGINT"),
        ("category_id", "BIGINT"),
        ("order_count", "BIGINT"),
        ("total_amount", "DECIMAL(18,2)"),
        ("total_quantity", "BIGINT"),
        ("avg_amount", "DECIMAL(18,2)"),
        ("discount_amount", "DECIMAL(18,2)"),
        ("tax_amount", "DECIMAL(18,2)"),
        ("active_days", "BIGINT"),
        ("high_value_count", "BIGINT"),
        ("metric_01", "DECIMAL(18,2)"),
        ("metric_02", "DECIMAL(18,2)"),
        ("metric_03", "DECIMAL(18,2)"),
        ("metric_04", "DECIMAL(18,2)"),
        ("metric_05", "DECIMAL(18,2)"),
        ("metric_06", "DECIMAL(18,2)"),
        ("etl_time", "DATETIME"),
    ]


def _ads_columns():
    return [
        ("report_date", "DATE"),
        ("customer_id", "BIGINT"),
        ("product_id", "BIGINT"),
        ("store_id", "BIGINT"),
        ("category_id", "BIGINT"),
        ("total_amount", "DECIMAL(18,2)"),
        ("total_orders", "BIGINT"),
        ("avg_amount", "DECIMAL(18,2)"),
        ("conversion_rate", "DECIMAL(18,4)"),
        ("high_value_count", "BIGINT"),
        ("metric_01", "DECIMAL(18,2)"),
        ("metric_02", "DECIMAL(18,2)"),
        ("metric_03", "DECIMAL(18,2)"),
        ("metric_04", "DECIMAL(18,2)"),
        ("metric_05", "DECIMAL(18,2)"),
        ("etl_time", "DATETIME"),
    ]


def _write_table_ddl(ddl_dir, table_name, columns, key_clause):
    path = ddl_dir / "{}.sql".format(table_name)
    column_sql = ",\n".join(
        "    {} {}".format(name, data_type) for name, data_type in columns
    )
    path.write_text(
        """CREATE TABLE {database}.{table_name} (
{column_sql}
) ENGINE=OLAP
{key_clause}
DISTRIBUTED BY HASH({distribution_key}) BUCKETS 10
PROPERTIES ("replication_num" = "1");
""".format(
            database=DATABASE,
            table_name=table_name,
            column_sql=column_sql,
            key_clause=key_clause,
            distribution_key=columns[0][0],
        ),
        encoding="utf-8",
    )
    return path


def _write_task(tasks_dir, table_name, sql_text):
    path = tasks_dir / "{}.sql".format(table_name)
    path.write_text(sql_text, encoding="utf-8")
    return path


def _dwd_task_sql(index, profile):
    ods_table = _q(_ods_table(index % profile.ods_tables))
    ref_table = _q(_ods_table((index + 1) % profile.ods_tables))
    target = _q(_dwd_table(index))
    target_columns = _column_list(_dwd_columns())
    select_sql = """SELECT
    o.id,
    o.event_date,
    o.customer_id,
    o.product_id,
    o.store_id,
    o.category_id,
    o.campaign_id,
    o.region_id,
    CAST(o.amount AS DECIMAL(18,2)) AS amount,
    o.quantity,
    o.discount_amount,
    o.tax_amount,
    CASE WHEN o.status = 'paid' THEN 'valid' ELSE o.status END AS status,
    o.channel,
    o.source_system,
    o.amount - o.discount_amount AS net_amount,
    o.amount + o.tax_amount AS gross_amount,
    CASE WHEN o.status = 'paid' THEN 1 ELSE 0 END AS is_valid,
    o.attr_01,
    o.attr_02,
    o.attr_03,
    o.attr_04,
    ref.attr_05,
    NOW() AS etl_time
FROM {ods_table} o
LEFT JOIN {ref_table} ref
    ON o.customer_id = ref.customer_id
WHERE o.event_date >= '2025-01-01'""".format(
        ods_table=ods_table,
        ref_table=ref_table,
    )
    if index % 5 == 0:
        select_sql = """WITH filtered_source AS (
    SELECT *
    FROM {ods_table}
    WHERE event_date >= '2025-01-01'
)
SELECT
    o.id,
    o.event_date,
    o.customer_id,
    o.product_id,
    o.store_id,
    o.category_id,
    o.campaign_id,
    o.region_id,
    CAST(o.amount AS DECIMAL(18,2)) AS amount,
    o.quantity,
    o.discount_amount,
    o.tax_amount,
    CASE WHEN o.status = 'paid' THEN 'valid' ELSE o.status END AS status,
    o.channel,
    o.source_system,
    o.amount - o.discount_amount AS net_amount,
    o.amount + o.tax_amount AS gross_amount,
    CASE WHEN o.status = 'paid' THEN 1 ELSE 0 END AS is_valid,
    o.attr_01,
    o.attr_02,
    o.attr_03,
    o.attr_04,
    ref.attr_05,
    NOW() AS etl_time
FROM filtered_source o
LEFT JOIN {ref_table} ref
    ON o.customer_id = ref.customer_id""".format(
            ods_table=ods_table,
            ref_table=ref_table,
        )
    return """INSERT INTO {target} (
{target_columns}
)
{select_sql};
""".format(
        target=target,
        target_columns=target_columns,
        select_sql=select_sql,
    )


def _dws_task_sql(index, profile):
    source = _q(_dwd_table(index % profile.dwd_tables))
    ref = _q(_dwd_table((index + 1) % profile.dwd_tables))
    target = _q(_dws_table(index))
    return """INSERT INTO {target} (
{target_columns}
)
SELECT
    d.event_date AS stat_date,
    d.customer_id,
    d.product_id,
    d.store_id,
    d.category_id,
    COUNT(*) AS order_count,
    SUM(d.amount) AS total_amount,
    SUM(d.quantity) AS total_quantity,
    AVG(d.amount) AS avg_amount,
    SUM(d.discount_amount) AS discount_amount,
    SUM(d.tax_amount) AS tax_amount,
    COUNT(DISTINCT d.event_date) AS active_days,
    SUM(CASE WHEN d.net_amount > 1000 THEN 1 ELSE 0 END) AS high_value_count,
    SUM(d.net_amount) AS metric_01,
    SUM(d.gross_amount) AS metric_02,
    SUM(ref.net_amount) AS metric_03,
    AVG(ref.gross_amount) AS metric_04,
    SUM(d.amount - d.discount_amount + d.tax_amount) AS metric_05,
    SUM(d.quantity * d.amount) AS metric_06,
    NOW() AS etl_time
FROM {source} d
LEFT JOIN {ref} ref
    ON d.product_id = ref.product_id
WHERE d.is_valid = 1
GROUP BY
    d.event_date,
    d.customer_id,
    d.product_id,
    d.store_id,
    d.category_id;
""".format(
        target=target,
        target_columns=_column_list(_dws_columns()),
        source=source,
        ref=ref,
    )


def _ads_task_sql(index, profile):
    source = _q(_dws_table(index % profile.dws_tables))
    ref = _q(_dws_table((index + 1) % profile.dws_tables))
    target = _q(_ads_table(index))
    return """INSERT INTO {target} (
{target_columns}
)
SELECT
    s.stat_date AS report_date,
    s.customer_id,
    s.product_id,
    s.store_id,
    s.category_id,
    SUM(s.total_amount + ref.total_amount) AS total_amount,
    SUM(s.order_count + ref.order_count) AS total_orders,
    AVG(s.avg_amount) AS avg_amount,
    CASE
        WHEN SUM(ref.order_count) = 0 THEN 0
        ELSE SUM(s.order_count) / SUM(ref.order_count)
    END AS conversion_rate,
    SUM(s.high_value_count) AS high_value_count,
    SUM(s.metric_01) AS metric_01,
    SUM(s.metric_02 + ref.metric_02) AS metric_02,
    AVG(s.metric_03) AS metric_03,
    SUM(ref.metric_04) AS metric_04,
    SUM(s.metric_05 + ref.metric_05) AS metric_05,
    NOW() AS etl_time
FROM {source} s
LEFT JOIN {ref} ref
    ON s.customer_id = ref.customer_id
WHERE s.stat_date >= '2025-01-01'
GROUP BY
    s.stat_date,
    s.customer_id,
    s.product_id,
    s.store_id,
    s.category_id;
""".format(
        target=target,
        target_columns=_column_list(_ads_columns()),
        source=source,
        ref=ref,
    )


def _column_list(columns):
    return ",\n".join("    {}".format(name) for name, _data_type in columns)


def _q(table_name):
    return "{}.{}".format(DATABASE, table_name)


def _ods_table(index):
    return "ods_event_{:04d}".format(index)


def _dwd_table(index):
    return "dwd_fact_{:04d}".format(index)


def _dws_table(index):
    return "dws_summary_{:04d}".format(index)


def _ads_table(index):
    return "ads_report_{:04d}".format(index)
