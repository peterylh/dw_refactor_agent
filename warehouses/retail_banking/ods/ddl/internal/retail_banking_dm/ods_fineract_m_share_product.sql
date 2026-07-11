-- ODS mirror of Apache Fineract m_share_product (投资、份额与资产持有)
DROP TABLE IF EXISTS retail_banking_dm.ods_fineract_m_share_product;
-- table_id: 749fe0a9-0330-4034-9355-3d0e76aa0eef
CREATE TABLE IF NOT EXISTS retail_banking_dm.ods_fineract_m_share_product (
    -- column_id: 72ed9e66-8b12-448f-a36e-c228506e4efe
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: 8a9475d8-fdd8-417c-a3b1-243db4f520e5
    `name` VARCHAR(200) NOT NULL COMMENT 'Fineract source column name',
    -- column_id: 773a2598-24ea-4284-b7f7-428e9a97288f
    `short_name` VARCHAR(4) NOT NULL COMMENT 'Fineract source column short_name',
    -- column_id: 293ee595-905d-445e-af4e-f6333c582f63
    `external_id` VARCHAR(100) NULL COMMENT 'Fineract source column external_id',
    -- column_id: 5919ada1-cce2-40ae-b683-b379e0b5fabe
    `description` VARCHAR(500) NOT NULL COMMENT 'Fineract source column description',
    -- column_id: 32b58b46-1c9f-48ec-8225-533b22121073
    `start_date` DATE NULL COMMENT 'Fineract source column start_date',
    -- column_id: c4c93a1b-af12-46af-9a68-e3476965c700
    `end_date` DATE NULL COMMENT 'Fineract source column end_date',
    -- column_id: 6548940d-d11d-4846-b40e-1a70d81f0de5
    `currency_code` VARCHAR(3) NOT NULL COMMENT 'Fineract source column currency_code',
    -- column_id: 4af99725-0927-4489-b552-a4fb4732062d
    `currency_digits` SMALLINT NOT NULL COMMENT 'Fineract source column currency_digits',
    -- column_id: 7fe439aa-20af-42dc-8bee-b50f94999ede
    `currency_multiplesof` SMALLINT NULL COMMENT 'Fineract source column currency_multiplesof',
    -- column_id: 95139383-4e77-491d-b86e-fe3cff90062e
    `total_shares` BIGINT NOT NULL COMMENT 'Fineract source column total_shares',
    -- column_id: 34b5620f-f16a-4199-9bd6-e249bb82a75f
    `issued_shares` BIGINT NULL COMMENT 'Fineract source column issued_shares',
    -- column_id: 6c09d02b-b8b0-4746-8918-a1f43211c7de
    `totalsubscribed_shares` BIGINT NULL COMMENT 'Fineract source column totalsubscribed_shares',
    -- column_id: d6104426-93ae-421a-a29d-7cec47a7356c
    `unit_price` DECIMAL(10,2) NOT NULL COMMENT 'Fineract source column unit_price',
    -- column_id: de753428-fade-4659-bde7-99aade25d852
    `capital_amount` DECIMAL(20,2) NOT NULL COMMENT 'Fineract source column capital_amount',
    -- column_id: b04deb24-797c-4fe5-96c4-b6a6861eaeb6
    `minimum_client_shares` BIGINT NULL COMMENT 'Fineract source column minimum_client_shares',
    -- column_id: db126912-0ec0-4263-b4af-b10aece06e1f
    `nominal_client_shares` BIGINT NOT NULL COMMENT 'Fineract source column nominal_client_shares',
    -- column_id: e0be6b1e-fc55-4fd8-a29e-dd4037df7f15
    `maximum_client_shares` BIGINT NULL COMMENT 'Fineract source column maximum_client_shares',
    -- column_id: c0bd6914-6918-4b80-8023-abe3ce657a4a
    `minimum_active_period_frequency` DECIMAL(19,6) NULL COMMENT 'Fineract source column minimum_active_period_frequency',
    -- column_id: 27e8d76a-b74e-4b15-bbfe-97f13c630471
    `minimum_active_period_frequency_enum` SMALLINT NULL COMMENT 'Fineract source column minimum_active_period_frequency_enum',
    -- column_id: 4ccc0f5b-314e-4f8f-b15d-20d641c2aa6a
    `lockin_period_frequency` DECIMAL(19,6) NULL COMMENT 'Fineract source column lockin_period_frequency',
    -- column_id: 78f67ffb-1e29-477b-80c6-c2f471254172
    `lockin_period_frequency_enum` SMALLINT NULL COMMENT 'Fineract source column lockin_period_frequency_enum',
    -- column_id: 11cc4465-e141-4a6c-aa99-d0fbb404ccd0
    `allow_dividends_inactive_clients` BOOLEAN NULL COMMENT 'Fineract source column allow_dividends_inactive_clients',
    -- column_id: 552baf32-6834-45bd-96e0-8a618a79b392
    `createdby_id` BIGINT NULL COMMENT 'Fineract source column createdby_id',
    -- column_id: c7ebe325-d08a-4e35-ac42-d05f29ca9818
    `created_date` DATETIME NULL COMMENT 'Fineract source column created_date',
    -- column_id: 244eaf11-0935-4d43-9d77-3e5fcdf74e86
    `lastmodifiedby_id` BIGINT NULL COMMENT 'Fineract source column lastmodifiedby_id',
    -- column_id: 1467b01d-a5c0-4b58-8c33-38dcd1d88529
    `lastmodified_date` DATETIME NULL COMMENT 'Fineract source column lastmodified_date',
    -- column_id: e76a7d4f-f60b-4d0d-ae71-8d1673271d3b
    `accounting_type` SMALLINT NOT NULL COMMENT 'Fineract source column accounting_type',
    -- column_id: 03a62327-4dc6-4c76-81af-99550e79ddf9
    `load_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
