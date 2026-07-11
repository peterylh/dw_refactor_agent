-- ODS mirror of Apache Fineract m_image (渠道与客户服务)
DROP TABLE IF EXISTS retail_banking_dm.ods_fineract_m_image;
-- table_id: 4ba96e8e-2d39-4b8e-8a1d-cbf5b7180ba5
CREATE TABLE IF NOT EXISTS retail_banking_dm.ods_fineract_m_image (
    -- column_id: e25d59a1-4be6-4e23-992a-19178c2136a1
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: 59776efd-0a62-4b5e-ae11-5eeaa3162838
    `location` VARCHAR(500) NULL COMMENT 'Fineract source column location',
    -- column_id: 6b226635-8bac-4bdd-9724-ec7ad4c5bb69
    `storage_type_enum` SMALLINT NULL COMMENT 'Fineract source column storage_type_enum',
    -- column_id: d1d7639a-7f7e-488b-ab25-c7f90340fcf7
    `load_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
