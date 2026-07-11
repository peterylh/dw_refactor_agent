-- DIM generated from m_share_product
DROP TABLE IF EXISTS retail_banking_dm.dim_share_product;
-- table_id: e6ba3e9a-f437-4782-bc67-2875c4a9aa00
CREATE TABLE IF NOT EXISTS retail_banking_dm.dim_share_product (
    -- column_id: a9445939-afba-428a-9e62-29bc7b340041
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: e67e4ff9-abfa-446e-b413-52e59d25e94d
    `name` VARCHAR(200) NOT NULL COMMENT 'Fineract source column name',
    -- column_id: 38629b85-844f-4863-a6af-cb924f3c428e
    `short_name` VARCHAR(4) NOT NULL COMMENT 'Fineract source column short_name',
    -- column_id: e5a41ecf-ee19-45c0-84e8-29c0223429f6
    `external_id` VARCHAR(100) NULL COMMENT 'Fineract source column external_id',
    -- column_id: 7424767e-56bc-4c0a-9c2f-4f1aa94a9c4e
    `description` VARCHAR(500) NOT NULL COMMENT 'Fineract source column description',
    -- column_id: c7167b2e-d60c-4f79-9fa3-58cf7a39792f
    `start_date` DATE NULL COMMENT 'Fineract source column start_date',
    -- column_id: f05d50f4-f111-41b9-87ca-61d5c79174f6
    `end_date` DATE NULL COMMENT 'Fineract source column end_date',
    -- column_id: 2c4b5b83-987b-4eec-8875-646bf2fc8fe1
    `currency_code` VARCHAR(3) NOT NULL COMMENT 'Fineract source column currency_code',
    -- column_id: 1f43e4f5-b5eb-4237-9a8e-3afd04ac5780
    `currency_digits` SMALLINT NOT NULL COMMENT 'Fineract source column currency_digits',
    -- column_id: 0e76fa58-334a-434a-b55b-0240c56dc749
    `currency_multiplesof` SMALLINT NULL COMMENT 'Fineract source column currency_multiplesof',
    -- column_id: 3765a49c-f62e-40d0-8b4f-6a8640434648
    `total_shares` BIGINT NOT NULL COMMENT 'Fineract source column total_shares',
    -- column_id: f3a33f45-6a96-454b-909b-4bc746d7402f
    `issued_shares` BIGINT NULL COMMENT 'Fineract source column issued_shares',
    -- column_id: 2a055117-966e-4198-a619-e94d2f632a97
    `totalsubscribed_shares` BIGINT NULL COMMENT 'Fineract source column totalsubscribed_shares',
    -- column_id: 99ff0a13-95da-414e-a960-6f3f9622b1f6
    `unit_price` DECIMAL(10,2) NOT NULL COMMENT 'Fineract source column unit_price',
    -- column_id: 037439c1-a564-4d32-8849-e82260403a8c
    `capital_amount` DECIMAL(20,2) NOT NULL COMMENT 'Fineract source column capital_amount',
    -- column_id: 20af0549-63d7-4dd7-bb7a-fca43ce6757b
    `minimum_client_shares` BIGINT NULL COMMENT 'Fineract source column minimum_client_shares',
    -- column_id: c1a6fbb0-90e9-48ab-bd22-d5239884aec4
    `nominal_client_shares` BIGINT NOT NULL COMMENT 'Fineract source column nominal_client_shares',
    -- column_id: 3a5b9ce0-5e08-4f46-8be3-b336b52fee81
    `maximum_client_shares` BIGINT NULL COMMENT 'Fineract source column maximum_client_shares',
    -- column_id: 4156d409-0684-44f7-b6a7-a27422e3a98a
    `minimum_active_period_frequency` DECIMAL(19,6) NULL COMMENT 'Fineract source column minimum_active_period_frequency',
    -- column_id: 4cfb0ece-8c7a-4863-90f2-093b0cd3a5f6
    `minimum_active_period_frequency_enum` SMALLINT NULL COMMENT 'Fineract source column minimum_active_period_frequency_enum',
    -- column_id: 6d2d3dff-409f-4433-a9bf-5a8d185897c4
    `lockin_period_frequency` DECIMAL(19,6) NULL COMMENT 'Fineract source column lockin_period_frequency',
    -- column_id: d6c1b37c-9272-4802-bed4-5424d9c46e39
    `lockin_period_frequency_enum` SMALLINT NULL COMMENT 'Fineract source column lockin_period_frequency_enum',
    -- column_id: 0df5413f-c49f-4ad0-8f6e-24e09ab1b4a2
    `allow_dividends_inactive_clients` BOOLEAN NULL COMMENT 'Fineract source column allow_dividends_inactive_clients',
    -- column_id: a89cf309-fb6d-49a2-a7dc-5c184957b45a
    `createdby_id` BIGINT NULL COMMENT 'Fineract source column createdby_id',
    -- column_id: fe468810-2117-42cb-abba-3554e3ebf66e
    `created_date` DATETIME NULL COMMENT 'Fineract source column created_date',
    -- column_id: 57fd0f58-a9c2-4395-8a6b-b766d3a81ec8
    `lastmodifiedby_id` BIGINT NULL COMMENT 'Fineract source column lastmodifiedby_id',
    -- column_id: 9eb03267-dab8-4034-b74a-cc3aece5bf20
    `lastmodified_date` DATETIME NULL COMMENT 'Fineract source column lastmodified_date',
    -- column_id: ac351324-a8a7-4dac-a1c5-98cea3b6d64f
    `accounting_type` SMALLINT NOT NULL COMMENT 'Fineract source column accounting_type',
    -- column_id: 101931fb-a2e6-47f2-9151-41c7d037d1ee
    `etl_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
