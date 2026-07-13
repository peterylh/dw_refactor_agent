-- ODS mirror of Apache Fineract acc_gl_journal_entry (总账与财务)
DROP TABLE IF EXISTS retail_banking_dm.ods_fineract_acc_gl_journal_entry;
-- table_id: 005c23b3-12dd-46ee-b357-528afd6799ae
CREATE TABLE IF NOT EXISTS retail_banking_dm.ods_fineract_acc_gl_journal_entry (
    -- column_id: c6b11391-c2fd-4ccf-94c3-bf11b415893a
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: b08345b7-3f00-4944-93c8-50132b8eb147
    `account_id` BIGINT NOT NULL COMMENT 'Fineract source column account_id',
    -- column_id: 2b303ef0-d15e-4a8b-b8a5-d837808d30ce
    `office_id` BIGINT NOT NULL COMMENT 'Fineract source column office_id',
    -- column_id: 2742c0b4-7d0d-4b4f-b940-ad6062f1cbec
    `reversal_id` BIGINT NULL COMMENT 'Fineract source column reversal_id',
    -- column_id: 375e9409-9579-4717-a82f-d31903d9aef9
    `currency_code` VARCHAR(3) NOT NULL COMMENT 'Fineract source column currency_code',
    -- column_id: cf8fa880-525f-453e-a903-66c862fa0728
    `transaction_id` VARCHAR(50) NOT NULL COMMENT 'Fineract source column transaction_id',
    -- column_id: 0e38ac41-a5ad-4d97-a2c7-a5baf6a326a3
    `loan_transaction_id` BIGINT NULL COMMENT 'Fineract source column loan_transaction_id',
    -- column_id: f68cac14-098e-407f-b3c6-e782a01d192f
    `savings_transaction_id` BIGINT NULL COMMENT 'Fineract source column savings_transaction_id',
    -- column_id: 60c0750c-2a53-4967-bfa5-fa39773c7c3a
    `client_transaction_id` BIGINT NULL COMMENT 'Fineract source column client_transaction_id',
    -- column_id: ea8703cb-862e-4b9b-91d8-fa137b5d578b
    `reversed` BOOLEAN NOT NULL COMMENT 'Fineract source column reversed',
    -- column_id: f095d613-b36e-4e9e-b9ab-a1adf3b3c43f
    `ref_num` VARCHAR(100) NULL COMMENT 'Fineract source column ref_num',
    -- column_id: db04b055-3ec9-4f20-ac59-ea5776e6347c
    `manual_entry` BOOLEAN NOT NULL COMMENT 'Fineract source column manual_entry',
    -- column_id: 5b656174-f050-4958-bf53-5e4ff4f13ffb
    `entry_date` DATE NOT NULL COMMENT 'Fineract source column entry_date',
    -- column_id: 30721583-cd0f-4162-b362-1e9186d67786
    `type_enum` SMALLINT NOT NULL COMMENT 'Fineract source column type_enum',
    -- column_id: 621443df-7e12-4b03-897e-fb5f506bc985
    `amount` DECIMAL(19,6) NOT NULL COMMENT 'Fineract source column amount',
    -- column_id: 7f2d8990-6f3c-417e-b209-ae04968fbeda
    `description` VARCHAR(500) NULL COMMENT 'Fineract source column description',
    -- column_id: bc7e4e64-5e49-4716-99af-49a1932be5f4
    `entity_type_enum` SMALLINT NULL COMMENT 'Fineract source column entity_type_enum',
    -- column_id: 2fda1868-75d3-47df-8ba4-abdb8de5cafb
    `entity_id` BIGINT NULL COMMENT 'Fineract source column entity_id',
    -- column_id: ebfd1033-4884-4908-b9a1-3e75eab2a777
    `created_by` BIGINT NOT NULL COMMENT 'Fineract source column created_by',
    -- column_id: 537c3e32-37e9-4b84-b590-56c2cfd29f37
    `last_modified_by` BIGINT NOT NULL COMMENT 'Fineract source column last_modified_by',
    -- column_id: f6684cf7-ea3f-49c7-a619-c4756427b4d9
    `created_date` DATETIME NULL COMMENT 'Fineract source column created_date',
    -- column_id: c30bb615-67cb-49ac-b8bb-172db667e680
    `lastmodified_date` DATETIME NULL COMMENT 'Fineract source column lastmodified_date',
    -- column_id: a4ebeec0-e4bf-45d0-a761-85cdf842b4f4
    `is_running_balance_calculated` BOOLEAN NOT NULL COMMENT 'Fineract source column is_running_balance_calculated',
    -- column_id: f5159c24-3447-4f3b-a675-b286a85e9b73
    `office_running_balance` DECIMAL(19,6) NOT NULL COMMENT 'Fineract source column office_running_balance',
    -- column_id: f8e9aef1-d0d7-4d49-a538-20b8855ce0e6
    `organization_running_balance` DECIMAL(19,6) NOT NULL COMMENT 'Fineract source column organization_running_balance',
    -- column_id: 0908fd4f-740d-45d9-912e-887557013de6
    `payment_details_id` BIGINT NULL COMMENT 'Fineract source column payment_details_id',
    -- column_id: 405baf0a-7f3d-4461-963f-c8a5071f3249
    `share_transaction_id` BIGINT NULL COMMENT 'Fineract source column share_transaction_id',
    -- column_id: 25c197e2-54a5-4601-9ce9-e96c826c9c65
    `transaction_date` DATE NULL COMMENT 'Fineract source column transaction_date',
    -- column_id: 3edf373b-4e13-407b-a1f9-69c8588463a3
    `created_on_utc` DATETIME NOT NULL COMMENT 'Fineract source column created_on_utc',
    -- column_id: e009158f-fa3b-402a-8c4c-d24b04fa7f7e
    `last_modified_on_utc` DATETIME NOT NULL COMMENT 'Fineract source column last_modified_on_utc',
    -- column_id: 46a562f9-cc82-4da0-b657-453d7f55dff1
    `submitted_on_date` DATE NOT NULL COMMENT 'Fineract source column submitted_on_date',
    -- column_id: ba218250-0e96-471a-aed7-75fb31ee8bc7
    `load_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
