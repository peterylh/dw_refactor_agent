-- ODS mirror of Apache Fineract c_account_number_format (公共参考与元数据)
DROP TABLE IF EXISTS retail_banking_dm.ods_fineract_c_account_number_format;
-- table_id: 9ade747c-c028-454d-b85c-b86f0eab932b
CREATE TABLE IF NOT EXISTS retail_banking_dm.ods_fineract_c_account_number_format (
    -- column_id: 5f1cce05-c713-445a-93e4-ebf0f4031c84
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: 79f54b9b-fbac-4260-a864-205baa2280f2
    `account_type_enum` SMALLINT NOT NULL COMMENT 'Fineract source column account_type_enum',
    -- column_id: d0977354-a20b-465c-9386-f3fc86adf212
    `prefix_type_enum` SMALLINT NULL COMMENT 'Fineract source column prefix_type_enum',
    -- column_id: af1ed524-3143-401b-844e-005567082269
    `prefix_character` VARCHAR(50) NULL COMMENT 'Fineract source column prefix_character',
    -- column_id: 68439dcb-67a4-41f7-9dd7-8e9c21d5455d
    `load_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
