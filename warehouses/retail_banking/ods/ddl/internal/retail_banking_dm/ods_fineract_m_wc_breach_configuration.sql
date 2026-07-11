-- ODS mirror of Apache Fineract m_wc_breach_configuration (营运资金贷款)
DROP TABLE IF EXISTS retail_banking_dm.ods_fineract_m_wc_breach_configuration;
-- table_id: 0aab352c-3c22-44d3-bad5-1f803d9f074c
CREATE TABLE IF NOT EXISTS retail_banking_dm.ods_fineract_m_wc_breach_configuration (
    -- column_id: 90c7a38d-f6b0-47dc-aef2-90b14444b179
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: e96d4d4f-af7c-4eff-bc91-e8bd21cd1bc9
    `name` VARCHAR(100) NOT NULL COMMENT 'Fineract source column name',
    -- column_id: d7e64975-a2b5-4fe5-9023-67b4add1c679
    `breach_frequency` INT NULL COMMENT 'Fineract source column breach_frequency',
    -- column_id: 6bebba9e-f944-4e2b-b236-7e8a2d5017da
    `breach_frequency_type` VARCHAR(50) NULL COMMENT 'Fineract source column breach_frequency_type',
    -- column_id: 48976209-bc10-4ddd-84ce-48c38623412e
    `breach_amount_calculation_type` VARCHAR(50) NULL COMMENT 'Fineract source column breach_amount_calculation_type',
    -- column_id: 88e83e86-e574-4b42-9aa5-4a4a1f9bce70
    `breach_amount` DECIMAL(19,6) NULL COMMENT 'Fineract source column breach_amount',
    -- column_id: a02cf3a6-f865-4bd0-b4e8-76ea32ba67c0
    `load_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
