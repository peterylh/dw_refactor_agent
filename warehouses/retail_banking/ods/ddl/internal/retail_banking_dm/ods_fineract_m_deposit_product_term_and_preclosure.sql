-- ODS mirror of Apache Fineract m_deposit_product_term_and_preclosure (存款与储蓄)
DROP TABLE IF EXISTS retail_banking_dm.ods_fineract_m_deposit_product_term_and_preclosure;
-- table_id: defe71b6-8b09-4493-bb76-1f9b4a7bad39
CREATE TABLE IF NOT EXISTS retail_banking_dm.ods_fineract_m_deposit_product_term_and_preclosure (
    -- column_id: 86024097-90ab-4e3b-b6ff-2bc448d3a90f
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: 3a6ecada-c6ab-4fd4-8fb5-4f36bb605e33
    `savings_product_id` BIGINT NOT NULL COMMENT 'Fineract source column savings_product_id',
    -- column_id: ffeebb65-8783-4a17-baa3-331b3cb6c38e
    `min_deposit_term` INT NULL COMMENT 'Fineract source column min_deposit_term',
    -- column_id: 59ad1473-a496-49a1-a86b-b40668b81319
    `max_deposit_term` INT NULL COMMENT 'Fineract source column max_deposit_term',
    -- column_id: a4bed8c5-db9c-45dc-b085-bc747e425063
    `min_deposit_term_type_enum` SMALLINT NULL COMMENT 'Fineract source column min_deposit_term_type_enum',
    -- column_id: 07188dc5-9d8d-4370-9a87-ebf537a92374
    `max_deposit_term_type_enum` SMALLINT NULL COMMENT 'Fineract source column max_deposit_term_type_enum',
    -- column_id: 4fb2809f-cf86-4ccf-b503-be4d85f046e4
    `in_multiples_of_deposit_term` INT NULL COMMENT 'Fineract source column in_multiples_of_deposit_term',
    -- column_id: 115d065a-f7ee-4684-aa10-913a3c5f2c11
    `in_multiples_of_deposit_term_type_enum` SMALLINT NULL COMMENT 'Fineract source column in_multiples_of_deposit_term_type_enum',
    -- column_id: e615d52b-7dc9-4dd6-a404-7b4c710feb33
    `pre_closure_penal_applicable` BOOLEAN NULL COMMENT 'Fineract source column pre_closure_penal_applicable',
    -- column_id: 648ed73b-eeb2-41a7-9c8b-c6c4ca8f6183
    `pre_closure_penal_interest` DECIMAL(19,6) NULL COMMENT 'Fineract source column pre_closure_penal_interest',
    -- column_id: 4289a8e8-3007-43c9-9852-d925573abea6
    `pre_closure_penal_interest_on_enum` SMALLINT NULL COMMENT 'Fineract source column pre_closure_penal_interest_on_enum',
    -- column_id: a92d0072-b87b-409b-819d-394eb32498b8
    `min_deposit_amount` DECIMAL(19,6) NULL COMMENT 'Fineract source column min_deposit_amount',
    -- column_id: 9ab80168-6990-4168-8e88-19eb77fce565
    `max_deposit_amount` DECIMAL(19,6) NULL COMMENT 'Fineract source column max_deposit_amount',
    -- column_id: bd2037ae-662f-4fc8-bc09-16e9b93d858c
    `deposit_amount` DECIMAL(19,6) NULL COMMENT 'Fineract source column deposit_amount',
    -- column_id: 3d044bdd-4166-4e55-a20a-959fa56d83db
    `load_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
