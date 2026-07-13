-- ODS mirror of Apache Fineract m_staff (机构与员工)
DROP TABLE IF EXISTS retail_banking_dm.ods_fineract_m_staff;
-- table_id: 236ef62f-631b-4c9d-80e6-9f9a983c966e
CREATE TABLE IF NOT EXISTS retail_banking_dm.ods_fineract_m_staff (
    -- column_id: fc6e0b15-2dbf-42a3-afb9-786b6a9e4701
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: 7fc866ba-bf89-44a9-ad1d-09e36bc2bd1a
    `is_loan_officer` BOOLEAN NOT NULL COMMENT 'Fineract source column is_loan_officer',
    -- column_id: 4e02f0d3-205d-4ac6-ac04-64c647c6896c
    `office_id` BIGINT NULL COMMENT 'Fineract source column office_id',
    -- column_id: b23b0e70-91d8-4081-af5b-691b8f199be3
    `firstname` VARCHAR(50) NULL COMMENT 'Fineract source column firstname',
    -- column_id: 9bad958b-8e7e-4906-b573-4860e1895c7d
    `lastname` VARCHAR(50) NULL COMMENT 'Fineract source column lastname',
    -- column_id: affceb7b-800a-4f46-8ebb-d62f20e8ca06
    `display_name` VARCHAR(102) NOT NULL COMMENT 'Fineract source column display_name',
    -- column_id: 99e250a4-2968-4d97-ae95-60ebb161d210
    `mobile_no` VARCHAR(50) NULL COMMENT 'Fineract source column mobile_no',
    -- column_id: 9f1c1bd8-b8e8-4243-a825-8ed52ae41a25
    `external_id` VARCHAR(100) NULL COMMENT 'Fineract source column external_id',
    -- column_id: f7abc4b8-ded0-475c-9b8b-60fdd77f6afa
    `organisational_role_enum` SMALLINT NULL COMMENT 'Fineract source column organisational_role_enum',
    -- column_id: 04594299-d38d-4871-9f9d-57785a2282ec
    `organisational_role_parent_staff_id` BIGINT NULL COMMENT 'Fineract source column organisational_role_parent_staff_id',
    -- column_id: 9ce41773-017d-42c4-b684-50c63b7036cb
    `is_active` BOOLEAN NOT NULL COMMENT 'Fineract source column is_active',
    -- column_id: 41d6e618-6387-4302-b6fe-fb58d5b8342f
    `joining_date` DATE NULL COMMENT 'Fineract source column joining_date',
    -- column_id: d34a4ee6-b065-4b97-84de-e175f570b996
    `image_id` BIGINT NULL COMMENT 'Fineract source column image_id',
    -- column_id: a47f2b0a-c69e-4c7c-b0c4-16e2bbddc1d0
    `email_address` VARCHAR(150) NULL COMMENT 'Fineract source column email_address',
    -- column_id: dc4c4aab-5e9e-463f-9d9d-49a4582acbf6
    `load_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
