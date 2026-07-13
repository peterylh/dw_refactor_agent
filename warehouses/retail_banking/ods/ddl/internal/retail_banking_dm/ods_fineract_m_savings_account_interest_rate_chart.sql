-- ODS mirror of Apache Fineract m_savings_account_interest_rate_chart (存款与储蓄)
DROP TABLE IF EXISTS retail_banking_dm.ods_fineract_m_savings_account_interest_rate_chart;
-- table_id: 286653ca-ecb8-49c8-918b-7125286644ea
CREATE TABLE IF NOT EXISTS retail_banking_dm.ods_fineract_m_savings_account_interest_rate_chart (
    -- column_id: f10a21f8-c816-47a4-8207-b9a00be0c8bf
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: 7e2c3f10-2c3c-43ff-9e20-0581d06888fa
    `savings_account_id` BIGINT NOT NULL COMMENT 'Fineract source column savings_account_id',
    -- column_id: 0b654fef-107f-4ca2-b714-7ec2747c4768
    `name` VARCHAR(100) NULL COMMENT 'Fineract source column name',
    -- column_id: 51e763cf-2aad-4727-9052-1618d9b7fb9b
    `description` VARCHAR(200) NULL COMMENT 'Fineract source column description',
    -- column_id: 4684a708-7426-46c7-8ad8-4334b8e9c056
    `from_date` DATE NOT NULL COMMENT 'Fineract source column from_date',
    -- column_id: f6c4a38e-d99a-4123-91f5-18af7bd16b95
    `end_date` DATE NULL COMMENT 'Fineract source column end_date',
    -- column_id: afab851d-47f6-488e-b600-99b435110ecc
    `is_primary_grouping_by_amount` BOOLEAN NOT NULL COMMENT 'Fineract source column is_primary_grouping_by_amount',
    -- column_id: 01e3ec9e-59dc-4fb7-afc2-5af7095b14d1
    `load_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
