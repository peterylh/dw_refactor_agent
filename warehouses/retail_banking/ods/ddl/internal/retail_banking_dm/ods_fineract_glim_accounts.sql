-- ODS mirror of Apache Fineract glim_accounts (贷款与信贷)
DROP TABLE IF EXISTS retail_banking_dm.ods_fineract_glim_accounts;
-- table_id: 48ce7bf0-89be-49fa-910a-53e032505235
CREATE TABLE IF NOT EXISTS retail_banking_dm.ods_fineract_glim_accounts (
    -- column_id: a13ebb0b-d0ea-4b97-8584-bb6c0c3bd895
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: 564ff9fa-00fb-4f6b-8a98-7ab8277bebcc
    `group_id` BIGINT NOT NULL COMMENT 'Fineract source column group_id',
    -- column_id: 0122e216-edb8-4e04-8af0-bb2efe86bd0d
    `account_number` VARCHAR(50) NOT NULL COMMENT 'Fineract source column account_number',
    -- column_id: fc154b1d-812a-4d8a-9994-bfb9358d7129
    `principal_amount` DECIMAL(19,6) NOT NULL COMMENT 'Fineract source column principal_amount',
    -- column_id: 4e4c4225-8cb2-4adf-94af-678444af5106
    `child_accounts_count` INT NOT NULL COMMENT 'Fineract source column child_accounts_count',
    -- column_id: aa84e0e6-e0a8-4f28-8dbc-e494e5b38097
    `accepting_child` BOOLEAN NOT NULL COMMENT 'Fineract source column accepting_child',
    -- column_id: 76335401-a56c-46f5-9316-50f92a271ffe
    `loan_status_id` SMALLINT NOT NULL COMMENT 'Fineract source column loan_status_id',
    -- column_id: 9d69ee59-3b72-47c6-9e8d-6a53d0b69b04
    `application_id` DECIMAL(10,0) NULL COMMENT 'Fineract source column application_id',
    -- column_id: 18b61c14-9fe6-4a4e-90a4-a12e9c81da93
    `load_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
