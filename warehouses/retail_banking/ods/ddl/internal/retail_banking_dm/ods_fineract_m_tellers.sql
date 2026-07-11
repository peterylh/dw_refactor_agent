-- ODS mirror of Apache Fineract m_tellers (支付结算)
DROP TABLE IF EXISTS retail_banking_dm.ods_fineract_m_tellers;
-- table_id: 057d8210-08cc-46e9-8270-752832a315ea
CREATE TABLE IF NOT EXISTS retail_banking_dm.ods_fineract_m_tellers (
    -- column_id: ff6c7bbe-a732-423f-8440-fb8f09b7e591
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: de23a053-9c23-4747-8819-7a934d41c83c
    `office_id` BIGINT NOT NULL COMMENT 'Fineract source column office_id',
    -- column_id: c24f60c6-6eb1-4555-95aa-47b54dac7713
    `debit_account_id` BIGINT NULL COMMENT 'Fineract source column debit_account_id',
    -- column_id: 175b02f7-e1e5-48e4-bad2-f7d29febc146
    `credit_account_id` BIGINT NULL COMMENT 'Fineract source column credit_account_id',
    -- column_id: f7f0bbf6-bb43-44c3-9f60-eb0feb71f792
    `name` VARCHAR(50) NOT NULL COMMENT 'Fineract source column name',
    -- column_id: d66271d3-4089-4c98-9808-a84dbf9fdcbf
    `description` VARCHAR(100) NULL COMMENT 'Fineract source column description',
    -- column_id: e1bf1cf0-25c9-4a58-bb98-b8d4a34af419
    `valid_from` DATE NULL COMMENT 'Fineract source column valid_from',
    -- column_id: 3dc3cc00-8d8f-47bd-b14e-1ff31b941ddc
    `valid_to` DATE NULL COMMENT 'Fineract source column valid_to',
    -- column_id: 4c77f435-3e06-422b-9942-368df6e544a2
    `state` SMALLINT NULL COMMENT 'Fineract source column state',
    -- column_id: d367fc62-8fac-4342-bd64-7460ff20ce84
    `load_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
