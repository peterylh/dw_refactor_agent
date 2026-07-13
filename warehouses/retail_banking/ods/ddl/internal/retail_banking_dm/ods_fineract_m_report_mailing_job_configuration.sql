-- ODS mirror of Apache Fineract m_report_mailing_job_configuration (公共参考与元数据)
DROP TABLE IF EXISTS retail_banking_dm.ods_fineract_m_report_mailing_job_configuration;
-- table_id: 1a4d14b3-0e39-4114-94a6-03ab82a73760
CREATE TABLE IF NOT EXISTS retail_banking_dm.ods_fineract_m_report_mailing_job_configuration (
    -- column_id: 7a4f5ba8-be30-4f19-a542-d6839c7f2fbf
    `id` INT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: f23cecf0-ff46-4a83-8737-9ab185e74dfa
    `name` VARCHAR(50) NOT NULL COMMENT 'Fineract source column name',
    -- column_id: 0be49b38-cfed-45a8-bbf2-c7f798914662
    `value` VARCHAR(200) NOT NULL COMMENT 'Fineract source column value',
    -- column_id: adaeea56-c844-4514-a841-c836a69dae17
    `load_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
