-- ODS mirror of Apache Fineract m_product_loan_floating_rates (贷款与信贷)
DROP TABLE IF EXISTS retail_banking_dm.ods_fineract_m_product_loan_floating_rates;
-- table_id: 0d095ad3-d2a7-4c11-b617-2b16ecf60f9c
CREATE TABLE IF NOT EXISTS retail_banking_dm.ods_fineract_m_product_loan_floating_rates (
    -- column_id: 26d9dbaa-9322-4304-b31d-f45c67eea92f
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: 44b8eeb2-bbb0-428d-a24a-afd407084117
    `loan_product_id` BIGINT NOT NULL COMMENT 'Fineract source column loan_product_id',
    -- column_id: b805bc66-47df-41ac-a91e-98da4cba37ff
    `floating_rates_id` BIGINT NOT NULL COMMENT 'Fineract source column floating_rates_id',
    -- column_id: fb7fe26f-1ee0-42c3-972c-4d25cf7ee251
    `interest_rate_differential` DECIMAL(19,6) NOT NULL COMMENT 'Fineract source column interest_rate_differential',
    -- column_id: 6cdb9b1b-e518-4904-9c84-045b95cda30e
    `min_differential_lending_rate` DECIMAL(19,6) NOT NULL COMMENT 'Fineract source column min_differential_lending_rate',
    -- column_id: 67729cb7-29e6-4655-870f-4f17df1cfe1d
    `default_differential_lending_rate` DECIMAL(19,6) NOT NULL COMMENT 'Fineract source column default_differential_lending_rate',
    -- column_id: 9acc9c4f-f8a0-4102-8101-6d14c4008a23
    `max_differential_lending_rate` DECIMAL(19,6) NOT NULL COMMENT 'Fineract source column max_differential_lending_rate',
    -- column_id: 275d24af-63be-4ad1-b876-679da5764092
    `is_floating_interest_rate_calculation_allowed` BOOLEAN NOT NULL COMMENT 'Fineract source column is_floating_interest_rate_calculation_allowed',
    -- column_id: b0d7e7ae-1856-45d5-810d-2631ec3f65f0
    `load_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
