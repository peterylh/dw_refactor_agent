-- ODS mirror of Apache Fineract m_product_loan_configurable_attributes (贷款与信贷)
DROP TABLE IF EXISTS retail_banking_dm.ods_fineract_m_product_loan_configurable_attributes;
-- table_id: 267c79b5-b839-4918-af00-c781d68ad959
CREATE TABLE IF NOT EXISTS retail_banking_dm.ods_fineract_m_product_loan_configurable_attributes (
    -- column_id: 77475db7-748f-4b17-9cbd-ef76e8a8ca6f
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: 4211df5e-fc9f-4373-aecb-8be8ba34f6ca
    `loan_product_id` BIGINT NOT NULL COMMENT 'Fineract source column loan_product_id',
    -- column_id: afe47b4c-7179-472c-af1b-1b447922eb53
    `amortization_method_enum` BOOLEAN NOT NULL COMMENT 'Fineract source column amortization_method_enum',
    -- column_id: 7a443809-414e-4ede-8858-36c7ab3ec264
    `interest_method_enum` BOOLEAN NOT NULL COMMENT 'Fineract source column interest_method_enum',
    -- column_id: 2e3867e3-234e-477c-a082-057a34cb9e2c
    `loan_transaction_strategy_code` BOOLEAN NOT NULL COMMENT 'Fineract source column loan_transaction_strategy_code',
    -- column_id: 913812d9-3c03-45e5-9450-35f4f571394b
    `interest_calculated_in_period_enum` BOOLEAN NOT NULL COMMENT 'Fineract source column interest_calculated_in_period_enum',
    -- column_id: 12681a5f-3417-4775-ae1f-9127f42e4209
    `arrearstolerance_amount` BOOLEAN NOT NULL COMMENT 'Fineract source column arrearstolerance_amount',
    -- column_id: a80905f7-ebb3-4955-87ed-046d7b551ff2
    `repay_every` BOOLEAN NOT NULL COMMENT 'Fineract source column repay_every',
    -- column_id: b62584fd-3205-46ec-ae74-5e133fa5822e
    `moratorium` BOOLEAN NOT NULL COMMENT 'Fineract source column moratorium',
    -- column_id: 12f3dd58-cdf6-4f37-8169-d44bab12c7c6
    `grace_on_arrears_ageing` BOOLEAN NOT NULL COMMENT 'Fineract source column grace_on_arrears_ageing',
    -- column_id: fdfa2e69-be61-4495-8c3e-67978435b94d
    `load_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
