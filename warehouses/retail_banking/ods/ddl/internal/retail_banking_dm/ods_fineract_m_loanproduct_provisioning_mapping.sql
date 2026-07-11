-- ODS mirror of Apache Fineract m_loanproduct_provisioning_mapping (贷款与信贷)
DROP TABLE IF EXISTS retail_banking_dm.ods_fineract_m_loanproduct_provisioning_mapping;
-- table_id: 8a138db6-2dc0-44fd-ae44-425dca7cc59f
CREATE TABLE IF NOT EXISTS retail_banking_dm.ods_fineract_m_loanproduct_provisioning_mapping (
    -- column_id: 59945e09-101e-4977-a7da-327b96ec253b
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: 464b3741-9481-48e4-8336-2a6adb0ad6bf
    `product_id` BIGINT NOT NULL COMMENT 'Fineract source column product_id',
    -- column_id: 0e435cbc-c24f-43ad-9154-9d5e830db83b
    `criteria_id` BIGINT NOT NULL COMMENT 'Fineract source column criteria_id',
    -- column_id: 2695a459-1490-4070-a621-0cf7741097fa
    `load_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
