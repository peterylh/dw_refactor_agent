SET allow_partition_column_nullable = true;

-- DWD generated from acc_gl_journal_entry
DROP TABLE IF EXISTS retail_banking_dm.dwd_gl_journal_entry;
-- table_id: 84116e19-2774-46bf-9310-3eeb1b583fa8
CREATE TABLE IF NOT EXISTS retail_banking_dm.dwd_gl_journal_entry (
    -- column_id: 7b877382-972a-4f5d-b7c3-02ae2f569826
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: b42dd8fd-b34d-4fe4-855c-af7a9eab0aaf
    `business_date` DATE NULL COMMENT 'Standardized business date from the semantic spec',
    -- column_id: 44d391a6-a56c-49a9-ac41-6e436f5c557d
    `account_id` BIGINT NOT NULL COMMENT 'Fineract source column account_id',
    -- column_id: 9fcaf2f9-de00-43e3-8f17-75916e2333f2
    `office_id` BIGINT NOT NULL COMMENT 'Fineract source column office_id',
    -- column_id: 7ec25b12-ceb5-4337-86ab-3bd67b8bf162
    `reversal_id` BIGINT NULL COMMENT 'Fineract source column reversal_id',
    -- column_id: 10234c2f-3d70-4a75-b851-2591d795b4df
    `currency_code` VARCHAR(3) NOT NULL COMMENT 'Fineract source column currency_code',
    -- column_id: 05fc7a72-b378-455f-acc2-42191ec6496c
    `transaction_id` VARCHAR(50) NOT NULL COMMENT 'Fineract source column transaction_id',
    -- column_id: e78b43cd-2065-466c-aa65-fef79e6d2a0f
    `loan_transaction_id` BIGINT NULL COMMENT 'Fineract source column loan_transaction_id',
    -- column_id: 4d8bdfa0-8e1b-491c-98b1-538e73aead29
    `savings_transaction_id` BIGINT NULL COMMENT 'Fineract source column savings_transaction_id',
    -- column_id: b9f0233c-19ce-4666-91fe-73d6ba2219da
    `client_transaction_id` BIGINT NULL COMMENT 'Fineract source column client_transaction_id',
    -- column_id: 20de8118-5535-4f26-9ccd-8f11bf660c14
    `reversed` BOOLEAN NOT NULL COMMENT 'Fineract source column reversed',
    -- column_id: 1561ccd6-7a15-4297-9900-bda22a42cd3d
    `ref_num` VARCHAR(100) NULL COMMENT 'Fineract source column ref_num',
    -- column_id: 0acc303f-37da-4dbb-9287-d4d05659b233
    `manual_entry` BOOLEAN NOT NULL COMMENT 'Fineract source column manual_entry',
    -- column_id: 68319105-58df-4efd-8e89-c24feaca7aa4
    `entry_date` DATE NOT NULL COMMENT 'Fineract source column entry_date',
    -- column_id: d7602b1c-0556-4533-96e7-5867f0f5be6c
    `type_enum` SMALLINT NOT NULL COMMENT 'Fineract source column type_enum',
    -- column_id: 5a364d9d-5ff5-42b1-a9b1-bc13d90bc4c4
    `amount` DECIMAL(19,6) NOT NULL COMMENT 'Fineract source column amount',
    -- column_id: 8baa1200-2f24-447f-81fa-4c757e0971a9
    `description` VARCHAR(500) NULL COMMENT 'Fineract source column description',
    -- column_id: 1afa9998-5381-4a1a-81a7-41af86fe98b3
    `entity_type_enum` SMALLINT NULL COMMENT 'Fineract source column entity_type_enum',
    -- column_id: 7e5e7a2d-26dc-4975-97ad-d4c9ef5912aa
    `entity_id` BIGINT NULL COMMENT 'Fineract source column entity_id',
    -- column_id: f0a46062-9e46-4e51-8e1a-c1b93df2d440
    `created_by` BIGINT NOT NULL COMMENT 'Fineract source column created_by',
    -- column_id: 09df282d-b153-4319-a6a6-d0755173d384
    `last_modified_by` BIGINT NOT NULL COMMENT 'Fineract source column last_modified_by',
    -- column_id: cda26149-389e-46ad-83bb-c02dedb76456
    `created_date` DATETIME NULL COMMENT 'Fineract source column created_date',
    -- column_id: 9be82be3-6062-471a-b50b-15e13c875d5c
    `lastmodified_date` DATETIME NULL COMMENT 'Fineract source column lastmodified_date',
    -- column_id: 8b828d95-c413-4a58-9666-86c3089b46ca
    `is_running_balance_calculated` BOOLEAN NOT NULL COMMENT 'Fineract source column is_running_balance_calculated',
    -- column_id: 04312fd2-61d3-4045-9c34-9d737f314196
    `office_running_balance` DECIMAL(19,6) NOT NULL COMMENT 'Fineract source column office_running_balance',
    -- column_id: 62cc2fac-df34-4262-99dd-9c0e65e12176
    `organization_running_balance` DECIMAL(19,6) NOT NULL COMMENT 'Fineract source column organization_running_balance',
    -- column_id: 85ba6973-a655-4a22-bfe2-7dc8b531ce80
    `payment_details_id` BIGINT NULL COMMENT 'Fineract source column payment_details_id',
    -- column_id: c3c24a2c-7b76-4de2-91ae-dad1ab575cdc
    `share_transaction_id` BIGINT NULL COMMENT 'Fineract source column share_transaction_id',
    -- column_id: a06d7168-f018-4b7b-ae60-2afe374c7048
    `transaction_date` DATE NULL COMMENT 'Fineract source column transaction_date',
    -- column_id: 9bec2d3b-99eb-4682-93f3-0a1a686380fa
    `created_on_utc` DATETIME NOT NULL COMMENT 'Fineract source column created_on_utc',
    -- column_id: 6bbbf00b-07c6-4379-8084-a41c951be2e1
    `last_modified_on_utc` DATETIME NOT NULL COMMENT 'Fineract source column last_modified_on_utc',
    -- column_id: 2e6e8fab-24c9-4a83-b01d-4f17f91ccba8
    `submitted_on_date` DATE NOT NULL COMMENT 'Fineract source column submitted_on_date',
    -- column_id: 870085e4-e84e-4d36-b40f-49db69db6521
    `etl_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`, `business_date`)
AUTO PARTITION BY LIST (`business_date`) ()
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
