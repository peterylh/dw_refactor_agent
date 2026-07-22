-- Reviewed aggregate from dwd_account_transfer_transaction
DROP TABLE IF EXISTS retail_banking_dm.dws_account_transfer_daily;
-- table_id: b19042f6-8c0a-40fb-9320-7e5b1d4a80ed
CREATE TABLE IF NOT EXISTS retail_banking_dm.dws_account_transfer_daily (
    -- column_id: ea1f1997-529a-4437-b785-4d20dd4b1023
    `stat_date` DATE NOT NULL COMMENT 'event_date',
    -- column_id: 0e161deb-1ab5-45f6-84da-cb0dcb73522d
    `from_office_id` BIGINT NOT NULL COMMENT 'Fineract source column from_office_id',
    -- column_id: a812eee5-8183-45e0-b596-1d9c30e0818b
    `to_office_id` BIGINT NOT NULL COMMENT 'Fineract source column to_office_id',
    -- column_id: 1057aca1-309b-4fdc-8b4a-7a22f5856cca
    `transfer_type` SMALLINT NULL COMMENT 'Fineract source column transfer_type',
    -- column_id: 7dd89d71-4fb7-42a4-9f60-e38cebb7aa55
    `currency_code` VARCHAR(3) NOT NULL COMMENT 'Fineract source column currency_code',
    -- column_id: b8ceafdc-fa4f-45b7-b6d7-f5a119a304ad
    `record_count` BIGINT NOT NULL COMMENT 'derived metric: count(*)',
    -- column_id: 97e61675-26d2-4c4e-88b6-5d5d7565e455
    `total_amount` DECIMAL(38,6) NOT NULL COMMENT 'derived metric: sum(amount)',
    -- column_id: 277a1f48-770b-4b4b-80ef-dd0d9a286c6d
    `etl_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`stat_date`, `from_office_id`, `to_office_id`, `transfer_type`, `currency_code`)
AUTO PARTITION BY LIST (`stat_date`) ()
DISTRIBUTED BY HASH(`stat_date`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
