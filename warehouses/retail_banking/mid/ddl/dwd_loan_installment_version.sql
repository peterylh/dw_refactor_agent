SET allow_partition_column_nullable = true;

-- DWD generated from m_loan_repayment_schedule_history
DROP TABLE IF EXISTS retail_banking_dm.dwd_loan_installment_version;
-- table_id: a8c0336b-bfe7-416d-ba47-34a396b0dea8
CREATE TABLE IF NOT EXISTS retail_banking_dm.dwd_loan_installment_version (
    -- column_id: ab0cdd53-0b47-4416-9f88-cbd94ed26610
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: 359b5a48-a024-4e27-b44d-61aec7705d57
    `business_date` DATE NULL COMMENT 'Standardized business date from the semantic spec',
    -- column_id: af772943-1dc0-42ee-984b-eea95d146788
    `loan_id` BIGINT NOT NULL COMMENT 'Fineract source column loan_id',
    -- column_id: c349fa9e-7d26-4052-997e-6ac7cd9bdb0a
    `loan_reschedule_request_id` BIGINT NULL COMMENT 'Fineract source column loan_reschedule_request_id',
    -- column_id: 81d882c1-229c-4deb-bf12-dac13c999144
    `fromdate` DATE NULL COMMENT 'Fineract source column fromdate',
    -- column_id: 042b1912-bffb-421c-b374-47727d6473a6
    `duedate` DATE NOT NULL COMMENT 'Fineract source column duedate',
    -- column_id: 8ce66e36-491b-414f-a351-194ddee85bed
    `installment` SMALLINT NOT NULL COMMENT 'Fineract source column installment',
    -- column_id: 89f91bc5-b0e7-4f4b-9d67-d42819708e0b
    `principal_amount` DECIMAL(19,6) NULL COMMENT 'Fineract source column principal_amount',
    -- column_id: 38698584-4bd4-4125-8aa5-94dadc2743b6
    `interest_amount` DECIMAL(19,6) NULL COMMENT 'Fineract source column interest_amount',
    -- column_id: 64e783ca-cb4f-49be-9985-9b582825db77
    `fee_charges_amount` DECIMAL(19,6) NULL COMMENT 'Fineract source column fee_charges_amount',
    -- column_id: 145738d1-4b17-417b-849d-5e55e6acae7c
    `penalty_charges_amount` DECIMAL(19,6) NULL COMMENT 'Fineract source column penalty_charges_amount',
    -- column_id: c00ce6a0-d176-4f06-a86d-7af96e1188a8
    `createdby_id` BIGINT NULL COMMENT 'Fineract source column createdby_id',
    -- column_id: 483b17ba-32bd-4b56-8b92-2c1cdaaa33b1
    `created_date` DATETIME NULL COMMENT 'Fineract source column created_date',
    -- column_id: ba28c152-dfbf-44ac-b1f4-fde0fcb78238
    `lastmodified_date` DATETIME NULL COMMENT 'Fineract source column lastmodified_date',
    -- column_id: 9f9cb673-128a-43df-a56c-7322a177ac16
    `lastmodifiedby_id` BIGINT NULL COMMENT 'Fineract source column lastmodifiedby_id',
    -- column_id: 3e4bd2bf-7893-46dc-a305-5ddef2c078dc
    `version` INT NOT NULL COMMENT 'Fineract source column version',
    -- column_id: 048272ee-2c64-4069-a841-d7dd754ff7d3
    `created_on_utc` DATETIME NOT NULL COMMENT 'Fineract source column created_on_utc',
    -- column_id: fe1899e2-bca9-436e-8a46-f97f3c8bc412
    `last_modified_on_utc` DATETIME NOT NULL COMMENT 'Fineract source column last_modified_on_utc',
    -- column_id: a580c023-3af5-4aa9-8c86-1412d626f649
    `etl_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`, `business_date`)
AUTO PARTITION BY LIST (`business_date`) ()
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
