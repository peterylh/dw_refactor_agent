-- ODS mirror of Apache Fineract x_table_column_code_mappings (公共参考与元数据)
DROP TABLE IF EXISTS retail_banking_dm.ods_fineract_x_table_column_code_mappings;
-- table_id: 0774727b-f001-4a7f-b62e-3c28c4c4b047
CREATE TABLE IF NOT EXISTS retail_banking_dm.ods_fineract_x_table_column_code_mappings (
    -- column_id: e5d05353-d507-4284-b53a-f492471cf2d4
    `column_alias_name` VARCHAR(50) NOT NULL COMMENT 'Fineract source column column_alias_name',
    -- column_id: c63c6dd1-be2d-4d26-b4d0-c3f9f2d7c65e
    `code_id` INT NOT NULL COMMENT 'Fineract source column code_id',
    -- column_id: 212e49b8-fba5-461c-b373-12503ea990ff
    `load_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`column_alias_name`)
DISTRIBUTED BY HASH(`column_alias_name`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
