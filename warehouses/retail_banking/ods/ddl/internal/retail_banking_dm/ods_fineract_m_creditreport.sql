-- ODS mirror of Apache Fineract m_creditreport (贷款与信贷)
DROP TABLE IF EXISTS retail_banking_dm.ods_fineract_m_creditreport;
-- table_id: e9b831e8-efff-4372-b22c-4849e282e2a9
CREATE TABLE IF NOT EXISTS retail_banking_dm.ods_fineract_m_creditreport (
    -- column_id: de0fd6fa-960f-4041-8c58-7e4841485bb7
    `id` INT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: 18137f9b-12c1-42cf-a26e-3835c22782e4
    `credit_bureau_id` BIGINT NULL COMMENT 'Fineract source column credit_bureau_id',
    -- column_id: 6fc49316-34ed-4411-8a02-31baecfde86b
    `national_id` VARCHAR(128) NULL COMMENT 'Fineract source column national_id',
    -- column_id: 6a97da77-e5cd-4672-809d-94458cc65dd2
    `credit_reports` STRING NULL COMMENT 'Fineract source column credit_reports',
    -- column_id: 2b0486d5-f4cf-43b2-b9cb-765f98c18568
    `load_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
