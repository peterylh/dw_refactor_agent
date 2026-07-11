-- ODS mirror of Apache Fineract m_portfolio_command_source (平台运营与安全)
DROP TABLE IF EXISTS retail_banking_dm.ods_fineract_m_portfolio_command_source;
-- table_id: 4dafdf8a-eb8e-475e-83b4-e56463bda4e6
CREATE TABLE IF NOT EXISTS retail_banking_dm.ods_fineract_m_portfolio_command_source (
    -- column_id: 9f61dbdc-6da9-4945-b14d-b2496430b88b
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: 58319eb8-9c16-4b0d-83cc-f41f202d1d9d
    `action_name` VARCHAR(50) NOT NULL COMMENT 'Fineract source column action_name',
    -- column_id: c0336b40-05e6-4573-a265-1e173b419584
    `entity_name` VARCHAR(50) NOT NULL COMMENT 'Fineract source column entity_name',
    -- column_id: 98145a61-e0ce-45c5-907b-4318cc20845e
    `office_id` BIGINT NULL COMMENT 'Fineract source column office_id',
    -- column_id: 62b72b21-b871-4fc1-a68f-1485a075e172
    `group_id` BIGINT NULL COMMENT 'Fineract source column group_id',
    -- column_id: 53d08061-cd4f-4cec-88ea-910a2d2f6da5
    `client_id` BIGINT NULL COMMENT 'Fineract source column client_id',
    -- column_id: 2f0e7ab9-1062-4a62-b853-36f6816e7d0e
    `loan_id` BIGINT NULL COMMENT 'Fineract source column loan_id',
    -- column_id: 9e63df94-34e6-406e-b0c9-336809f27da3
    `savings_account_id` BIGINT NULL COMMENT 'Fineract source column savings_account_id',
    -- column_id: da75d87b-f024-41d4-92a3-fb172b7399f9
    `api_get_url` VARCHAR(100) NOT NULL COMMENT 'Fineract source column api_get_url',
    -- column_id: 15726834-5d6c-46a0-b2bf-934f4e3b5876
    `resource_id` BIGINT NULL COMMENT 'Fineract source column resource_id',
    -- column_id: 9e4de5c4-4464-4c67-a8ed-2638df9599cc
    `subresource_id` BIGINT NULL COMMENT 'Fineract source column subresource_id',
    -- column_id: a24f27f7-e5ff-4a01-b1af-7a755ac534b5
    `command_as_json` STRING NOT NULL COMMENT 'Fineract source column command_as_json',
    -- column_id: eb481d78-e284-4091-abdd-fd2500a16f9a
    `maker_id` BIGINT NOT NULL COMMENT 'Fineract source column maker_id',
    -- column_id: 3488ad5a-488c-47c9-abc8-c164b33307f3
    `made_on_date` DATETIME NULL COMMENT 'Fineract source column made_on_date',
    -- column_id: 6a1561d5-dd38-4814-8ac1-fe9e6379d31e
    `checker_id` BIGINT NULL COMMENT 'Fineract source column checker_id',
    -- column_id: fb77b0b8-1c43-40fe-a0a8-ff94b46d75eb
    `checked_on_date` DATETIME NULL COMMENT 'Fineract source column checked_on_date',
    -- column_id: 9ff2b33d-4a89-41ba-b920-408b8046cb78
    `status` SMALLINT NOT NULL COMMENT 'Fineract source column status',
    -- column_id: 87905105-0f3a-4d62-9f96-a83ea1105684
    `product_id` BIGINT NULL COMMENT 'Fineract source column product_id',
    -- column_id: dd4b63a9-16d6-470a-96ab-8d2ad95b57b0
    `transaction_id` VARCHAR(100) NULL COMMENT 'Fineract source column transaction_id',
    -- column_id: 180b6985-24e1-460b-8535-82b47ee7efa8
    `creditbureau_id` BIGINT NULL COMMENT 'Fineract source column creditbureau_id',
    -- column_id: c328bfe4-40c6-4f21-8e49-64ad6b96ab5e
    `organisation_creditbureau_id` BIGINT NULL COMMENT 'Fineract source column organisation_creditbureau_id',
    -- column_id: 1440afee-e1a9-4583-b021-e14ac2c40c1a
    `made_on_date_utc` DATETIME NOT NULL COMMENT 'Fineract source column made_on_date_utc',
    -- column_id: 4fae12bc-39df-4411-8796-b19025e05c8b
    `checked_on_date_utc` DATETIME NULL COMMENT 'Fineract source column checked_on_date_utc',
    -- column_id: 78c7b8d8-2e8f-4a2f-a06d-c61acdd53ff3
    `job_name` VARCHAR(100) NULL COMMENT 'Fineract source column job_name',
    -- column_id: 34620053-d287-4bc6-bffe-56ac37a7c15e
    `idempotency_key` VARCHAR(50) NOT NULL COMMENT 'Fineract source column idempotency_key',
    -- column_id: 0b1bcc5d-f756-4b8d-9fb9-b87f69abc3ec
    `resource_external_id` VARCHAR(100) NULL COMMENT 'Fineract source column resource_external_id',
    -- column_id: 2e89c355-792d-4ae9-893e-89ff4e870d06
    `subresource_external_id` VARCHAR(100) NULL COMMENT 'Fineract source column subresource_external_id',
    -- column_id: 141bc752-7381-4024-8731-4ff7917e8f4b
    `result` STRING NULL COMMENT 'Fineract source column result',
    -- column_id: efecd485-a166-4455-82e5-641d4fd7a7ea
    `result_status_code` INT NULL COMMENT 'Fineract source column result_status_code',
    -- column_id: 97cb744d-9b75-44c6-84ad-862a98e568d3
    `loan_external_id` VARCHAR(100) NULL COMMENT 'Fineract source column loan_external_id',
    -- column_id: feaeb7b0-a841-4a30-b7e9-9554f50adc4d
    `is_sanitized` BOOLEAN NOT NULL COMMENT 'Fineract source column is_sanitized',
    -- column_id: ad19f5c1-681c-42a7-85a9-7baa05fc917d
    `client_ip` VARCHAR(100) NULL COMMENT 'Fineract source column client_ip',
    -- column_id: 58986cad-c388-4064-8827-3afd980a6ce0
    `load_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
