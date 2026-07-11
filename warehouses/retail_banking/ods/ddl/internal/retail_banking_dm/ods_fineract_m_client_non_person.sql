-- ODS mirror of Apache Fineract m_client_non_person (客户与参与方)
DROP TABLE IF EXISTS retail_banking_dm.ods_fineract_m_client_non_person;
-- table_id: 61fc1480-d903-45a1-8050-33cfa15cb31c
CREATE TABLE IF NOT EXISTS retail_banking_dm.ods_fineract_m_client_non_person (
    -- column_id: be2b3508-ff9f-48a3-916c-3bef88322b55
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: 688e4ed5-c6b5-48c4-b227-613c6e6a569d
    `client_id` BIGINT NOT NULL COMMENT 'Fineract source column client_id',
    -- column_id: 932182da-f285-41d4-9da4-0536f00b43ee
    `constitution_cv_id` INT NOT NULL COMMENT 'Fineract source column constitution_cv_id',
    -- column_id: dfeed965-c3ec-4dff-8e11-0e313c1c2255
    `incorp_no` VARCHAR(50) NULL COMMENT 'Fineract source column incorp_no',
    -- column_id: 7842717e-2aa2-4b6c-ae04-2f9be1b8cfee
    `incorp_validity_till` DATE NULL COMMENT 'Fineract source column incorp_validity_till',
    -- column_id: cc296bcd-5fb9-423b-9bdc-016d47bbfc98
    `main_business_line_cv_id` INT NULL COMMENT 'Fineract source column main_business_line_cv_id',
    -- column_id: c6a60a35-784e-41aa-8a2e-29068a2ffd13
    `remarks` VARCHAR(150) NULL COMMENT 'Fineract source column remarks',
    -- column_id: 5fc542c2-152b-49e3-ba01-40b905470cd5
    `load_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
