-- ODS mirror of Apache Fineract m_loan_repayment_schedule_history (贷款与信贷)
DROP TABLE IF EXISTS retail_banking_dm.ods_fineract_m_loan_repayment_schedule_history;
-- table_id: 1a5013ab-09da-43c4-96ea-53cb9b7b51b2
CREATE TABLE IF NOT EXISTS retail_banking_dm.ods_fineract_m_loan_repayment_schedule_history (
    -- column_id: 4117f50a-44cf-4328-97ec-9df3f14ff47a
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: 6fad7cad-5b3b-4044-8e6c-390377b52256
    `loan_id` BIGINT NOT NULL COMMENT 'Fineract source column loan_id',
    -- column_id: bcaa563c-9c91-4b9c-83f7-ffea38103d28
    `loan_reschedule_request_id` BIGINT NULL COMMENT 'Fineract source column loan_reschedule_request_id',
    -- column_id: 7b5331f0-234b-4701-8e22-8584b9e16d22
    `fromdate` DATE NULL COMMENT 'Fineract source column fromdate',
    -- column_id: c2dd6239-2e08-435d-a6d6-8c2661bc9106
    `duedate` DATE NOT NULL COMMENT 'Fineract source column duedate',
    -- column_id: f9de10d5-31a0-4575-9c33-a667f1909263
    `installment` SMALLINT NOT NULL COMMENT 'Fineract source column installment',
    -- column_id: bfba832b-f090-4c83-af62-6f661f842268
    `principal_amount` DECIMAL(19,6) NULL COMMENT 'Fineract source column principal_amount',
    -- column_id: 03187eac-8547-49f2-a17a-5f12d61e6a9f
    `interest_amount` DECIMAL(19,6) NULL COMMENT 'Fineract source column interest_amount',
    -- column_id: d1530b48-379a-4d0f-94c5-813609dd1e50
    `fee_charges_amount` DECIMAL(19,6) NULL COMMENT 'Fineract source column fee_charges_amount',
    -- column_id: 315cee8a-ad02-4848-b5c6-f632d8199156
    `penalty_charges_amount` DECIMAL(19,6) NULL COMMENT 'Fineract source column penalty_charges_amount',
    -- column_id: 34e4cdd3-93a7-462c-9c44-14dc8f8566f6
    `createdby_id` BIGINT NULL COMMENT 'Fineract source column createdby_id',
    -- column_id: 06e54eeb-7c4c-4e8f-976c-8e9ad63de766
    `created_date` DATETIME NULL COMMENT 'Fineract source column created_date',
    -- column_id: 2ada3139-cc67-46aa-bda8-f5fefb300bf0
    `lastmodified_date` DATETIME NULL COMMENT 'Fineract source column lastmodified_date',
    -- column_id: 2f941f45-c644-4af6-a919-0f88975abcc0
    `lastmodifiedby_id` BIGINT NULL COMMENT 'Fineract source column lastmodifiedby_id',
    -- column_id: 138d4875-3aff-4834-9cfd-8ce1474cae11
    `version` INT NOT NULL COMMENT 'Fineract source column version',
    -- column_id: 2c6e1701-8077-4d1c-9924-706da28ddac1
    `created_on_utc` DATETIME NOT NULL COMMENT 'Fineract source column created_on_utc',
    -- column_id: e8c57684-7241-43bf-b2d9-5d7f20caa30d
    `last_modified_on_utc` DATETIME NOT NULL COMMENT 'Fineract source column last_modified_on_utc',
    -- column_id: 59ce34d5-94a5-4e80-9142-dce8208334f9
    `load_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
