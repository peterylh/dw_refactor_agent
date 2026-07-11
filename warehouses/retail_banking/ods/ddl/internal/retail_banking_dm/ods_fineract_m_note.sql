-- ODS mirror of Apache Fineract m_note (渠道与客户服务)
DROP TABLE IF EXISTS retail_banking_dm.ods_fineract_m_note;
-- table_id: f481b198-b611-41eb-84d2-a9ffa4cd65a0
CREATE TABLE IF NOT EXISTS retail_banking_dm.ods_fineract_m_note (
    -- column_id: c881921b-be9f-442f-b743-ab4fa3d2a7ed
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: 7e37b6bd-39ec-408d-8693-cf679809c541
    `client_id` BIGINT NULL COMMENT 'Fineract source column client_id',
    -- column_id: 45060335-40fb-48bc-9c43-38e29591bf37
    `group_id` BIGINT NULL COMMENT 'Fineract source column group_id',
    -- column_id: 58f8974d-fbf3-4aeb-91d5-81cefdeafeba
    `loan_id` BIGINT NULL COMMENT 'Fineract source column loan_id',
    -- column_id: f69892b6-f897-4b09-9c38-d01d9a11f991
    `loan_transaction_id` BIGINT NULL COMMENT 'Fineract source column loan_transaction_id',
    -- column_id: d5e82aa4-06ff-4719-941a-f8c4d761e50f
    `savings_account_id` BIGINT NULL COMMENT 'Fineract source column savings_account_id',
    -- column_id: aa510107-34aa-4952-b354-26ca0b736cdc
    `savings_account_transaction_id` BIGINT NULL COMMENT 'Fineract source column savings_account_transaction_id',
    -- column_id: 9be055e2-7c2a-4925-9921-35f291f3edb0
    `share_account_id` BIGINT NULL COMMENT 'Fineract source column share_account_id',
    -- column_id: e2ce0406-7179-4787-b256-2a56177f9c0b
    `note_type_enum` SMALLINT NOT NULL COMMENT 'Fineract source column note_type_enum',
    -- column_id: 41d01e7a-5389-4500-8987-440dab9ad7b5
    `note` VARCHAR(1000) NULL COMMENT 'Fineract source column note',
    -- column_id: 05c125f5-299e-4166-878b-cc15dfe6e4c3
    `created_date` DATETIME NULL COMMENT 'Fineract source column created_date',
    -- column_id: e7b99f9c-42df-4c56-8019-66f1d36943a3
    `created_by` BIGINT NOT NULL COMMENT 'Fineract source column created_by',
    -- column_id: 7b30355e-168e-4c7b-ba8d-54bc24be70bc
    `lastmodified_date` DATETIME NULL COMMENT 'Fineract source column lastmodified_date',
    -- column_id: f7928d0e-1dad-4fc4-8280-fed36f92783f
    `last_modified_by` BIGINT NOT NULL COMMENT 'Fineract source column last_modified_by',
    -- column_id: 5b6c2ec4-86b1-4bb6-b9f8-295f294fedc8
    `created_on_utc` DATETIME NOT NULL COMMENT 'Fineract source column created_on_utc',
    -- column_id: d468a74c-6f3f-4599-ab49-93fbd4bbf04e
    `last_modified_on_utc` DATETIME NOT NULL COMMENT 'Fineract source column last_modified_on_utc',
    -- column_id: 1c015283-e5ad-4f30-9bbb-a3bd3776e579
    `load_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
