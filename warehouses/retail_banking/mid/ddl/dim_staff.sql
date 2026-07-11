-- DIM generated from m_staff
DROP TABLE IF EXISTS retail_banking_dm.dim_staff;
-- table_id: fcbfa839-bdc9-4c1f-baab-413e81733121
CREATE TABLE IF NOT EXISTS retail_banking_dm.dim_staff (
    -- column_id: 5b9db173-5005-4a93-8ca4-a7d040becdd7
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: bab47f5c-bfe8-4d13-accd-1a41b09c14aa
    `is_loan_officer` BOOLEAN NOT NULL COMMENT 'Fineract source column is_loan_officer',
    -- column_id: eebcb80d-3e46-4f66-980b-fe320ba421da
    `office_id` BIGINT NULL COMMENT 'Fineract source column office_id',
    -- column_id: 03e997a1-d0af-4086-8fb5-8d4c23e6a4d9
    `firstname` VARCHAR(256) NULL COMMENT 'Fineract source column firstname',
    -- column_id: 1f2e588e-807e-4470-abd4-1e89d4653b98
    `lastname` VARCHAR(256) NULL COMMENT 'Fineract source column lastname',
    -- column_id: 978ece2b-5c6b-4885-aa87-b710a63542dd
    `display_name` VARCHAR(256) NOT NULL COMMENT 'Fineract source column display_name',
    -- column_id: 58e3acf3-5501-4931-a8cd-4531338cd003
    `mobile_no` VARCHAR(64) NULL COMMENT 'Fineract source column mobile_no',
    -- column_id: 08de6a1c-3009-43bc-a592-b580741453bd
    `external_id` VARCHAR(64) NULL COMMENT 'Fineract source column external_id',
    -- column_id: 05bd2847-58a5-4890-b469-22e7fea8a1c8
    `organisational_role_enum` SMALLINT NULL COMMENT 'Fineract source column organisational_role_enum',
    -- column_id: 88335339-3394-49c6-940e-7f65b3fa83a9
    `organisational_role_parent_staff_id` BIGINT NULL COMMENT 'Fineract source column organisational_role_parent_staff_id',
    -- column_id: b88a495d-5ac4-4ec8-867a-7ae7b2728ea1
    `is_active` BOOLEAN NOT NULL COMMENT 'Fineract source column is_active',
    -- column_id: 2617fe87-e8d2-4981-b899-bbd5c04a8f49
    `joining_date` DATE NULL COMMENT 'Fineract source column joining_date',
    -- column_id: b430ef13-0b48-4550-bcec-579da04a092e
    `image_id` BIGINT NULL COMMENT 'Fineract source column image_id',
    -- column_id: 30de7a4e-215a-42bd-bfaa-30c8608036e8
    `email_address` VARCHAR(64) NULL COMMENT 'Fineract source column email_address',
    -- column_id: fc12ac67-93b2-410d-b5f2-be25f8c3069d
    `etl_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
