-- ODS mirror of Apache Fineract c_cache (平台运营与安全)
DROP TABLE IF EXISTS retail_banking_dm.ods_fineract_c_cache;
-- table_id: 173a9a73-d035-4d53-86ef-acc856b3ea8c
CREATE TABLE IF NOT EXISTS retail_banking_dm.ods_fineract_c_cache (
    -- column_id: f6091868-582c-4593-a0f1-4cc8302998f4
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: a977dde1-ab32-4ee4-a662-0db0c642eeef
    `cache_type_enum` TINYINT NOT NULL COMMENT 'Fineract source column cache_type_enum',
    -- column_id: e4555fa9-f857-40b5-a883-3810e8cb5308
    `load_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
