-- DIM generated from m_loan_recalculation_details
DROP TABLE IF EXISTS retail_banking_dm.dim_loan_interest_terms_satellite;
-- table_id: 28780580-3844-411e-947a-20c01e3ce07b
CREATE TABLE IF NOT EXISTS retail_banking_dm.dim_loan_interest_terms_satellite (
    -- column_id: f9e02a30-3039-479e-a7ac-b5e6436b22f8
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: 76ab617c-d037-4cd5-8821-b76adefb597c
    `loan_id` BIGINT NOT NULL COMMENT 'Fineract source column loan_id',
    -- column_id: bcd699e1-ce1a-4707-8391-2839e83ec5d5
    `compound_type_enum` SMALLINT NOT NULL COMMENT 'Fineract source column compound_type_enum',
    -- column_id: 5de3af33-7acb-425c-8645-c59606e448a7
    `reschedule_strategy_enum` SMALLINT NOT NULL COMMENT 'Fineract source column reschedule_strategy_enum',
    -- column_id: 49a3124a-0347-4c14-ad7e-024d3fa08752
    `rest_frequency_type_enum` SMALLINT NOT NULL COMMENT 'Fineract source column rest_frequency_type_enum',
    -- column_id: 5eb3e3e6-4b18-4b1a-904c-49b3b4ac63b0
    `rest_frequency_interval` SMALLINT NOT NULL COMMENT 'Fineract source column rest_frequency_interval',
    -- column_id: a3903c83-4f34-409b-a6dc-769463e05682
    `compounding_frequency_type_enum` SMALLINT NULL COMMENT 'Fineract source column compounding_frequency_type_enum',
    -- column_id: 43ff6670-18bf-4625-bbf9-64fe4d121794
    `compounding_frequency_interval` SMALLINT NULL COMMENT 'Fineract source column compounding_frequency_interval',
    -- column_id: 3d4b53c7-9732-4499-95fe-8c816432d718
    `rest_frequency_nth_day_enum` INT NULL COMMENT 'Fineract source column rest_frequency_nth_day_enum',
    -- column_id: 24c60a24-20e4-4d97-a05d-c4b789fbcad7
    `rest_frequency_on_day` INT NULL COMMENT 'Fineract source column rest_frequency_on_day',
    -- column_id: 22e2cf89-c6cd-4761-86ef-a3b79854cce5
    `rest_frequency_weekday_enum` INT NULL COMMENT 'Fineract source column rest_frequency_weekday_enum',
    -- column_id: 77d8ea8f-0277-40b7-9fcc-b06c42a84900
    `compounding_frequency_nth_day_enum` INT NULL COMMENT 'Fineract source column compounding_frequency_nth_day_enum',
    -- column_id: 5d726a21-39e4-4706-bfa4-41c100690645
    `compounding_frequency_on_day` INT NULL COMMENT 'Fineract source column compounding_frequency_on_day',
    -- column_id: 5ef9e30a-079f-4ea9-a6ea-7dc9fa1cde9c
    `is_compounding_to_be_posted_as_transaction` BOOLEAN NOT NULL COMMENT 'Fineract source column is_compounding_to_be_posted_as_transaction',
    -- column_id: f812d4be-d082-452b-a68d-fe9ea287bd9f
    `compounding_frequency_weekday_enum` INT NULL COMMENT 'Fineract source column compounding_frequency_weekday_enum',
    -- column_id: 07718e37-0719-417c-8265-016c3c4135f6
    `allow_compounding_on_eod` BOOLEAN NOT NULL COMMENT 'Fineract source column allow_compounding_on_eod',
    -- column_id: 1d4b8a76-283c-4311-bb65-beb56a465432
    `disallow_interest_calc_on_past_due` BOOLEAN NOT NULL COMMENT 'Fineract source column disallow_interest_calc_on_past_due',
    -- column_id: 90f37575-d33b-4853-aff7-f0ad731c382c
    `pre_close_interest_calculation_strategy` SMALLINT NOT NULL COMMENT 'Fineract source column pre_close_interest_calculation_strategy',
    -- column_id: f84d6c93-ea4f-49d3-893b-ff0ab23eaf3b
    `etl_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
