-- ODS mirror of Apache Fineract m_currency (产品、定价与税费)
DROP TABLE IF EXISTS retail_banking_dm.ods_fineract_m_currency;
-- table_id: 07337c9b-4b1f-48f0-ad93-53d8d54a569a
CREATE TABLE IF NOT EXISTS retail_banking_dm.ods_fineract_m_currency (
    -- column_id: b84e0b48-cb9c-424f-9e29-42e37a8e7b57
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: 2bb84370-1216-4b8a-9287-f8c10727682f
    `code` VARCHAR(3) NOT NULL COMMENT 'Fineract source column code',
    -- column_id: 1a33bc90-5b5b-4fb0-8ea6-8b73e0edde68
    `decimal_places` SMALLINT NOT NULL COMMENT 'Fineract source column decimal_places',
    -- column_id: af6ee292-c6da-43a0-b0be-4bd388a98b6d
    `currency_multiplesof` SMALLINT NULL COMMENT 'Fineract source column currency_multiplesof',
    -- column_id: a0645e43-133c-44d3-8ac2-1bbb5ac4f020
    `display_symbol` VARCHAR(10) NULL COMMENT 'Fineract source column display_symbol',
    -- column_id: 2f9e17df-3f46-4854-a678-2bfaf8d1a072
    `name` VARCHAR(50) NOT NULL COMMENT 'Fineract source column name',
    -- column_id: 6fd26a15-892f-4c83-a0e4-bc98f06c7b88
    `internationalized_name_code` VARCHAR(50) NOT NULL COMMENT 'Fineract source column internationalized_name_code',
    -- column_id: 6657deda-6e89-4f13-af14-459d270e56f6
    `load_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
