-- ODS mirror of Apache Fineract c_external_service (其它银行运营)
DROP TABLE IF EXISTS retail_banking_dm.ods_fineract_c_external_service;
-- table_id: 3c82f136-d2f2-464a-9686-dfc01f79065d
CREATE TABLE IF NOT EXISTS retail_banking_dm.ods_fineract_c_external_service (
    -- column_id: 3638e754-d7da-47d5-a59b-3625f3d202a7
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: bf3f6bc2-b4fc-48b3-a850-9b43aaec9039
    `name` VARCHAR(100) NULL COMMENT 'Fineract source column name',
    -- column_id: 22186041-b6e8-4491-9c53-cbb223d8073a
    `load_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
