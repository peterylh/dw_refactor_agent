-- DWD generated from m_loan_reschedule_request
DROP TABLE IF EXISTS retail_banking_dm.dwd_loan_restructure_event;
-- table_id: 880314a1-ed7d-4573-8930-f86ba2ad8ff6
CREATE TABLE IF NOT EXISTS retail_banking_dm.dwd_loan_restructure_event (
    -- column_id: ab098a34-a012-4d8b-8633-a4f45b0b558f
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: edcd7789-5656-41a3-af89-a95cc85bfe3e
    `loan_id` BIGINT NOT NULL COMMENT 'Fineract source column loan_id',
    -- column_id: b5e2da4a-c7c4-4792-b7f4-c6fd63e61509
    `status_enum` SMALLINT NOT NULL COMMENT 'Fineract source column status_enum',
    -- column_id: 35ee3ab7-3408-4086-acbb-7c7b477a87c0
    `reschedule_from_installment` SMALLINT NOT NULL COMMENT 'Rescheduling will start from this installment',
    -- column_id: c6e39388-59ff-4899-a02f-5b4247a32062
    `reschedule_from_date` DATE NOT NULL COMMENT 'Rescheduling will start from the installment with due date similar to this date.',
    -- column_id: 7be1db6e-ba7f-4337-85d2-f92d6b26c5c0
    `recalculate_interest` BOOLEAN NULL COMMENT 'If set to 1, interest will be recalculated starting from the reschedule period.',
    -- column_id: 7ea34edf-538e-4047-98ec-79a40a636253
    `reschedule_reason_cv_id` INT NULL COMMENT 'ID of code value of reason for rescheduling',
    -- column_id: 67bb9ac6-4a10-49b1-b3e4-b0e80b4795fa
    `reschedule_reason_comment` VARCHAR(256) NULL COMMENT 'Text provided in addition to the reason code value',
    -- column_id: d9ca1959-1d9e-4dc7-a194-d0c1321a3b71
    `submitted_on_date` DATE NOT NULL COMMENT 'Fineract source column submitted_on_date',
    -- column_id: 7d4ecc73-201d-461e-9c28-190ebaf47d2e
    `submitted_by_user_id` BIGINT NOT NULL COMMENT 'Fineract source column submitted_by_user_id',
    -- column_id: 323e359e-8968-4736-83ef-e38af0cb2156
    `approved_on_date` DATE NULL COMMENT 'Fineract source column approved_on_date',
    -- column_id: c55b5267-4d9e-471f-8944-b962033248ff
    `approved_by_user_id` BIGINT NULL COMMENT 'Fineract source column approved_by_user_id',
    -- column_id: 517943c6-9b80-4eef-8c29-5bd8fab9bae3
    `rejected_on_date` DATE NULL COMMENT 'Fineract source column rejected_on_date',
    -- column_id: 5b4e3bc0-60d3-43da-90b7-1b6c807ceda5
    `rejected_by_user_id` BIGINT NULL COMMENT 'Fineract source column rejected_by_user_id',
    -- column_id: a53f4c44-5727-452f-b2c4-5f3dc8ef1194
    `business_date` DATE NULL COMMENT 'Standardized business date from the semantic spec',
    -- column_id: 86034a7c-28f0-40a3-9988-9804034a4b61
    `etl_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
