-- ODS mirror of Apache Fineract m_savings_account_transaction_tax_details (存款与储蓄)
DROP TABLE IF EXISTS retail_banking_dm.ods_fineract_m_savings_account_transaction_tax_details;
-- table_id: b9a8f39e-be33-476f-aa08-1eaa5e606e62
CREATE TABLE IF NOT EXISTS retail_banking_dm.ods_fineract_m_savings_account_transaction_tax_details (
    -- column_id: d96f9eb8-fe8d-4c36-b25a-1ae67ab7eecd
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: e9a138ed-2a01-4fc8-bda9-658584c519eb
    `savings_transaction_id` BIGINT NOT NULL COMMENT 'Fineract source column savings_transaction_id',
    -- column_id: c72d4211-a810-4acd-8356-8f1d180fd9d0
    `tax_component_id` BIGINT NOT NULL COMMENT 'Fineract source column tax_component_id',
    -- column_id: ad7d32a3-aaa7-4650-a8da-4bc14e31e7c9
    `amount` DECIMAL(19,6) NOT NULL COMMENT 'Fineract source column amount',
    -- column_id: 829ce1d2-2cc7-4b60-816c-a274aee53868
    `load_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
