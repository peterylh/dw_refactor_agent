-- Reviewed aggregate from dwd_share_transaction
DROP TABLE IF EXISTS retail_banking_dm.dws_share_transaction_daily;
-- table_id: 0a2a5929-3301-407d-a8c8-44a2d7127fd1
CREATE TABLE IF NOT EXISTS retail_banking_dm.dws_share_transaction_daily (
    -- column_id: ac0da505-d883-4fcd-8fb2-ecc256b482ff
    `stat_date` DATE NOT NULL COMMENT 'event_date',
    -- column_id: 7680ceb1-fd59-4ad4-a060-23008a6a1cd5
    `account_id` BIGINT NOT NULL COMMENT 'Fineract source column account_id',
    -- column_id: 17e8f22b-aa94-4b82-bdca-db918a6a1dd1
    `type_enum` SMALLINT NULL COMMENT 'Fineract source column type_enum',
    -- column_id: adb977bb-4c09-4f46-aea5-a4f85a3f4241
    `status_enum` SMALLINT NOT NULL COMMENT 'Fineract source column status_enum',
    -- column_id: 23f0eb8a-a63c-4a2c-8a54-e575236c036e
    `record_count` BIGINT NOT NULL COMMENT 'derived metric: count(*)',
    -- column_id: f057e363-56bf-4498-afdd-e823023f3bbd
    `total_shares` DECIMAL(38,6) NOT NULL COMMENT 'derived metric: sum(total_shares)',
    -- column_id: b2343495-c958-4e7f-97e8-a31f744b72b9
    `total_amount` DECIMAL(38,6) NOT NULL COMMENT 'derived metric: sum(amount)',
    -- column_id: f71bc5d0-fd54-47d0-8864-734fc1766828
    `total_charge_amount` DECIMAL(38,6) NOT NULL COMMENT 'derived metric: sum(charge_amount)',
    -- column_id: e8d0b2ed-a878-47fe-9106-fee69861e267
    `total_amount_paid` DECIMAL(38,6) NOT NULL COMMENT 'derived metric: sum(amount_paid)',
    -- column_id: e4b115a2-9a5a-401b-b186-6798a7b2509a
    `etl_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`stat_date`, `account_id`, `type_enum`, `status_enum`)
AUTO PARTITION BY LIST (`stat_date`) ()
DISTRIBUTED BY HASH(`stat_date`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
