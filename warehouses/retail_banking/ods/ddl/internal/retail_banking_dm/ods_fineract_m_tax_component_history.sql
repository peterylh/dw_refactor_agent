-- ODS mirror of Apache Fineract m_tax_component_history (产品、定价与税费)
DROP TABLE IF EXISTS retail_banking_dm.ods_fineract_m_tax_component_history;
-- table_id: c05d8ae6-6cc4-4d17-8a64-96cae32878db
CREATE TABLE IF NOT EXISTS retail_banking_dm.ods_fineract_m_tax_component_history (
    -- column_id: 4f2c186d-b6f5-4192-94da-9a69ffeda27f
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: 088cd482-db17-43dd-86c2-e0ca7ab7425e
    `tax_component_id` BIGINT NOT NULL COMMENT 'Fineract source column tax_component_id',
    -- column_id: f0e58628-0e5f-4c1d-9aec-2544a8bb06c2
    `percentage` DECIMAL(19,6) NOT NULL COMMENT 'Fineract source column percentage',
    -- column_id: 378862e0-c67a-4ce8-932f-04f1272797c7
    `start_date` DATE NOT NULL COMMENT 'Fineract source column start_date',
    -- column_id: c2f20d62-e460-4047-88f9-78d9a0ce4205
    `end_date` DATE NOT NULL COMMENT 'Fineract source column end_date',
    -- column_id: 953cbb7b-e2e4-472f-a9e8-b409d02ecda9
    `createdby_id` BIGINT NOT NULL COMMENT 'Fineract source column createdby_id',
    -- column_id: 94e9b497-2033-4c74-8c7b-8248f69adbb6
    `created_date` DATETIME NOT NULL COMMENT 'Fineract source column created_date',
    -- column_id: 4481db05-d271-48cc-af55-317dda7ffe65
    `lastmodifiedby_id` BIGINT NOT NULL COMMENT 'Fineract source column lastmodifiedby_id',
    -- column_id: 1a6218af-a30e-4744-a306-cf306a76a8a1
    `lastmodified_date` DATETIME NOT NULL COMMENT 'Fineract source column lastmodified_date',
    -- column_id: fe2d8cbd-d003-450f-9e88-4549dc230371
    `load_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
