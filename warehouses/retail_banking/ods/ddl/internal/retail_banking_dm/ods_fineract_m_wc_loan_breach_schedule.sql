-- ODS mirror of Apache Fineract m_wc_loan_breach_schedule (营运资金贷款)
DROP TABLE IF EXISTS retail_banking_dm.ods_fineract_m_wc_loan_breach_schedule;
-- table_id: 2e311393-bbfe-4273-ac2c-7aef751c7187
CREATE TABLE IF NOT EXISTS retail_banking_dm.ods_fineract_m_wc_loan_breach_schedule (
    -- column_id: 1ae94b2d-777b-4d12-966b-17e94b7a1c4c
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: 86675a5b-4949-42b4-aa21-5df10391f750
    `wc_loan_id` BIGINT NOT NULL COMMENT 'Fineract source column wc_loan_id',
    -- column_id: e636ee3f-0efe-4734-8a93-60b3296c2d28
    `period_number` INT NOT NULL COMMENT 'Fineract source column period_number',
    -- column_id: e950d0a4-e24f-4766-94b2-c941f9c6011d
    `from_date` DATE NOT NULL COMMENT 'Fineract source column from_date',
    -- column_id: e58c4703-ebea-4f59-a229-090411453596
    `to_date` DATE NOT NULL COMMENT 'Fineract source column to_date',
    -- column_id: a260874b-552b-456a-b922-f5bd31e42ddb
    `number_of_days` INT NULL COMMENT 'Fineract source column number_of_days',
    -- column_id: 5e03841b-b4ed-4c05-ac2b-c0a276aa72c2
    `min_payment_amount` DECIMAL(19,6) NULL COMMENT 'Fineract source column min_payment_amount',
    -- column_id: 1a04f989-ceda-4398-bebc-9c4025f7bc32
    `paid_amount` DECIMAL(19,6) NULL COMMENT 'Fineract source column paid_amount',
    -- column_id: bc0c45c6-416d-471e-a040-841f8840804c
    `outstanding_amount` DECIMAL(19,6) NULL COMMENT 'Fineract source column outstanding_amount',
    -- column_id: 2cd880ec-aa67-411c-8a46-ba5691075eb9
    `near_breach` BOOLEAN NULL COMMENT 'Fineract source column near_breach',
    -- column_id: 3e69b60d-9fdf-4b81-85d8-e1c606bffc57
    `breach` BOOLEAN NULL COMMENT 'Fineract source column breach',
    -- column_id: cd000562-3bd0-4f08-9c06-eccf37eac3fe
    `created_by` BIGINT NOT NULL COMMENT 'Fineract source column created_by',
    -- column_id: 0f344e9b-9e34-4355-831c-eec09427a0b8
    `last_modified_by` BIGINT NOT NULL COMMENT 'Fineract source column last_modified_by',
    -- column_id: a733dd07-709c-45e8-b75c-677d1917acec
    `created_on_utc` DATETIME NOT NULL COMMENT 'Fineract source column created_on_utc',
    -- column_id: 8334fc5b-f55c-4ace-b07c-8d7663a8ed3d
    `last_modified_on_utc` DATETIME NOT NULL COMMENT 'Fineract source column last_modified_on_utc',
    -- column_id: 9119b90d-c06b-4e0d-86c5-3050dcb960db
    `reset` BOOLEAN NOT NULL COMMENT 'Fineract source column reset',
    -- column_id: 5bc0ceff-e852-418b-a8d1-1f820820afdd
    `load_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
