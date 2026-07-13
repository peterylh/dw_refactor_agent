-- ODS mirror of Apache Fineract m_wc_loan_product (营运资金贷款)
DROP TABLE IF EXISTS retail_banking_dm.ods_fineract_m_wc_loan_product;
-- table_id: f14ef31f-5750-4b82-a9d1-f3cd0440e3d0
CREATE TABLE IF NOT EXISTS retail_banking_dm.ods_fineract_m_wc_loan_product (
    -- column_id: 9d837fcd-2383-4b0c-8bb8-132985245197
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: 2ee9040f-fbcd-4790-b96e-0532bc6093d3
    `name` VARCHAR(100) NOT NULL COMMENT 'Fineract source column name',
    -- column_id: 165c45a5-ea79-4daa-bbbc-1192cb87f4c3
    `short_name` VARCHAR(4) NOT NULL COMMENT 'Fineract source column short_name',
    -- column_id: 1936b990-a254-4e6b-a288-c38ca994f018
    `external_id` VARCHAR(100) NULL COMMENT 'Fineract source column external_id',
    -- column_id: 854c9f93-9e66-44f0-813c-6dc7e790dacc
    `fund_id` BIGINT NULL COMMENT 'Fineract source column fund_id',
    -- column_id: 0ec3c98f-182a-42b4-bce5-e721cb69f58b
    `start_date` DATE NULL COMMENT 'Fineract source column start_date',
    -- column_id: 10cbce5d-d4a1-4029-99b1-6b0d4ba9b19f
    `close_date` DATE NULL COMMENT 'Fineract source column close_date',
    -- column_id: 28f1767c-e96b-48a0-9897-2e44332ee3dd
    `description` VARCHAR(500) NULL COMMENT 'Fineract source column description',
    -- column_id: 60628283-6a8d-40d7-b8f0-66830c3a751d
    `currency_code` VARCHAR(3) NOT NULL COMMENT 'Fineract source column currency_code',
    -- column_id: 4aecd43e-eeb4-481a-b9aa-3877054819b6
    `currency_digits` SMALLINT NOT NULL COMMENT 'Fineract source column currency_digits',
    -- column_id: 79290ff3-c388-4eee-902f-130d949b5df9
    `currency_multiplesof` SMALLINT NULL COMMENT 'Fineract source column currency_multiplesof',
    -- column_id: 5db8585a-85c1-43ee-841c-7e21e52f8f80
    `amortization_type` VARCHAR(50) NOT NULL COMMENT 'Fineract source column amortization_type',
    -- column_id: 53699a17-27c4-4c81-b220-94505ed420e6
    `delinquency_bucket_classification_id` BIGINT NULL COMMENT 'Fineract source column delinquency_bucket_classification_id',
    -- column_id: 3a218f09-c456-4e6c-852d-8927b94e8aa1
    `npv_day_count` INT NOT NULL COMMENT 'Fineract source column npv_day_count',
    -- column_id: ea8f4012-0a05-43b6-bbcd-6a7b105749fd
    `min_principal_amount` DECIMAL(19,6) NULL COMMENT 'Fineract source column min_principal_amount',
    -- column_id: fb61d260-7e3e-42a0-86e9-b92918bab9a9
    `principal_amount` DECIMAL(19,6) NOT NULL COMMENT 'Fineract source column principal_amount',
    -- column_id: 5a55bd59-3c34-44cc-8002-fb3bcc8c12ae
    `max_principal_amount` DECIMAL(19,6) NULL COMMENT 'Fineract source column max_principal_amount',
    -- column_id: 7e4c4d97-026f-470c-8eb6-6ea921c6b2c2
    `min_period_payment_rate` DECIMAL(19,6) NULL COMMENT 'Fineract source column min_period_payment_rate',
    -- column_id: 9fa6a895-bcf7-4b6b-89bb-769fad2c8e94
    `period_payment_rate` DECIMAL(19,6) NOT NULL COMMENT 'Fineract source column period_payment_rate',
    -- column_id: f1c47cd1-93ca-48ab-aa50-f043e20951f5
    `max_period_payment_rate` DECIMAL(19,6) NULL COMMENT 'Fineract source column max_period_payment_rate',
    -- column_id: 9e854ecc-20f7-411f-b58b-df92f9bba1d9
    `discount` DECIMAL(19,6) NULL COMMENT 'Fineract source column discount',
    -- column_id: 8c3071d1-d041-4ff5-90d3-d217a6a3808a
    `repayment_every` INT NOT NULL COMMENT 'Fineract source column repayment_every',
    -- column_id: 1476e8a4-d880-4f29-b381-2997b61b532d
    `repayment_frequency_enum` VARCHAR(50) NOT NULL COMMENT 'Fineract source column repayment_frequency_enum',
    -- column_id: d2e4d472-5433-4dea-ad97-ba9cab887fd4
    `delinquency_grace_days` INT NULL COMMENT 'Fineract source column delinquency_grace_days',
    -- column_id: 3a07025f-a773-4d2d-b1b6-2c93dd454057
    `delinquency_start_type` VARCHAR(20) NULL COMMENT 'Fineract source column delinquency_start_type',
    -- column_id: 39b9174a-22c5-4f61-929b-81bce15f97f3
    `breach_id` BIGINT NULL COMMENT 'Fineract source column breach_id',
    -- column_id: 44348ca8-922e-48fa-95b9-83263c53e909
    `accounting_type` VARCHAR(20) NOT NULL COMMENT 'Fineract source column accounting_type',
    -- column_id: fa2c3e53-974b-4e78-bdc5-bd2ebd5c6bd5
    `near_breach_id` BIGINT NULL COMMENT 'Fineract source column near_breach_id',
    -- column_id: 0e1cef99-1687-4181-8d88-0ba192e2fcb1
    `breach_grace_days` INT NULL COMMENT 'Fineract source column breach_grace_days',
    -- column_id: 3a003076-f817-4880-8165-5171e05f8cfb
    `load_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
