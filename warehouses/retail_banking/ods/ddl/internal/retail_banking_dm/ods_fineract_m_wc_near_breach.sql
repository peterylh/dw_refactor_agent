-- ODS mirror of Apache Fineract m_wc_near_breach (营运资金贷款)
DROP TABLE IF EXISTS retail_banking_dm.ods_fineract_m_wc_near_breach;
-- table_id: 230ef339-9950-41e3-b51d-f98493995366
CREATE TABLE IF NOT EXISTS retail_banking_dm.ods_fineract_m_wc_near_breach (
    -- column_id: 52d869c8-997f-4aa2-9f7a-e83c830dbd88
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: fbd1119b-efc2-4e70-869f-de9ac384e65a
    `near_breach_name` VARCHAR(100) NOT NULL COMMENT 'Fineract source column near_breach_name',
    -- column_id: 5c0444b8-4bd4-4a38-90ce-29cf925bee50
    `near_breach_frequency` INT NOT NULL COMMENT 'Fineract source column near_breach_frequency',
    -- column_id: bce7aded-49c3-4178-bb7e-36c58d242af9
    `near_breach_frequency_type` VARCHAR(50) NOT NULL COMMENT 'Fineract source column near_breach_frequency_type',
    -- column_id: 1d2caf04-993f-48b5-a985-c3a128bed197
    `near_breach_threshold` DECIMAL(19,6) NOT NULL COMMENT 'Fineract source column near_breach_threshold',
    -- column_id: 2627b5f9-f7e5-4c71-8724-b9bcbaae17e2
    `load_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
