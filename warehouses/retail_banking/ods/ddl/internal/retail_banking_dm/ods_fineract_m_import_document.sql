-- ODS mirror of Apache Fineract m_import_document (渠道与客户服务)
DROP TABLE IF EXISTS retail_banking_dm.ods_fineract_m_import_document;
-- table_id: 6e702467-c7f2-4945-a61d-2bf48a0f05e3
CREATE TABLE IF NOT EXISTS retail_banking_dm.ods_fineract_m_import_document (
    -- column_id: 192641f0-d57e-479e-8ab8-64c81bd71300
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: 7740baee-25f6-45d6-8f69-6eec7e882630
    `document_id` INT NOT NULL COMMENT 'Fineract source column document_id',
    -- column_id: 0e6b046a-a072-489f-8745-32fb10e9ee66
    `import_time` DATETIME NOT NULL COMMENT 'Fineract source column import_time',
    -- column_id: ec2e626c-fe65-4fed-91ef-b9e00991812a
    `end_time` DATETIME NULL COMMENT 'Fineract source column end_time',
    -- column_id: 9436feaf-9524-4f59-829c-48f593a65be5
    `entity_type` TINYINT NOT NULL COMMENT 'Fineract source column entity_type',
    -- column_id: 3594878c-1d7a-440b-9f5c-87f78749df16
    `completed` BOOLEAN NULL COMMENT 'Fineract source column completed',
    -- column_id: 1f131153-4417-48df-8996-51fa13f9aff2
    `total_records` BIGINT NULL COMMENT 'Fineract source column total_records',
    -- column_id: 53912df2-7c78-4ca3-ab2a-f6f7f596e96d
    `success_count` BIGINT NULL COMMENT 'Fineract source column success_count',
    -- column_id: 48c407ff-03ef-4282-bfd4-00e2894a70dc
    `failure_count` BIGINT NULL COMMENT 'Fineract source column failure_count',
    -- column_id: 9521e071-29d7-4c5f-a552-810dc3cb7cc2
    `createdby_id` BIGINT NULL COMMENT 'Fineract source column createdby_id',
    -- column_id: 772faf06-6638-47f6-bb85-08e41ec52491
    `load_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
