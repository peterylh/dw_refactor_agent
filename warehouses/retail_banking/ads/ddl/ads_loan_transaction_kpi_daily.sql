-- Reviewed application metrics derived from dws_loan_transaction_daily
DROP TABLE IF EXISTS retail_banking_dm.ads_loan_transaction_kpi_daily;
-- table_id: 7e9b5394-1c04-4789-8f13-73e093a9bcb1
CREATE TABLE IF NOT EXISTS retail_banking_dm.ads_loan_transaction_kpi_daily (
    -- column_id: 50c7970d-f2da-41d5-bd3f-4461c5f051c7
    `stat_date` DATE NOT NULL COMMENT 'event_date',
    -- column_id: 32d7d234-676b-4a63-a5cb-b2896874a01b
    `office_id` BIGINT NOT NULL COMMENT 'Fineract source column office_id',
    -- column_id: 5889196c-60fd-4795-bc1c-173a8a0cd5b6
    `loan_id` BIGINT NOT NULL COMMENT 'Fineract source column loan_id',
    -- column_id: b26a52f8-ea6d-4e62-b744-6196d9a2e92c
    `transaction_type_enum` SMALLINT NOT NULL COMMENT 'Fineract source column transaction_type_enum',
    -- column_id: 61b972e0-822c-45f2-848b-2f1932acfe0c
    `record_count` BIGINT NULL COMMENT 'derived metric: source.record_count',
    -- column_id: 933b18d2-326f-4682-a8b8-24b774c78d60
    `total_amount` DECIMAL(38,6) NULL COMMENT 'derived metric: source.total_amount',
    -- column_id: db480fdb-c55e-4f08-b234-54f18682648f
    `average_amount` DECIMAL(38,6) NULL COMMENT 'calculated metric: total_amount / nullif(record_count, 0)',
    -- column_id: a2d456a9-5ab5-4c3f-820a-202cf2884f06
    `principal_component_ratio` DECIMAL(38,6) NULL COMMENT 'calculated metric: total_principal_component / nullif(total_amount, 0)',
    -- column_id: 1f7f2d43-1cef-46fa-83aa-457be33bcca2
    `interest_component_ratio` DECIMAL(38,6) NULL COMMENT 'calculated metric: total_interest_component / nullif(total_amount, 0)',
    -- column_id: 2d6be95b-df16-416e-8dff-77530cbd2352
    `etl_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`stat_date`, `office_id`, `loan_id`, `transaction_type_enum`)
DISTRIBUTED BY HASH(`stat_date`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
