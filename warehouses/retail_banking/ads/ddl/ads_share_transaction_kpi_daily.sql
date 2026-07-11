-- Reviewed application metrics derived from dws_share_transaction_daily
DROP TABLE IF EXISTS retail_banking_dm.ads_share_transaction_kpi_daily;
-- table_id: 103983fb-b6f5-4d75-aeb3-8cfeaa24e1f4
CREATE TABLE IF NOT EXISTS retail_banking_dm.ads_share_transaction_kpi_daily (
    -- column_id: 6f9c83e1-d3e2-4d9e-9b44-a445d1adbfce
    `stat_date` DATE NOT NULL COMMENT 'event_date',
    -- column_id: af0a4ef1-5293-4789-a006-c5568a4b236f
    `account_id` BIGINT NOT NULL COMMENT 'Fineract source column account_id',
    -- column_id: bc9a87a9-4cc5-49a9-8b73-73936bc1896f
    `type_enum` SMALLINT NULL COMMENT 'Fineract source column type_enum',
    -- column_id: d0ad99f7-e7e9-4cd6-b21b-df1c87ef85fd
    `status_enum` SMALLINT NOT NULL COMMENT 'Fineract source column status_enum',
    -- column_id: 5d56e860-a69e-4540-9920-b37dceac80ed
    `record_count` BIGINT NULL COMMENT 'derived metric: source.record_count',
    -- column_id: 7913c6e7-9363-4046-bae2-24241ca958c7
    `total_shares` DECIMAL(38,6) NULL COMMENT 'derived metric: source.total_shares',
    -- column_id: 0ea107fa-719e-4c60-8d12-78266e277e67
    `total_amount` DECIMAL(38,6) NULL COMMENT 'derived metric: source.total_amount',
    -- column_id: b642e812-83f5-4828-9867-77a882be9e02
    `average_share_price` DECIMAL(38,6) NULL COMMENT 'calculated metric: total_amount / nullif(total_shares, 0)',
    -- column_id: 5d196d04-f9a3-40ed-8c2c-b6c952bc5e5e
    `paid_ratio` DECIMAL(38,6) NULL COMMENT 'calculated metric: total_amount_paid / nullif(total_amount, 0)',
    -- column_id: e4e1d0a0-a1e9-41a0-91d9-2fa0211d1e9d
    `etl_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`stat_date`, `account_id`, `type_enum`, `status_enum`)
DISTRIBUTED BY HASH(`stat_date`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
