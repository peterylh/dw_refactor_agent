-- DIM generated from m_tellers
DROP TABLE IF EXISTS retail_banking_dm.dim_teller;
-- table_id: e1a643b9-0d17-4cff-8caf-4c35958c8f82
CREATE TABLE IF NOT EXISTS retail_banking_dm.dim_teller (
    -- column_id: 2043224f-4cc1-4d7d-9b2f-eab24ddc0d0a
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: d843136b-7ec7-4f84-b9d9-225f9dcf67a6
    `office_id` BIGINT NOT NULL COMMENT 'Fineract source column office_id',
    -- column_id: 20bd4072-e234-4250-b739-13058cff1ce7
    `debit_account_id` BIGINT NULL COMMENT 'Fineract source column debit_account_id',
    -- column_id: d147062a-a8f0-42e6-9955-7977978702c0
    `credit_account_id` BIGINT NULL COMMENT 'Fineract source column credit_account_id',
    -- column_id: 1bdfd04b-f8c9-48b7-99e6-2b8efc62523f
    `name` VARCHAR(50) NOT NULL COMMENT 'Fineract source column name',
    -- column_id: 0bffb929-7649-43fd-8e5d-5d70428f16fa
    `description` VARCHAR(100) NULL COMMENT 'Fineract source column description',
    -- column_id: 1d24eac5-eac6-4e1a-ad1c-4f0603dd386b
    `valid_from` DATE NULL COMMENT 'Fineract source column valid_from',
    -- column_id: fd2b660c-5e9f-4137-b2e9-b387d8c86ac8
    `valid_to` DATE NULL COMMENT 'Fineract source column valid_to',
    -- column_id: a2d2205d-f4f5-483c-b936-0652487dc72c
    `state` SMALLINT NULL COMMENT 'Fineract source column state',
    -- column_id: 2de78dfa-d38f-45ab-b563-3ef7c3f10fee
    `etl_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
