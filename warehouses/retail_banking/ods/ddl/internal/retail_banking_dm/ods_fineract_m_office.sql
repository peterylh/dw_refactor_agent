-- ODS mirror of Apache Fineract m_office (机构与员工)
DROP TABLE IF EXISTS retail_banking_dm.ods_fineract_m_office;
-- table_id: 81f63d22-12bf-4f40-8061-fe6b92579bf9
CREATE TABLE IF NOT EXISTS retail_banking_dm.ods_fineract_m_office (
    -- column_id: c3d1ab70-7c8e-460a-842c-3c82c458a539
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: 473952a7-0b68-45c2-9b8e-09fb7d9fa7d2
    `parent_id` BIGINT NULL COMMENT 'Fineract source column parent_id',
    -- column_id: b0e25549-f146-4bfb-b1a1-664230fc207f
    `hierarchy` VARCHAR(100) NULL COMMENT 'Fineract source column hierarchy',
    -- column_id: f1bcb563-119d-4390-a7ba-a6704dcb2743
    `external_id` VARCHAR(100) NULL COMMENT 'Fineract source column external_id',
    -- column_id: bbf04dbc-1182-4fe6-ba82-a7b70aeb75db
    `name` VARCHAR(50) NOT NULL COMMENT 'Fineract source column name',
    -- column_id: 465adada-fba5-473a-9588-66c563b56e3a
    `opening_date` DATE NOT NULL COMMENT 'Fineract source column opening_date',
    -- column_id: 04bfb81b-9b94-4e59-ad24-13abe5f57139
    `load_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
