-- DWD generated from m_account_transfer_details
DROP TABLE IF EXISTS retail_banking_dm.dwd_account_transfer_instruction;
-- table_id: dbedfe52-c3f8-46cd-9ee8-353c124c2038
CREATE TABLE IF NOT EXISTS retail_banking_dm.dwd_account_transfer_instruction (
    -- column_id: 7d328605-2811-4495-86fb-8a3c471f95c8
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: 4d7e3c0f-6384-4693-b54a-959f7caab177
    `from_office_id` BIGINT NOT NULL COMMENT 'Fineract source column from_office_id',
    -- column_id: ec3b2d19-f07d-4c09-8b85-be17f2e20b44
    `to_office_id` BIGINT NOT NULL COMMENT 'Fineract source column to_office_id',
    -- column_id: e38c0c80-840b-4880-9b0e-efd79ef21de1
    `from_client_id` BIGINT NULL COMMENT 'Fineract source column from_client_id',
    -- column_id: aab78f7a-658a-46be-9553-924a20ed1a4c
    `to_client_id` BIGINT NULL COMMENT 'Fineract source column to_client_id',
    -- column_id: cb31ea9c-cfa0-494c-9175-d65f59725923
    `from_savings_account_id` BIGINT NULL COMMENT 'Fineract source column from_savings_account_id',
    -- column_id: ea23f805-60dd-4ebb-a79d-373b8dba3982
    `to_savings_account_id` BIGINT NULL COMMENT 'Fineract source column to_savings_account_id',
    -- column_id: dc986c7e-aa96-40e7-9312-32eb3b72d3f0
    `from_loan_account_id` BIGINT NULL COMMENT 'Fineract source column from_loan_account_id',
    -- column_id: 39dddd16-d0cd-4198-87f7-df9bffaf1b39
    `to_loan_account_id` BIGINT NULL COMMENT 'Fineract source column to_loan_account_id',
    -- column_id: 3bf98057-9a56-4a29-b8d7-7efc54ab4b86
    `transfer_type` SMALLINT NULL COMMENT 'Fineract source column transfer_type',
    -- column_id: 5ff5c2e1-98e9-4c5b-8651-fb3f1a2d425a
    `business_date` DATE NULL COMMENT 'Standardized business date from the semantic spec',
    -- column_id: f8221f90-b97c-4483-b2ef-e117299fa8e4
    `etl_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
