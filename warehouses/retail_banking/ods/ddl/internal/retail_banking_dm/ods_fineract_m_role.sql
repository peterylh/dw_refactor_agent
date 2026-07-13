-- ODS mirror of Apache Fineract m_role (平台运营与安全)
DROP TABLE IF EXISTS retail_banking_dm.ods_fineract_m_role;
-- table_id: 185ddc50-3641-4c67-976d-2a62cce00c24
CREATE TABLE IF NOT EXISTS retail_banking_dm.ods_fineract_m_role (
    -- column_id: cf470bff-a514-45a8-8357-97f6cafba06f
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: f7ad8b90-0371-4628-8c26-f859ccc67c90
    `name` VARCHAR(100) NOT NULL COMMENT 'Fineract source column name',
    -- column_id: c4b8d3bb-c99f-4b85-8954-ac6881cebca3
    `description` VARCHAR(500) NOT NULL COMMENT 'Fineract source column description',
    -- column_id: dac99097-0eb8-462a-aff6-1c8a8283b4cc
    `is_disabled` BOOLEAN NOT NULL COMMENT 'Fineract source column is_disabled',
    -- column_id: 253bfb08-9d92-4266-b9d3-31bf8660b409
    `load_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
