-- ODS mirror of Apache Fineract stretchy_parameter (公共参考与元数据)
DROP TABLE IF EXISTS retail_banking_dm.ods_fineract_stretchy_parameter;
-- table_id: 0ebbc16c-90fc-4e69-9f38-fdf3287f8c7d
CREATE TABLE IF NOT EXISTS retail_banking_dm.ods_fineract_stretchy_parameter (
    -- column_id: e39cec8d-a152-412a-8f65-11d78f305fa2
    `id` INT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: 8a8ac84c-6f70-4508-b0e9-9272b2b3728a
    `parameter_name` VARCHAR(45) NOT NULL COMMENT 'Fineract source column parameter_name',
    -- column_id: 0eb1d3b2-585d-4523-9c27-a5bbbc6be3c6
    `parameter_variable` VARCHAR(45) NULL COMMENT 'Fineract source column parameter_variable',
    -- column_id: 3d4c7312-636f-4ed9-bd01-82e79e6ebb2f
    `parameter_label` VARCHAR(45) NOT NULL COMMENT 'Fineract source column parameter_label',
    -- column_id: cfd5d758-74d8-4aa9-98d7-1df986da872b
    `parameter_displayType` VARCHAR(45) NOT NULL COMMENT 'Fineract source column parameter_displayType',
    -- column_id: db3c1e65-e616-4000-ac5e-e209e7a9cff2
    `parameter_FormatType` VARCHAR(10) NOT NULL COMMENT 'Fineract source column parameter_FormatType',
    -- column_id: 25f3ca2d-1a50-4067-9dae-c954782a0ab8
    `parameter_default` VARCHAR(45) NOT NULL COMMENT 'Fineract source column parameter_default',
    -- column_id: 15007abb-18c7-432c-afa9-96a10c792267
    `special` VARCHAR(1) NULL COMMENT 'Fineract source column special',
    -- column_id: 8495558e-d4ba-4738-b03b-3867641efab8
    `selectOne` VARCHAR(1) NULL COMMENT 'Fineract source column selectOne',
    -- column_id: 4706c5c8-ca5b-4786-b819-796818c0af4a
    `selectAll` VARCHAR(1) NULL COMMENT 'Fineract source column selectAll',
    -- column_id: dd78e148-52ec-4e7b-82de-48984ac13f03
    `parameter_sql` STRING NULL COMMENT 'Fineract source column parameter_sql',
    -- column_id: e5d0c168-9537-4aaa-b1df-d319e0284d0e
    `parent_id` INT NULL COMMENT 'Fineract source column parent_id',
    -- column_id: e14ca01b-0d83-41c7-a560-1c0766fbb63a
    `load_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
