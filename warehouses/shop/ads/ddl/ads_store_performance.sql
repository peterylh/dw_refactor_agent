-- ADS 门店绩效评估表
-- table_id: b6e00810-e675-41a8-bc53-22b826fa1e23
DROP TABLE IF EXISTS shop_dm.ads_store_performance;
CREATE TABLE IF NOT EXISTS shop_dm.ads_store_performance (
    -- column_id: 95b29b6f-0202-44f9-96eb-d14074ef0b74
    store_id         BIGINT        NOT NULL COMMENT '门店ID',
    -- column_id: 5087eb4c-7a4f-4a99-9898-d22b84b6c5f2
    stat_month       VARCHAR(7)    NOT NULL COMMENT '统计月份:YYYY-MM',
    -- column_id: f8bf8eb7-432a-44c0-8adf-54228ae79cc2
    stat_month_date  DATE          NOT NULL COMMENT '统计月份(月初日期)',
    -- column_id: fa16e826-ef25-4b8c-82c9-8d4f79cccfb3
    store_name       VARCHAR(128)  NULL COMMENT '门店名称',
    -- column_id: eef41612-8165-4206-8e3e-57f9c397ffb7
    city             VARCHAR(64)   NULL COMMENT '城市',
    -- column_id: 745e340b-bcff-4f04-972d-f024b6d1f976
    store_type       VARCHAR(32)   NULL COMMENT '门店类型',
    -- column_id: 337d120c-ad23-4c04-a290-6cd2bcb206f7
    total_orders     INT           NULL COMMENT '总订单数',
    -- column_id: 991a4e07-fb24-4acc-8bdc-399fa88c56ed
    total_amount     DECIMAL(14,2) NULL COMMENT '总销售额',
    -- column_id: ba6c5cd4-301d-4596-b756-9162a5ee47d8
    customer_count   INT           NULL COMMENT '客户数',
    -- column_id: 390cf2fc-562a-4800-82dc-a2b878808f9b
    avg_order_amount DECIMAL(10,2) NULL COMMENT '客单价',
    -- column_id: 8f57e220-9649-4629-bf37-09e91f508d1b
    performance_score DECIMAL(5,2) NULL COMMENT '绩效评分',
    -- column_id: 5a14e728-ed4d-45a9-adca-625ba32e83bb
    etl_time         DATETIME      NOT NULL COMMENT 'ETL处理时间'
) ENGINE=OLAP
UNIQUE KEY(store_id, stat_month, stat_month_date)
PARTITION BY RANGE(stat_month_date) (
    PARTITION p202406 VALUES LESS THAN ("2024-07-01"),
    PARTITION p202407 VALUES LESS THAN ("2024-08-01"),
    PARTITION p202408 VALUES LESS THAN ("2024-09-01"),
    PARTITION p202409 VALUES LESS THAN ("2024-10-01"),
    PARTITION p202410 VALUES LESS THAN ("2024-11-01"),
    PARTITION p202411 VALUES LESS THAN ("2024-12-01"),
    PARTITION p202412 VALUES LESS THAN ("2025-01-01"),
    PARTITION p202501 VALUES LESS THAN ("2025-02-01")
)
DISTRIBUTED BY HASH(store_id) BUCKETS 1
PROPERTIES (
    "replication_num" = "1"
);
