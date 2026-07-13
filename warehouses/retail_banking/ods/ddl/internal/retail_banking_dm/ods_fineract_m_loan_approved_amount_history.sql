-- ODS mirror of Apache Fineract m_loan_approved_amount_history (贷款与信贷)
DROP TABLE IF EXISTS retail_banking_dm.ods_fineract_m_loan_approved_amount_history;
-- table_id: b723c983-44e5-49a6-b4ca-f55e5e8d499b
CREATE TABLE IF NOT EXISTS retail_banking_dm.ods_fineract_m_loan_approved_amount_history (
    -- column_id: e92f8f6d-24ff-49a5-b78c-229dfa62fdf9
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: e14f2def-a665-454d-be4e-d8f2f9eb5895
    `loan_id` BIGINT NOT NULL COMMENT 'Fineract source column loan_id',
    -- column_id: 6c899cbe-fc59-4de6-9a77-1faa1a6fe7b4
    `new_approved_amount` DECIMAL(19,6) NOT NULL COMMENT 'Fineract source column new_approved_amount',
    -- column_id: 832a0f68-5c7a-49bf-b7fe-1e777290e7ca
    `old_approved_amount` DECIMAL(19,6) NOT NULL COMMENT 'Fineract source column old_approved_amount',
    -- column_id: 4a2682a5-e4d4-4aa7-a04a-8fabbc97caa6
    `created_by` BIGINT NULL COMMENT 'Fineract source column created_by',
    -- column_id: ddd1181d-0ce4-465c-8e57-6fbd56788ca7
    `created_on_utc` DATETIME NULL COMMENT 'Fineract source column created_on_utc',
    -- column_id: 802e9be4-d98f-46ad-ba8c-7f052848cba4
    `last_modified_by` BIGINT NULL COMMENT 'Fineract source column last_modified_by',
    -- column_id: 57806fff-112f-45cf-933e-761b8f5e3d1f
    `last_modified_on_utc` DATETIME NULL COMMENT 'Fineract source column last_modified_on_utc',
    -- column_id: 698e8856-b188-4e86-8426-f391f8d5a6f2
    `load_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
