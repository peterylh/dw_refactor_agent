-- ODS mirror of Apache Fineract stretchy_report_parameter (公共参考与元数据)
DROP TABLE IF EXISTS retail_banking_dm.ods_fineract_stretchy_report_parameter;
-- table_id: 6625a2a4-4108-4f57-8acc-ee79456052dc
CREATE TABLE IF NOT EXISTS retail_banking_dm.ods_fineract_stretchy_report_parameter (
    -- column_id: b2b35f68-0d00-4768-96c9-b0d1a2b75fca
    `id` INT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: 0acaa408-d2bb-464a-b145-ee85e6dced95
    `report_id` INT NOT NULL COMMENT 'Fineract source column report_id',
    -- column_id: 3c408280-2a97-485b-842c-ccda3d8a19bb
    `parameter_id` INT NOT NULL COMMENT 'Fineract source column parameter_id',
    -- column_id: 9c2e32da-484d-4209-a540-8ceaf83058a4
    `report_parameter_name` VARCHAR(45) NULL COMMENT 'Fineract source column report_parameter_name',
    -- column_id: cdc14200-14dd-427f-a30d-f3762cdedabf
    `load_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
