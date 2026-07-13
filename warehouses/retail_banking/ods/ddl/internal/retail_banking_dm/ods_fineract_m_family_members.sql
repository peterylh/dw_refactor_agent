-- ODS mirror of Apache Fineract m_family_members (客户与参与方)
DROP TABLE IF EXISTS retail_banking_dm.ods_fineract_m_family_members;
-- table_id: 55e89c97-eaa1-4888-b031-5dd4dcfddab8
CREATE TABLE IF NOT EXISTS retail_banking_dm.ods_fineract_m_family_members (
    -- column_id: 74bf14f8-4a55-46df-ab5d-0c531fff0c9f
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: 732cf1af-2e4f-4179-bf14-b3870e52f2e4
    `client_id` BIGINT NOT NULL COMMENT 'Fineract source column client_id',
    -- column_id: fe4a4f9c-94b5-4333-b50d-ef36faa29ecb
    `firstname` VARCHAR(50) NOT NULL COMMENT 'Fineract source column firstname',
    -- column_id: 4ddf4880-5d9f-47dd-8962-f36c7640c1ce
    `middlename` VARCHAR(50) NULL COMMENT 'Fineract source column middlename',
    -- column_id: 3639e9f3-367b-4647-9717-178ee416b5a0
    `lastname` VARCHAR(50) NULL COMMENT 'Fineract source column lastname',
    -- column_id: c840b61b-ce7d-4fd7-8ee0-8c53acdc0ac2
    `qualification` VARCHAR(50) NULL COMMENT 'Fineract source column qualification',
    -- column_id: 8658af08-89bf-4f0d-9621-137e2948af96
    `relationship_cv_id` INT NOT NULL COMMENT 'Fineract source column relationship_cv_id',
    -- column_id: 3a82e4c4-b985-4a68-89a6-19aeeb3a64ad
    `marital_status_cv_id` INT NULL COMMENT 'Fineract source column marital_status_cv_id',
    -- column_id: d21719b6-abc3-40cb-9c1e-3c01955088f9
    `gender_cv_id` INT NULL COMMENT 'Fineract source column gender_cv_id',
    -- column_id: 69694a94-6610-47fe-b77f-feb57d38d12f
    `date_of_birth` DATE NULL COMMENT 'Fineract source column date_of_birth',
    -- column_id: 77d32881-87aa-495c-8f8f-39e7650b7efd
    `age` INT NULL COMMENT 'Fineract source column age',
    -- column_id: 85e47eea-4dd2-4b78-89a4-5e7cb47f6878
    `profession_cv_id` INT NULL COMMENT 'Fineract source column profession_cv_id',
    -- column_id: 0aac2522-11c6-4ea3-9c64-e3373f92fe2e
    `mobile_number` VARCHAR(50) NULL COMMENT 'Fineract source column mobile_number',
    -- column_id: dbf03673-0a98-4377-9f1d-d14fc255dff3
    `is_dependent` BOOLEAN NULL COMMENT 'Fineract source column is_dependent',
    -- column_id: 332370fc-cfac-4e85-9bbe-b4cfd4bf38f9
    `load_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
