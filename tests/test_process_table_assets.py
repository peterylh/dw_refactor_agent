import re

from dw_refactor_agent.config import project_dir as configured_project_dir
from tests.case_matrix import case_matrix

PROCESS_PRODUCER_TASKS = (
    (
        "shop",
        "mid/tasks/dws_store_sales_daily.sql",
        "shop_dm.stage_store_sales_daily",
    ),
    (
        "shop",
        "mid/tasks/full_refresh/dws_store_sales_daily_full_refresh.sql",
        "shop_dm.stage_store_sales_daily",
    ),
    (
        "retail_banking",
        "mid/tasks/dws_client_transaction_daily.sql",
        "retail_banking_dm.stage_client_transaction_daily",
    ),
    (
        "retail_banking",
        (
            "mid/tasks/full_refresh/"
            "dws_client_transaction_daily_full_refresh.sql"
        ),
        "retail_banking_dm.stage_client_transaction_daily",
    ),
)


def _task_sql(project: str, relative_path: str) -> str:
    project_path = configured_project_dir(project)
    assert project_path is not None
    return (project_path / relative_path).read_text(encoding="utf-8")


@case_matrix(
    ("project", "relative_path", "process_table"),
    PROCESS_PRODUCER_TASKS,
    ids=("shop-slice", "shop-window", "retail-slice", "retail-window"),
)
def test_process_producer_ctas_is_one_replica_and_immutable(
    project: str,
    relative_path: str,
    process_table: str,
) -> None:
    sql = _task_sql(project, relative_path)
    ctas = re.search(
        rf"CREATE\s+TABLE\s+{re.escape(process_table)}\s+"
        r'PROPERTIES\s*\(\s*"replication_num"\s*=\s*"1"\s*\)\s+AS\b',
        sql,
        flags=re.IGNORECASE | re.DOTALL,
    )

    assert ctas is not None
    assert not re.search(
        rf"\b(?:DELETE\s+FROM|UPDATE|TRUNCATE\s+TABLE|INSERT\s+INTO|"
        rf"ALTER\s+TABLE|DROP\s+TABLE(?:\s+IF\s+EXISTS)?)\s+"
        rf"{re.escape(process_table)}\b",
        sql[ctas.end() :],
        flags=re.IGNORECASE,
    )


@case_matrix(
    "relative_path",
    (
        "mid/tasks/dws_store_sales_daily.sql",
        "mid/tasks/full_refresh/dws_store_sales_daily_full_refresh.sql",
    ),
    ids=("slice", "window"),
)
def test_shop_process_cleanup_is_folded_into_ctas(
    relative_path: str,
) -> None:
    sql = _task_sql("shop", relative_path)

    assert "COALESCE(SUM(discount), 0.00) AS discount_amount" in sql
    assert re.search(
        r"HAVING\s+COUNT\(DISTINCT\s+order_id\)\s*<>\s*0\s+AND\s*"
        r"\(\s*SUM\(subtotal\s*-\s*discount\)\s+IS\s+NULL\s+OR\s+"
        r"SUM\(subtotal\s*-\s*discount\)\s*>=\s*0\s*\)",
        sql,
        flags=re.IGNORECASE | re.DOTALL,
    )
