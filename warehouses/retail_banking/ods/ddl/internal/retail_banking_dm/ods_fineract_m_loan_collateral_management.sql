-- ODS mirror of Apache Fineract m_loan_collateral_management (贷款与信贷)
DROP TABLE IF EXISTS retail_banking_dm.ods_fineract_m_loan_collateral_management;
-- table_id: 9527161a-24df-4b1e-9f62-abe974db1b6a
CREATE TABLE IF NOT EXISTS retail_banking_dm.ods_fineract_m_loan_collateral_management (
    -- column_id: a7a883ce-3fcc-45f1-a0a7-1c9301e102af
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: 0d354a6c-cfeb-4956-9eec-31e42965c39e
    `quantity` DECIMAL(20,5) NOT NULL COMMENT 'Fineract source column quantity',
    -- column_id: 916619c7-bd64-4b46-b5c2-c42ae2a9c33e
    `loan_id` BIGINT NULL COMMENT 'Fineract source column loan_id',
    -- column_id: 39c6f0c8-a23c-4837-bd21-0b4626127caa
    `client_collateral_id` BIGINT NULL COMMENT 'Fineract source column client_collateral_id',
    -- column_id: 2fead713-cfd6-4eb0-b601-9f4546399fad
    `is_released` BOOLEAN NULL COMMENT 'Fineract source column is_released',
    -- column_id: e4186ca8-37b6-4a50-a8af-485049ccb0ff
    `transaction_id` BIGINT NULL COMMENT 'Fineract source column transaction_id',
    -- column_id: 6a2b8960-d27d-40d6-bc8a-02c53e79f5be
    `load_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
