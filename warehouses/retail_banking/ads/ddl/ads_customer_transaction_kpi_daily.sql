-- Reviewed application metrics derived from dws_client_transaction_daily
DROP TABLE IF EXISTS retail_banking_dm.ads_customer_transaction_kpi_daily;
-- table_id: 2cf9c7d7-1878-4f8a-908a-191797e28a1a
CREATE TABLE IF NOT EXISTS retail_banking_dm.ads_customer_transaction_kpi_daily (
    -- column_id: 9ed360e7-2b69-448d-939b-ab99f58060e7
    `stat_date` DATE NOT NULL COMMENT 'event_date',
    -- column_id: c7c05736-a799-46b6-aab4-ed548e21958a
    `office_id` BIGINT NOT NULL COMMENT 'Fineract source column office_id',
    -- column_id: eb0ee942-7c4e-4a03-92c2-fd6b87a5502d
    `client_id` BIGINT NOT NULL COMMENT 'Fineract source column client_id',
    -- column_id: 31f523d9-83db-4275-99de-9ad849252056
    `currency_code` VARCHAR(3) NOT NULL COMMENT 'Fineract source column currency_code',
    -- column_id: 5525bfc8-de10-4807-952b-f74eea082bfd
    `transaction_type_enum` SMALLINT NOT NULL COMMENT 'Fineract source column transaction_type_enum',
    -- column_id: 0d20db64-e438-4884-a26f-d8c9f44e5bf0
    `record_count` BIGINT NULL COMMENT 'derived metric: source.record_count',
    -- column_id: da7ce3d3-9181-417f-8988-52c48f4862ba
    `total_amount` DECIMAL(38,6) NULL COMMENT 'derived metric: source.total_amount',
    -- column_id: 4c595f5c-ad09-4dfa-af98-716730117bba
    `average_amount` DECIMAL(38,6) NULL COMMENT 'calculated metric: total_amount / nullif(record_count, 0)',
    -- column_id: 7fdf0e71-e79b-401b-a3d2-f58e51c74c84
    `etl_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`stat_date`, `office_id`, `client_id`, `currency_code`, `transaction_type_enum`)
DISTRIBUTED BY HASH(`stat_date`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
