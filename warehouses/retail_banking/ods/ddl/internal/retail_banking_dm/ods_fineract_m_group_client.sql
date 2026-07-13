-- ODS mirror of Apache Fineract m_group_client (客户与参与方)
DROP TABLE IF EXISTS retail_banking_dm.ods_fineract_m_group_client;
-- table_id: af287303-001c-4cce-aad3-a2c30340f32e
CREATE TABLE IF NOT EXISTS retail_banking_dm.ods_fineract_m_group_client (
    -- column_id: 05327f7b-dd4c-4d51-91ff-fdcb21b0873f
    `group_id` BIGINT NOT NULL COMMENT 'Fineract source column group_id',
    -- column_id: 735d3c5d-6cb4-48f2-9920-9e09a089312e
    `client_id` BIGINT NOT NULL COMMENT 'Fineract source column client_id',
    -- column_id: 97e314a2-a933-4674-90e6-bad5f2f7194d
    `load_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`group_id`, `client_id`)
DISTRIBUTED BY HASH(`group_id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
