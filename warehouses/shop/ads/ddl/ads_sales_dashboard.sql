-- ADS 销售驾驶舱汇总表
-- table_id: cd82b3a9-ec2f-4269-8cd0-d4e8d5476a01
DROP TABLE IF EXISTS shop_dm.ads_sales_dashboard;
CREATE TABLE IF NOT EXISTS shop_dm.ads_sales_dashboard (
    -- column_id: b29d9f9f-1504-4522-8931-cb68d1c19a3d
    stat_date          DATE          NOT NULL COMMENT '统计日期',
    -- column_id: 42de9533-b663-4c91-9e9a-67575f140b4d
    total_orders       INT           NULL COMMENT '总订单数',
    -- column_id: c9c3645a-e66d-4e75-a070-6bb4807c6789
    total_customers    INT           NULL COMMENT '总客户数(去重)',
    -- column_id: b0a568ac-bdf9-472f-bc41-b3ba264b66f8
    total_amount       DECIMAL(14,2) NULL COMMENT '总销售额',
    -- column_id: f0a8b613-db1d-4be7-9ebe-837f99901429
    total_discount     DECIMAL(14,2) NULL COMMENT '总折扣金额',
    -- column_id: 88cd7714-3870-4c7d-b233-97c54727ad5b
    avg_order_amount   DECIMAL(10,2) NULL COMMENT '平均客单价',
    -- column_id: 8e2e6db3-09a2-4cf4-8582-5f1745e25d4d
    order_growth_rate  DECIMAL(12,2)  NULL COMMENT '订单环比增长率(%)',
    -- column_id: fa7c5dda-4469-4a3e-a0e3-5c4c2f9d88ad
    amount_growth_rate DECIMAL(12,2)  NULL COMMENT '销售额环比增长率(%)',
    -- column_id: ebd3b721-a923-4c52-9a3c-fb8db95c1a71
    etl_time           DATETIME      NOT NULL COMMENT 'ETL处理时间'
) ENGINE=OLAP
UNIQUE KEY(stat_date)
DISTRIBUTED BY HASH(stat_date) BUCKETS 1
PROPERTIES (
    "replication_num" = "1"
);
