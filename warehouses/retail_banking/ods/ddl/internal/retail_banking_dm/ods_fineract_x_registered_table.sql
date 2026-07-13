-- ODS mirror of Apache Fineract x_registered_table (其它银行运营)
DROP TABLE IF EXISTS retail_banking_dm.ods_fineract_x_registered_table;
-- table_id: f7af76a6-839b-4279-bf32-aa340c77c8ad
CREATE TABLE IF NOT EXISTS retail_banking_dm.ods_fineract_x_registered_table (
    -- column_id: 2a18e9cb-263a-451b-92b7-32c6e9a1825c
    `registered_table_name` VARCHAR(50) NOT NULL COMMENT 'Fineract source column registered_table_name',
    -- column_id: effa20ba-7a68-4fb4-8b21-3e71a9e292ea
    `application_table_name` VARCHAR(50) NOT NULL COMMENT 'Fineract source column application_table_name',
    -- column_id: bd2d7327-ac66-4ecf-9ae8-e9dd8b27ff81
    `entity_subtype` VARCHAR(50) NULL COMMENT 'Fineract source column entity_subtype',
    -- column_id: 4683ddb6-3148-46cf-96b5-bf0e0e4ae72b
    `category` INT NOT NULL COMMENT 'Fineract source column category',
    -- column_id: 637552e0-27fb-4266-9f4d-d263f7aad911
    `load_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`registered_table_name`)
DISTRIBUTED BY HASH(`registered_table_name`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
