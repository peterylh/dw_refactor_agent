-- Reviewed application metrics derived from dws_deposit_transaction_daily
DROP TABLE IF EXISTS retail_banking_dm.ads_deposit_transaction_kpi_daily;
-- table_id: b01d9d92-f0ff-4b01-9dad-638330e32cbd
CREATE TABLE IF NOT EXISTS retail_banking_dm.ads_deposit_transaction_kpi_daily (
    -- column_id: 53a0dd7f-0fda-40a6-bbca-8481d7ab5cd3
    `stat_date` DATE NOT NULL COMMENT 'event_date',
    -- column_id: 4071bb35-98eb-4e3b-8762-d2ac3d7dcf81
    `office_id` BIGINT NOT NULL COMMENT 'Fineract source column office_id',
    -- column_id: 626cc36e-1212-41c8-93ea-572e0c756762
    `savings_account_id` BIGINT NOT NULL COMMENT 'Fineract source column savings_account_id',
    -- column_id: bb444446-0744-4e48-901c-e2eec8e81bb7
    `transaction_type_enum` SMALLINT NOT NULL COMMENT 'Fineract source column transaction_type_enum',
    -- column_id: 14362ead-ed9e-45d2-ad0a-371de4ce433d
    `record_count` BIGINT NULL COMMENT 'derived metric: source.record_count',
    -- column_id: c9dc1d73-558c-4008-a1f5-1c5302677b74
    `total_amount` DECIMAL(38,6) NULL COMMENT 'derived metric: source.total_amount',
    -- column_id: 4d24f21c-c10c-4a01-a5cd-58a5cd73408d
    `total_overdraft_amount` DECIMAL(38,6) NULL COMMENT 'derived metric: source.total_overdraft_amount',
    -- column_id: 7b2268c5-0fe3-46b5-9902-3074ac6f8387
    `average_amount` DECIMAL(38,6) NULL COMMENT 'calculated metric: total_amount / nullif(record_count, 0)',
    -- column_id: 0260c8c8-3284-4036-9e25-8b2b545947db
    `overdraft_amount_ratio` DECIMAL(38,6) NULL COMMENT 'calculated metric: total_overdraft_amount / nullif(total_amount, 0)',
    -- column_id: a7d569fc-5741-42a9-99f0-a7a760ec05eb
    `etl_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`stat_date`, `office_id`, `savings_account_id`, `transaction_type_enum`)
DISTRIBUTED BY HASH(`stat_date`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
