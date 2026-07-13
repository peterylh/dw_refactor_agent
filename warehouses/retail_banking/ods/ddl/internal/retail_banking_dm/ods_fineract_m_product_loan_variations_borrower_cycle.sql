-- ODS mirror of Apache Fineract m_product_loan_variations_borrower_cycle (贷款与信贷)
DROP TABLE IF EXISTS retail_banking_dm.ods_fineract_m_product_loan_variations_borrower_cycle;
-- table_id: 502cbc1e-442c-4405-8975-56c49e6e580f
CREATE TABLE IF NOT EXISTS retail_banking_dm.ods_fineract_m_product_loan_variations_borrower_cycle (
    -- column_id: a1eaf54d-113d-4903-b270-f6e8b455e583
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: 4713c3b6-6a7a-42d1-934c-f8b7debd63aa
    `loan_product_id` BIGINT NOT NULL COMMENT 'Fineract source column loan_product_id',
    -- column_id: 99f1a0b3-e8b5-4142-a681-cddf9b407120
    `borrower_cycle_number` INT NOT NULL COMMENT 'Fineract source column borrower_cycle_number',
    -- column_id: ae23d3d2-feef-47d6-8e2b-e80c43601ce3
    `value_condition` INT NOT NULL COMMENT 'Fineract source column value_condition',
    -- column_id: 5563291b-5bed-424a-89f8-f7a41bd469a4
    `param_type` INT NOT NULL COMMENT 'Fineract source column param_type',
    -- column_id: e9c38cf8-e9e6-49cf-a467-3870cfd61239
    `default_value` DECIMAL(19,6) NOT NULL COMMENT 'Fineract source column default_value',
    -- column_id: 7e4b2649-6032-422d-8163-819a5ae74c5d
    `max_value` DECIMAL(19,6) NULL COMMENT 'Fineract source column max_value',
    -- column_id: 9a84ce7f-5d8c-487d-9ad1-36c3889c3d26
    `min_value` DECIMAL(19,6) NULL COMMENT 'Fineract source column min_value',
    -- column_id: 183d4435-e2a4-49f9-a60e-fe5b20acf858
    `load_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
