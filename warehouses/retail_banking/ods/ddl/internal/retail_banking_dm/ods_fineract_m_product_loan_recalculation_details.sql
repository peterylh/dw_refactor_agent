-- ODS mirror of Apache Fineract m_product_loan_recalculation_details (贷款与信贷)
DROP TABLE IF EXISTS retail_banking_dm.ods_fineract_m_product_loan_recalculation_details;
-- table_id: 28bbb6c5-4fc5-44a9-814b-1312e58a97d5
CREATE TABLE IF NOT EXISTS retail_banking_dm.ods_fineract_m_product_loan_recalculation_details (
    -- column_id: cd4b79c5-b35b-4693-8ce6-df6f978f821f
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: 5bf85a7e-3d78-4814-a9fd-a166f0c56a5b
    `product_id` BIGINT NOT NULL COMMENT 'Fineract source column product_id',
    -- column_id: 5433d3d6-973f-4cb5-b9fd-fc0f8bd24647
    `compound_type_enum` SMALLINT NOT NULL COMMENT 'Fineract source column compound_type_enum',
    -- column_id: e7e18bd3-e859-4d51-b2a2-ed12bcf79166
    `reschedule_strategy_enum` SMALLINT NOT NULL COMMENT 'Fineract source column reschedule_strategy_enum',
    -- column_id: cd94111f-a428-4d24-8f70-d837fb67cd49
    `rest_frequency_type_enum` SMALLINT NOT NULL COMMENT 'Fineract source column rest_frequency_type_enum',
    -- column_id: 5ac41ede-4bda-4161-b879-9090c7f6f515
    `rest_frequency_interval` SMALLINT NOT NULL COMMENT 'Fineract source column rest_frequency_interval',
    -- column_id: ee3b3e4c-3667-46cf-8900-34ae80c92477
    `arrears_based_on_original_schedule` BOOLEAN NOT NULL COMMENT 'Fineract source column arrears_based_on_original_schedule',
    -- column_id: 6a1971ce-1991-423e-9a98-54c8a3d3ab9b
    `pre_close_interest_calculation_strategy` SMALLINT NOT NULL COMMENT 'Fineract source column pre_close_interest_calculation_strategy',
    -- column_id: 7c23b4d0-abbe-4968-a252-1228f51be376
    `compounding_frequency_type_enum` SMALLINT NULL COMMENT 'Fineract source column compounding_frequency_type_enum',
    -- column_id: d246aac9-d703-4ebb-9824-8bd2896da769
    `compounding_frequency_interval` SMALLINT NULL COMMENT 'Fineract source column compounding_frequency_interval',
    -- column_id: 1ce1af0f-d432-48ee-93c8-8cd7645c8375
    `rest_frequency_nth_day_enum` INT NULL COMMENT 'Fineract source column rest_frequency_nth_day_enum',
    -- column_id: 80ff2bcf-12a2-441f-ba42-760af4428cc2
    `rest_frequency_on_day` INT NULL COMMENT 'Fineract source column rest_frequency_on_day',
    -- column_id: ecf42acc-25d0-4d06-b5ba-b6e903f8669d
    `rest_frequency_weekday_enum` INT NULL COMMENT 'Fineract source column rest_frequency_weekday_enum',
    -- column_id: 4054c3c7-52b7-41e8-96cd-99b2ae7bd9d8
    `compounding_frequency_nth_day_enum` INT NULL COMMENT 'Fineract source column compounding_frequency_nth_day_enum',
    -- column_id: bb6f1498-1ab3-4de8-8d9f-676504b244a4
    `compounding_frequency_on_day` INT NULL COMMENT 'Fineract source column compounding_frequency_on_day',
    -- column_id: c7b25bed-e4c8-4b12-a535-1894057b1c63
    `compounding_frequency_weekday_enum` INT NULL COMMENT 'Fineract source column compounding_frequency_weekday_enum',
    -- column_id: 368720cf-71dc-40d4-903f-a2153fab35b8
    `is_compounding_to_be_posted_as_transaction` BOOLEAN NOT NULL COMMENT 'Fineract source column is_compounding_to_be_posted_as_transaction',
    -- column_id: e2d643ea-02d2-435b-94d0-cf7d3b4d3260
    `allow_compounding_on_eod` BOOLEAN NOT NULL COMMENT 'Fineract source column allow_compounding_on_eod',
    -- column_id: 98b555b7-7c28-4023-93b1-3080bfdafb9d
    `disallow_interest_calc_on_past_due` BOOLEAN NOT NULL COMMENT 'Fineract source column disallow_interest_calc_on_past_due',
    -- column_id: a87f3a7f-f541-47de-9d5c-fb05c9c7b5b1
    `load_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
