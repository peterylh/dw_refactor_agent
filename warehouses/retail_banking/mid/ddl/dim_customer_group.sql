-- DIM generated from m_group
DROP TABLE IF EXISTS retail_banking_dm.dim_customer_group;
-- table_id: b316d65f-2cb5-4d77-917c-1cd37c5ba446
CREATE TABLE IF NOT EXISTS retail_banking_dm.dim_customer_group (
    -- column_id: 26153e3a-17b2-4989-bb08-5b341f202576
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: 18d40f77-f73b-4688-84b4-9ac452978918
    `external_id` VARCHAR(64) NULL COMMENT 'Fineract source column external_id',
    -- column_id: 7a711da8-d8a8-4843-8c4e-d5a89721e207
    `status_enum` INT NOT NULL COMMENT 'Fineract source column status_enum',
    -- column_id: 3b4113f1-7e42-4c46-86d1-ef64529f6fab
    `activation_date` DATE NULL COMMENT 'Fineract source column activation_date',
    -- column_id: f83d08d4-3e1b-4b4c-8360-92692b97a56a
    `office_id` BIGINT NOT NULL COMMENT 'Fineract source column office_id',
    -- column_id: 3dac13e0-ebea-4b24-b2d2-dd4b3ee84af4
    `staff_id` BIGINT NULL COMMENT 'Fineract source column staff_id',
    -- column_id: 90aab2c0-a307-4872-b54e-fa8b4c900556
    `parent_id` BIGINT NULL COMMENT 'Fineract source column parent_id',
    -- column_id: 45cbca9f-ff7c-4467-b511-61daeee1dfac
    `level_id` INT NOT NULL COMMENT 'Fineract source column level_id',
    -- column_id: 2df915d4-dd76-4e9f-a5d1-91977cd4f091
    `display_name` VARCHAR(256) NOT NULL COMMENT 'Fineract source column display_name',
    -- column_id: 89d64cd8-66ab-4e45-b595-b81aeadfa703
    `hierarchy` VARCHAR(100) NULL COMMENT 'Fineract source column hierarchy',
    -- column_id: ab1976ad-fbde-45dc-8ba6-c77c3f5048e5
    `closure_reason_cv_id` INT NULL COMMENT 'Fineract source column closure_reason_cv_id',
    -- column_id: 7fb48415-bf94-4e35-8c57-26b40daa17a3
    `closedon_date` DATE NULL COMMENT 'Fineract source column closedon_date',
    -- column_id: 10fc4ddb-1c15-4e19-a81c-0ea126a5ba80
    `activatedon_userid` BIGINT NULL COMMENT 'Fineract source column activatedon_userid',
    -- column_id: 434a22c0-29f0-498e-9f15-04c62112dbc6
    `submittedon_date` DATE NULL COMMENT 'Fineract source column submittedon_date',
    -- column_id: 983b05a3-4077-4334-b80a-3921f3edb434
    `submittedon_userid` BIGINT NULL COMMENT 'Fineract source column submittedon_userid',
    -- column_id: 39bc0444-011a-40a7-872b-bd326c326fd9
    `closedon_userid` BIGINT NULL COMMENT 'Fineract source column closedon_userid',
    -- column_id: 39c962ce-8c25-4b8a-b14d-4c41bbdca8a3
    `account_no` VARCHAR(64) NOT NULL COMMENT 'Fineract source column account_no',
    -- column_id: d90dfb3d-d8e7-433e-bd79-35b029eb7fb2
    `etl_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
