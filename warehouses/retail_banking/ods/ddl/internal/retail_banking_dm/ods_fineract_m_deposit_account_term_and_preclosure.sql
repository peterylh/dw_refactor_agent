-- ODS mirror of Apache Fineract m_deposit_account_term_and_preclosure (存款与储蓄)
DROP TABLE IF EXISTS retail_banking_dm.ods_fineract_m_deposit_account_term_and_preclosure;
-- table_id: 5bfddfac-90d0-4cb0-88a3-63381610c4c7
CREATE TABLE IF NOT EXISTS retail_banking_dm.ods_fineract_m_deposit_account_term_and_preclosure (
    -- column_id: 33d26036-394d-4d98-870a-232e04aa6390
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: 1a6e5dc2-555f-4540-8e15-a0fc1a929103
    `savings_account_id` BIGINT NOT NULL COMMENT 'Fineract source column savings_account_id',
    -- column_id: a2af428a-0bf4-4ca1-be0e-430bca46a83a
    `min_deposit_term` INT NULL COMMENT 'Fineract source column min_deposit_term',
    -- column_id: 61dcfa9a-43a6-43cc-9589-ffb6a07cf365
    `max_deposit_term` INT NULL COMMENT 'Fineract source column max_deposit_term',
    -- column_id: b70d362b-fd97-446d-bffa-f776b3e39023
    `min_deposit_term_type_enum` SMALLINT NULL COMMENT 'Fineract source column min_deposit_term_type_enum',
    -- column_id: 82bb5b82-d508-4941-b2da-ccdee6973283
    `max_deposit_term_type_enum` SMALLINT NULL COMMENT 'Fineract source column max_deposit_term_type_enum',
    -- column_id: cf6e4e9f-ecc5-4677-99c8-6cebe73e5a54
    `in_multiples_of_deposit_term` INT NULL COMMENT 'Fineract source column in_multiples_of_deposit_term',
    -- column_id: f2660034-20fe-43f4-ae9c-4ee411b1fae4
    `in_multiples_of_deposit_term_type_enum` SMALLINT NULL COMMENT 'Fineract source column in_multiples_of_deposit_term_type_enum',
    -- column_id: 089385c4-75cb-4a99-9412-e90972632672
    `pre_closure_penal_applicable` BOOLEAN NULL COMMENT 'Fineract source column pre_closure_penal_applicable',
    -- column_id: bd6549f5-90b4-4e3b-932e-ae20d1c4bc3a
    `pre_closure_penal_interest` DECIMAL(19,6) NULL COMMENT 'Fineract source column pre_closure_penal_interest',
    -- column_id: 8e140a05-adef-428b-92c5-dad0a30ada3a
    `pre_closure_penal_interest_on_enum` SMALLINT NULL COMMENT 'Fineract source column pre_closure_penal_interest_on_enum',
    -- column_id: dcc5f723-f6b9-4974-aa2f-2ad0a35159f9
    `deposit_period` INT NULL COMMENT 'Fineract source column deposit_period',
    -- column_id: 673a88c9-3e9f-4b9d-9462-10aca676cd88
    `deposit_period_frequency_enum` SMALLINT NULL COMMENT 'Fineract source column deposit_period_frequency_enum',
    -- column_id: f06f52e8-b2f3-462e-8635-9fe38770103e
    `deposit_amount` DECIMAL(19,6) NULL COMMENT 'Fineract source column deposit_amount',
    -- column_id: 33738b10-bbcf-4594-8f68-fa6c1525fe2a
    `maturity_amount` DECIMAL(19,6) NULL COMMENT 'Fineract source column maturity_amount',
    -- column_id: 674d1844-2f39-4028-9df0-c4884b7a102a
    `maturity_date` DATE NULL COMMENT 'Fineract source column maturity_date',
    -- column_id: 7d718fde-f68a-4249-be98-d00daa7f71b6
    `on_account_closure_enum` SMALLINT NULL COMMENT 'Fineract source column on_account_closure_enum',
    -- column_id: 0746a6e5-5346-4d00-9718-0b24bfc7b85d
    `expected_firstdepositon_date` DATE NULL COMMENT 'Fineract source column expected_firstdepositon_date',
    -- column_id: e4281265-54d9-4833-b8db-7ec5b2cbdfb9
    `transfer_interest_to_linked_account` BOOLEAN NOT NULL COMMENT 'Fineract source column transfer_interest_to_linked_account',
    -- column_id: d9d40799-4393-47c8-93ac-88944854e0a6
    `transfer_to_savings_account_id` BIGINT NULL COMMENT 'Fineract source column transfer_to_savings_account_id',
    -- column_id: f05d279b-e625-4058-9a0f-31f40569f4c0
    `load_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
