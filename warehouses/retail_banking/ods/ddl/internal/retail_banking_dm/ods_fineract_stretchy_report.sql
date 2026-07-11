-- ODS mirror of Apache Fineract stretchy_report (公共参考与元数据)
DROP TABLE IF EXISTS retail_banking_dm.ods_fineract_stretchy_report;
-- table_id: efb6f2d6-2c72-4e8d-a5ea-971acb913f36
CREATE TABLE IF NOT EXISTS retail_banking_dm.ods_fineract_stretchy_report (
    -- column_id: db22308c-4263-47b0-8f9e-665ec197e238
    `id` INT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: 25e72c32-5b17-4986-a8a8-9836ca13f058
    `report_name` VARCHAR(100) NOT NULL COMMENT 'Fineract source column report_name',
    -- column_id: bac4cacc-125c-48bd-9534-bb1a7db20e43
    `report_type` VARCHAR(20) NOT NULL COMMENT 'Fineract source column report_type',
    -- column_id: d459b755-679b-4520-a682-8c63772f6955
    `report_subtype` VARCHAR(20) NULL COMMENT 'Fineract source column report_subtype',
    -- column_id: 28c63c3e-efc9-4487-b460-e75d9742ad3e
    `report_category` VARCHAR(45) NULL COMMENT 'Fineract source column report_category',
    -- column_id: c53c4641-70e0-48a7-a5c5-644f7ce7c02b
    `report_sql` STRING NULL COMMENT 'Fineract source column report_sql',
    -- column_id: a7b18cd8-95e1-40f2-aa7a-fd31cbf98630
    `description` STRING NULL COMMENT 'Fineract source column description',
    -- column_id: c670d0ab-bf76-4393-92b0-74c23fa4ff4e
    `core_report` BOOLEAN NULL COMMENT 'Fineract source column core_report',
    -- column_id: c60e280b-3654-45e2-899c-9fd20c17d7c8
    `use_report` BOOLEAN NULL COMMENT 'Fineract source column use_report',
    -- column_id: 0929083b-5362-4336-8b00-962fce1308ea
    `self_service_user_report` BOOLEAN NOT NULL COMMENT 'Fineract source column self_service_user_report',
    -- column_id: 9e802d33-aeda-411b-b90d-a5c0fd5c838c
    `load_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
