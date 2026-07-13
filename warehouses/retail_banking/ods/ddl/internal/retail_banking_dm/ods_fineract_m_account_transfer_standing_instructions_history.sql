-- ODS mirror of Apache Fineract m_account_transfer_standing_instructions_history (支付结算)
DROP TABLE IF EXISTS retail_banking_dm.ods_fineract_m_account_transfer_standing_instructions_history;
-- table_id: 11864878-488d-4801-8bd0-2e4019d4cf01
CREATE TABLE IF NOT EXISTS retail_banking_dm.ods_fineract_m_account_transfer_standing_instructions_history (
    -- column_id: 5820a854-c97b-4c15-bf79-857ed3f98ef9
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: a4ef1367-d259-41f0-8ced-2aa6ec3c183c
    `standing_instruction_id` BIGINT NOT NULL COMMENT 'Fineract source column standing_instruction_id',
    -- column_id: 3cdecf24-5519-42ab-924e-5e4778916bf0
    `status` VARCHAR(20) NOT NULL COMMENT 'Fineract source column status',
    -- column_id: 08c1b4a4-5e6d-4b99-9d2e-2540978e4a44
    `execution_time` DATETIME NOT NULL COMMENT 'Fineract source column execution_time',
    -- column_id: a6e97d58-7164-46da-b602-a4cbb3c8be85
    `amount` DECIMAL(19,6) NOT NULL COMMENT 'Fineract source column amount',
    -- column_id: 7f4587a9-ed4a-44b0-8d66-7938c50a23b9
    `error_log` VARCHAR(500) NULL COMMENT 'Fineract source column error_log',
    -- column_id: f4cb2fe5-595c-4c31-8b4c-e0a0944103f1
    `load_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
