from __future__ import annotations

from datetime import date

from dw_refactor_agent.refactor.shadow_scope import RowScope
from dw_refactor_agent.sql.doris import (
    PartitionSelectionKind,
    parse_doris_partitions,
    parse_show_partitions,
)
from tests.case_matrix import case_matrix


def test_parse_fixed_range_and_list_partitions():
    range_catalog = parse_doris_partitions(
        """CREATE TABLE dm.sales (stat_date DATE) ENGINE=OLAP
PARTITION BY RANGE(stat_date) (
  PARTITION p202501 VALUES [("2025-01-01"), ("2025-02-01")),
  PARTITION p202502 VALUES [("2025-02-01"), ("2025-03-01"))
);"""
    )
    list_catalog = parse_doris_partitions(
        """CREATE TABLE dm.stores (region_id INT) ENGINE=OLAP
PARTITION BY LIST(region_id) (
  PARTITION p_east VALUES IN (1, 3),
  PARTITION p_west VALUES IN (2, 4)
);"""
    )

    assert range_catalog.map_scope(
        RowScope.point("stat_date", date(2025, 2, 10))
    ).partitions == ("p202502",)
    assert list_catalog.map_scope(
        RowScope.from_points("region_id", (1, 4))
    ).partitions == ("p_east", "p_west")


def test_daily_scope_maps_to_monthly_partition_without_copying_neighbors():
    catalog = parse_doris_partitions(
        """CREATE TABLE dm.sales (stat_date DATE) ENGINE=OLAP
PARTITION BY RANGE(stat_date) (
  PARTITION p202501 VALUES [("2025-01-01"), ("2025-02-01")),
  PARTITION p202502 VALUES [("2025-02-01"), ("2025-03-01"))
);"""
    )

    selection = catalog.map_scope(
        RowScope.interval("stat_date", date(2025, 1, 14), date(2025, 1, 16))
    )

    assert selection.kind is PartitionSelectionKind.PARTITIONS
    assert selection.partitions == ("p202501",)


@case_matrix(
    ("ddl", "scope_date", "reason"),
    [
        (
            """CREATE TABLE dm.sales (stat_date DATE) ENGINE=OLAP
PARTITION BY RANGE(stat_date) (
);""",
            date(2025, 1, 15),
            "no static partitions",
        ),
        (
            """CREATE TABLE dm.sales (stat_date DATE) ENGINE=OLAP
PARTITION BY RANGE(stat_date) (
  PARTITION p202501 VALUES LESS THAN ("2025-02-01")
)
PROPERTIES (
  "dynamic_partition.enable" = "true"
);""",
            date(2025, 3, 15),
            "runtime partitions",
        ),
    ],
    ids=("no-static-partitions", "missing-dynamic-runtime-partition"),
)
def test_partition_catalog_without_static_proof_is_unknown(
    ddl, scope_date, reason
):
    catalog = parse_doris_partitions(ddl)
    selection = catalog.map_scope(RowScope.point("stat_date", scope_date))

    assert selection.kind is PartitionSelectionKind.UNKNOWN
    assert reason in selection.reason


def test_parse_show_partitions_tsv_range_metadata():
    output = "\n".join(
        [
            "PartitionId\tPartitionName\tRange",
            "101\tp202501\t[(2025-01-01), (2025-02-01))",
            "102\tp202502\t[(2025-02-01), (2025-03-01))",
        ]
    )

    catalog = parse_show_partitions(output, "stat_date")
    selection = catalog.map_scope(
        RowScope.point("stat_date", date(2025, 2, 15))
    )

    assert selection.kind is PartitionSelectionKind.PARTITIONS
    assert selection.partitions == ("p202502",)
