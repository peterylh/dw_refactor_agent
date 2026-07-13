-- ODS mirror of Apache Fineract m_loan_recalculation_details (贷款与信贷)
DROP TABLE IF EXISTS retail_banking_dm.ods_fineract_m_loan_recalculation_details;
-- table_id: 19f1779d-ce88-428b-b636-033babbc2977
CREATE TABLE IF NOT EXISTS retail_banking_dm.ods_fineract_m_loan_recalculation_details (
    -- column_id: deba2290-cd36-40ea-95e7-2a0d8856356a
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: 36fea6c5-be53-48b4-bdd5-26db94ad2ac6
    `loan_id` BIGINT NOT NULL COMMENT 'Fineract source column loan_id',
    -- column_id: 6e9c832b-5899-475b-a324-70269b389cfc
    `compound_type_enum` SMALLINT NOT NULL COMMENT 'Fineract source column compound_type_enum',
    -- column_id: 32066e61-f7f3-434f-94dd-1110339e6b1d
    `reschedule_strategy_enum` SMALLINT NOT NULL COMMENT 'Fineract source column reschedule_strategy_enum',
    -- column_id: e072cd1e-a2af-40a7-9935-63bcb99e616d
    `rest_frequency_type_enum` SMALLINT NOT NULL COMMENT 'Fineract source column rest_frequency_type_enum',
    -- column_id: f0505be7-0e34-4f9b-8371-c0d4027e08dc
    `rest_frequency_interval` SMALLINT NOT NULL COMMENT 'Fineract source column rest_frequency_interval',
    -- column_id: 67fc44a4-13f0-483e-aa4e-0709fd1af52a
    `compounding_frequency_type_enum` SMALLINT NULL COMMENT 'Fineract source column compounding_frequency_type_enum',
    -- column_id: 6edf2ae7-941f-450d-8a4a-5b4cf89e2cc3
    `compounding_frequency_interval` SMALLINT NULL COMMENT 'Fineract source column compounding_frequency_interval',
    -- column_id: c3032e11-9037-425e-92b9-66a25042c84a
    `rest_frequency_nth_day_enum` INT NULL COMMENT 'Fineract source column rest_frequency_nth_day_enum',
    -- column_id: 358d4949-52b2-48fe-8bec-efa1aee524d3
    `rest_frequency_on_day` INT NULL COMMENT 'Fineract source column rest_frequency_on_day',
    -- column_id: b3086d9e-c9d9-43ac-893e-681b7ee78118
    `rest_frequency_weekday_enum` INT NULL COMMENT 'Fineract source column rest_frequency_weekday_enum',
    -- column_id: e70b1f5c-b915-46ca-9752-c43746204ad2
    `compounding_frequency_nth_day_enum` INT NULL COMMENT 'Fineract source column compounding_frequency_nth_day_enum',
    -- column_id: ea1e332f-90b8-4e72-9701-ee4a51391fd4
    `compounding_frequency_on_day` INT NULL COMMENT 'Fineract source column compounding_frequency_on_day',
    -- column_id: 02fb420a-5ac4-4a20-92be-0ebd4af6def1
    `is_compounding_to_be_posted_as_transaction` BOOLEAN NOT NULL COMMENT 'Fineract source column is_compounding_to_be_posted_as_transaction',
    -- column_id: 81072edc-8a09-4d99-8742-fb728330361d
    `compounding_frequency_weekday_enum` INT NULL COMMENT 'Fineract source column compounding_frequency_weekday_enum',
    -- column_id: 983cb566-9406-44d9-9036-a933a77badbe
    `allow_compounding_on_eod` BOOLEAN NOT NULL COMMENT 'Fineract source column allow_compounding_on_eod',
    -- column_id: fb60ba51-deb9-40b8-bc5a-2a2261291526
    `disallow_interest_calc_on_past_due` BOOLEAN NOT NULL COMMENT 'Fineract source column disallow_interest_calc_on_past_due',
    -- column_id: fb0a1ced-4bbc-4f65-9a81-f0b788af256c
    `pre_close_interest_calculation_strategy` SMALLINT NOT NULL COMMENT 'Fineract source column pre_close_interest_calculation_strategy',
    -- column_id: 97d40548-548e-4302-8f0f-05eb705a30f4
    `load_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
