-- ODS mirror of Apache Fineract m_code (公共参考与元数据)
DROP TABLE IF EXISTS retail_banking_dm.ods_fineract_m_code;
-- table_id: a7930dc2-080f-4c39-8bd2-f755f955e4cc
CREATE TABLE IF NOT EXISTS retail_banking_dm.ods_fineract_m_code (
    -- column_id: ed92d724-5f46-4ca6-a6ad-fa199b7b6ac0
    `id` INT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: 0467ffde-8693-4e45-9f0d-5679c7171765
    `code_name` VARCHAR(100) NULL COMMENT 'Fineract source column code_name',
    -- column_id: c7d48e6f-0166-4f63-8ab6-5b6b11e5e125
    `is_system_defined` BOOLEAN NOT NULL COMMENT 'Fineract source column is_system_defined',
    -- column_id: ec3d133d-6fcb-4dc6-af4e-e3fe7a8db20b
    `load_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
