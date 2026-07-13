-- ODS mirror of Apache Fineract acc_gl_closure (总账与财务)
DROP TABLE IF EXISTS retail_banking_dm.ods_fineract_acc_gl_closure;
-- table_id: 8c1cc7fd-9edc-489f-8a21-82299fc9f1be
CREATE TABLE IF NOT EXISTS retail_banking_dm.ods_fineract_acc_gl_closure (
    -- column_id: 209421ff-1675-4b5e-9ca1-74832b919058
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: b12f03df-7fdc-46e2-b071-2479ab076f55
    `office_id` BIGINT NOT NULL COMMENT 'Fineract source column office_id',
    -- column_id: 98eff24b-a659-4c3a-ac1d-dce3615cb080
    `closing_date` DATE NOT NULL COMMENT 'Fineract source column closing_date',
    -- column_id: 36e7f6c0-b94e-4b2a-b8cb-7507b7f4a6bd
    `is_deleted` BOOLEAN NOT NULL COMMENT 'Fineract source column is_deleted',
    -- column_id: 30c70974-e97d-4981-9af6-2ee398a769af
    `createdby_id` BIGINT NULL COMMENT 'Fineract source column createdby_id',
    -- column_id: 67b90c91-afe3-4d63-8b84-7e28ec35cdb9
    `lastmodifiedby_id` BIGINT NULL COMMENT 'Fineract source column lastmodifiedby_id',
    -- column_id: de0b4d6a-6eeb-40c2-8ed9-79edfd98fe95
    `created_date` DATETIME NULL COMMENT 'Fineract source column created_date',
    -- column_id: f8a997bf-41be-4ec9-9e21-65d05331be8d
    `lastmodified_date` DATETIME NULL COMMENT 'Fineract source column lastmodified_date',
    -- column_id: 0f322152-0067-4644-b648-6da88f9aabf3
    `comments` VARCHAR(500) NULL COMMENT 'Fineract source column comments',
    -- column_id: 56a95d4d-4def-4b62-88eb-18ae4593523a
    `load_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
