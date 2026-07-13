-- ODS mirror of Apache Fineract m_fund (机构与员工)
DROP TABLE IF EXISTS retail_banking_dm.ods_fineract_m_fund;
-- table_id: d558e911-b389-40cf-9a66-189f48ef96e8
CREATE TABLE IF NOT EXISTS retail_banking_dm.ods_fineract_m_fund (
    -- column_id: 5db2b734-6d38-4cfc-8d99-2f13f978236b
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: 0d291a1a-8736-4469-b9e2-9607eeaddc93
    `name` VARCHAR(255) NULL COMMENT 'Fineract source column name',
    -- column_id: f72edfca-10c3-450e-8bf4-6ab75ec0e40f
    `external_id` VARCHAR(100) NULL COMMENT 'Fineract source column external_id',
    -- column_id: f57080ec-93f7-4f66-ab73-a198d4554a4a
    `load_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
