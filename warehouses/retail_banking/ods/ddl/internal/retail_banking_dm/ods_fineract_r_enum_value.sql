-- ODS mirror of Apache Fineract r_enum_value (其它银行运营)
DROP TABLE IF EXISTS retail_banking_dm.ods_fineract_r_enum_value;
-- table_id: 4b50c9cf-2826-4ddf-ac8c-029d975a9d78
CREATE TABLE IF NOT EXISTS retail_banking_dm.ods_fineract_r_enum_value (
    -- column_id: e1fde96d-c526-4ad5-8637-8dde38fdd6f8
    `enum_name` VARCHAR(100) NOT NULL COMMENT 'Fineract source column enum_name',
    -- column_id: 09b9b029-d013-47a4-a9a4-c6d5bb9dd679
    `enum_id` INT NOT NULL COMMENT 'Fineract source column enum_id',
    -- column_id: 56023cca-993f-4219-a885-beac65c2dd66
    `enum_message_property` VARCHAR(100) NOT NULL COMMENT 'Fineract source column enum_message_property',
    -- column_id: 016eeb76-9252-4d96-9a46-c030982d4ddc
    `enum_value` VARCHAR(100) NOT NULL COMMENT 'Fineract source column enum_value',
    -- column_id: c8a102fc-9607-4b47-830b-e972dade85c4
    `enum_type` BOOLEAN NOT NULL COMMENT 'Fineract source column enum_type',
    -- column_id: 3ceaf44e-3654-40e2-ae3e-d12c78c75438
    `load_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`enum_name`, `enum_id`)
DISTRIBUTED BY HASH(`enum_name`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
