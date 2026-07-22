SET allow_partition_column_nullable = true;

-- DWD generated from m_account_transfer_standing_instructions_history
DROP TABLE IF EXISTS retail_banking_dm.dwd_standing_instruction_event;
-- table_id: 8cc54639-133b-4e4f-8264-9a94b57ed94a
CREATE TABLE IF NOT EXISTS retail_banking_dm.dwd_standing_instruction_event (
    -- column_id: 91acb3c1-b2af-4862-a7d3-2b91a5f56df4
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: 204f0898-6987-45ae-97a2-4fa7189d17ea
    `business_date` DATE NULL COMMENT 'Standardized business date from the semantic spec',
    -- column_id: 4be6a657-2fbf-4076-8fbf-f49ff11af453
    `standing_instruction_id` BIGINT NOT NULL COMMENT 'Fineract source column standing_instruction_id',
    -- column_id: 4259de4b-6490-4697-8dfb-d28166219565
    `status` VARCHAR(20) NOT NULL COMMENT 'Fineract source column status',
    -- column_id: b7a5c1e7-ce58-47c0-968d-f324645e59ab
    `execution_time` DATETIME NOT NULL COMMENT 'Fineract source column execution_time',
    -- column_id: 214231b8-a0af-42f3-af9f-55d1d065acf6
    `amount` DECIMAL(19,6) NOT NULL COMMENT 'Fineract source column amount',
    -- column_id: 678f83ea-8b96-4f96-a80a-4c8bc1fa9061
    `error_log` VARCHAR(500) NULL COMMENT 'Fineract source column error_log',
    -- column_id: 014e912b-4edf-4a0b-ae04-dbef12c50b60
    `etl_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`, `business_date`)
AUTO PARTITION BY LIST (`business_date`) ()
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
