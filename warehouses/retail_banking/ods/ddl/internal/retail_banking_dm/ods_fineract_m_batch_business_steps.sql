-- ODS mirror of Apache Fineract m_batch_business_steps (其它银行运营)
DROP TABLE IF EXISTS retail_banking_dm.ods_fineract_m_batch_business_steps;
-- table_id: dd4594d8-939b-4321-942e-94e67d3ad30f
CREATE TABLE IF NOT EXISTS retail_banking_dm.ods_fineract_m_batch_business_steps (
    -- column_id: 363fc284-6980-4428-b8be-451f866f4763
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: 4439e668-69c6-4e1f-ba15-5927f6cf7bd3
    `job_name` VARCHAR(100) NOT NULL COMMENT 'Fineract source column job_name',
    -- column_id: 400012de-34cd-4e11-af97-4ebd633d69a1
    `step_name` VARCHAR(100) NOT NULL COMMENT 'Fineract source column step_name',
    -- column_id: 62e8b675-9c1c-4585-aa60-4d955098c83f
    `step_order` SMALLINT NOT NULL COMMENT 'Fineract source column step_order',
    -- column_id: 1105391e-889a-4fe9-8f97-378ebe4384d4
    `load_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
