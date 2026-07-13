-- ODS mirror of Apache Fineract m_wc_loan_balance (营运资金贷款)
DROP TABLE IF EXISTS retail_banking_dm.ods_fineract_m_wc_loan_balance;
-- table_id: 45086dd5-5d91-45e1-98bd-fb15125a714c
CREATE TABLE IF NOT EXISTS retail_banking_dm.ods_fineract_m_wc_loan_balance (
    -- column_id: 556aaa18-cb67-40f3-a5c0-e14ce66e5004
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: c0a92393-9add-4dbc-b328-e02029d5c030
    `wc_loan_id` BIGINT NOT NULL COMMENT 'Fineract source column wc_loan_id',
    -- column_id: 54ca977d-87e5-4c50-a0f7-350c087d5ed0
    `principal_paid` DECIMAL(19,6) NOT NULL COMMENT 'Fineract source column principal_paid',
    -- column_id: 2e76ffb9-f92f-4527-87bd-a592924fb1a6
    `realized_income_from_discount_fee` DECIMAL(19,6) NOT NULL COMMENT 'Fineract source column realized_income_from_discount_fee',
    -- column_id: b2caa671-1b73-4c1e-91bc-2e8931975f26
    `version` INT NOT NULL COMMENT 'Fineract source column version',
    -- column_id: 98b9c3f8-9cbd-4540-90ec-c0a8275c609d
    `created_by` BIGINT NOT NULL COMMENT 'Fineract source column created_by',
    -- column_id: f15f5398-a77e-4f82-9240-290714ac4ddd
    `last_modified_by` BIGINT NOT NULL COMMENT 'Fineract source column last_modified_by',
    -- column_id: 7e5c6703-9a57-464b-bae7-d1e0e7d86f3a
    `created_on_utc` DATETIME NOT NULL COMMENT 'Fineract source column created_on_utc',
    -- column_id: c0cdc1e5-692d-49cc-bece-6a99aa10f91d
    `last_modified_on_utc` DATETIME NOT NULL COMMENT 'Fineract source column last_modified_on_utc',
    -- column_id: 5aa7d389-c8e4-4ace-b7ba-222a417fe426
    `overpayment_amount` DECIMAL(19,6) NOT NULL COMMENT 'Fineract source column overpayment_amount',
    -- column_id: 8042a5f1-3c6b-4723-b9a5-e02a35896261
    `principal` DECIMAL(19,6) NOT NULL COMMENT 'Fineract source column principal',
    -- column_id: f0c9d73a-bd53-459c-8df0-41ed4409d60f
    `fee` DECIMAL(19,6) NOT NULL COMMENT 'Fineract source column fee',
    -- column_id: 85858e57-f183-4ca8-86d8-78bb31807298
    `fee_paid` DECIMAL(19,6) NOT NULL COMMENT 'Fineract source column fee_paid',
    -- column_id: bd64062e-052f-4b55-ab24-bf6ee26939aa
    `penalty` DECIMAL(19,6) NOT NULL COMMENT 'Fineract source column penalty',
    -- column_id: 7e6ca290-299b-482b-8992-290cf7eb08dc
    `penalty_paid` DECIMAL(19,6) NOT NULL COMMENT 'Fineract source column penalty_paid',
    -- column_id: 08b25f29-67a5-4e8e-b749-7d778f136947
    `total_disbursement` DECIMAL(19,6) NOT NULL COMMENT 'Fineract source column total_disbursement',
    -- column_id: f6a4cb56-d0fd-402f-9649-b7a127dbf779
    `total_discount_fee` DECIMAL(19,6) NOT NULL COMMENT 'Fineract source column total_discount_fee',
    -- column_id: 7c331ce4-0b1d-4db9-8082-875266a138e9
    `total_discount_fee_adjustment` DECIMAL(19,6) NOT NULL COMMENT 'Fineract source column total_discount_fee_adjustment',
    -- column_id: feff0e4a-14ad-4282-9c8c-91eb7b968b6f
    `load_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
