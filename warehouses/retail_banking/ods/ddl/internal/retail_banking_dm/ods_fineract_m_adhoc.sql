-- ODS mirror of Apache Fineract m_adhoc (其它银行运营)
DROP TABLE IF EXISTS retail_banking_dm.ods_fineract_m_adhoc;
-- table_id: 906af93f-9844-4bd8-8659-c4ab0be7753c
CREATE TABLE IF NOT EXISTS retail_banking_dm.ods_fineract_m_adhoc (
    -- column_id: 652e8e40-4389-4dfb-802a-130de1399b89
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: a7018475-7b13-4293-a18a-a74d0ed33a0f
    `name` VARCHAR(100) NULL COMMENT 'Fineract source column name',
    -- column_id: 85526b77-fb87-4d8c-b800-8c1d46e36f35
    `query` VARCHAR(2000) NULL COMMENT 'Fineract source column query',
    -- column_id: c1dd4808-9491-4451-84ab-a0d1360ba552
    `table_name` VARCHAR(100) NULL COMMENT 'Fineract source column table_name',
    -- column_id: 33b49107-e27a-48e6-95c2-da49175e557a
    `table_fields` VARCHAR(1000) NULL COMMENT 'Fineract source column table_fields',
    -- column_id: 12269dda-44fe-4eba-8f2a-aad7383133f8
    `email` VARCHAR(500) NULL COMMENT 'Fineract source column email',
    -- column_id: b49be4a9-2736-448a-8b65-f59ecb1916c7
    `is_active` BOOLEAN NOT NULL COMMENT 'Fineract source column is_active',
    -- column_id: 07dbc650-b31a-410a-9b88-6249a8f13313
    `created_date` DATETIME NULL COMMENT 'Fineract source column created_date',
    -- column_id: f057f141-ba5e-454d-860b-740ae8899a9a
    `createdby_id` BIGINT NOT NULL COMMENT 'Fineract source column createdby_id',
    -- column_id: 953176b2-ee90-498f-ae34-042d1f5f852c
    `lastmodifiedby_id` BIGINT NOT NULL COMMENT 'Fineract source column lastmodifiedby_id',
    -- column_id: 2c228c1a-c523-4f86-b4c9-b649ca3ced0f
    `lastmodified_date` DATETIME NULL COMMENT 'Fineract source column lastmodified_date',
    -- column_id: 6e5f9d45-15c9-426c-839e-a1afd7f4b010
    `report_run_frequency_code` INT NULL COMMENT 'Fineract source column report_run_frequency_code',
    -- column_id: 7e0580a0-51d8-482c-bcbe-5b1a64913a01
    `report_run_every` INT NULL COMMENT 'Fineract source column report_run_every',
    -- column_id: f02589ed-f322-478b-8332-08e783c62ed4
    `last_run` DATETIME NULL COMMENT 'Fineract source column last_run',
    -- column_id: 869c8cd4-cbb4-437e-934d-20ecd4bbafa0
    `load_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
