-- ODS mirror of Apache Fineract m_provisioning_criteria (贷款与信贷)
DROP TABLE IF EXISTS retail_banking_dm.ods_fineract_m_provisioning_criteria;
-- table_id: 63cae07c-01ed-46bd-8300-298a4ff80003
CREATE TABLE IF NOT EXISTS retail_banking_dm.ods_fineract_m_provisioning_criteria (
    -- column_id: d5996cfb-29e3-49df-a1b7-fffd961a1a36
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: 80b2bae4-b2b9-4eab-86dd-68812af0bc1c
    `criteria_name` VARCHAR(200) NOT NULL COMMENT 'Fineract source column criteria_name',
    -- column_id: 9442ac01-8f7b-48a9-ad38-bf3267e726d0
    `createdby_id` BIGINT NULL COMMENT 'Fineract source column createdby_id',
    -- column_id: 3078e778-5dbd-4a8c-b8c9-b05748f764a5
    `created_date` DATETIME NULL COMMENT 'Fineract source column created_date',
    -- column_id: 7f2a9497-3913-464a-ac7b-8cf813167878
    `lastmodifiedby_id` BIGINT NULL COMMENT 'Fineract source column lastmodifiedby_id',
    -- column_id: 3a302ad0-15a3-4441-8805-9b1f85395190
    `lastmodified_date` DATETIME NULL COMMENT 'Fineract source column lastmodified_date',
    -- column_id: 35d5edc0-e689-43e4-9d7f-9a6d0541b9de
    `load_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
