-- DIM generated from m_wc_loan_product
DROP TABLE IF EXISTS retail_banking_dm.dim_wc_loan_product;
-- table_id: 7b9f86a1-91fd-4606-8c59-7147cdd730fb
CREATE TABLE IF NOT EXISTS retail_banking_dm.dim_wc_loan_product (
    -- column_id: d68be67e-4a30-4bc7-9b49-10e720fc7553
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: d33210a2-d4a4-4b59-9113-be167152de87
    `name` VARCHAR(100) NOT NULL COMMENT 'Fineract source column name',
    -- column_id: ca83aa05-55ba-486e-80f0-5f6d3cbdcc14
    `short_name` VARCHAR(4) NOT NULL COMMENT 'Fineract source column short_name',
    -- column_id: 50b4200b-d212-40b6-9534-23fa0a906fd3
    `external_id` VARCHAR(100) NULL COMMENT 'Fineract source column external_id',
    -- column_id: 55ba7ae2-5b82-433d-9a9a-34dc95658907
    `fund_id` BIGINT NULL COMMENT 'Fineract source column fund_id',
    -- column_id: 330934d0-5fe8-4834-8ea7-7106c38bd0f1
    `start_date` DATE NULL COMMENT 'Fineract source column start_date',
    -- column_id: 031c4c82-7164-4aa2-8da6-f7c9db3a65b9
    `close_date` DATE NULL COMMENT 'Fineract source column close_date',
    -- column_id: 051e616b-0eef-4338-9c49-827364376e9d
    `description` VARCHAR(500) NULL COMMENT 'Fineract source column description',
    -- column_id: 1e974056-878b-45f2-a0d0-0cf0d67069e8
    `currency_code` VARCHAR(3) NOT NULL COMMENT 'Fineract source column currency_code',
    -- column_id: 3cea2230-63b0-4a1d-846d-78d5ba36c83a
    `currency_digits` SMALLINT NOT NULL COMMENT 'Fineract source column currency_digits',
    -- column_id: 1fc76b87-9f66-4fe9-a209-447b45dc57ef
    `currency_multiplesof` SMALLINT NULL COMMENT 'Fineract source column currency_multiplesof',
    -- column_id: 4e5196ef-b5af-435f-a2bc-e73cc2b2f572
    `amortization_type` VARCHAR(50) NOT NULL COMMENT 'Fineract source column amortization_type',
    -- column_id: b574724b-a26a-4223-855d-f189609b53be
    `delinquency_bucket_classification_id` BIGINT NULL COMMENT 'Fineract source column delinquency_bucket_classification_id',
    -- column_id: 8b70bb4f-e3d3-443e-998f-969f0b070ee7
    `npv_day_count` INT NOT NULL COMMENT 'Fineract source column npv_day_count',
    -- column_id: 5e479f2e-8942-43a6-9f90-95657206432f
    `min_principal_amount` DECIMAL(19,6) NULL COMMENT 'Fineract source column min_principal_amount',
    -- column_id: 902f0e88-e781-4870-8f7e-9038604ac161
    `principal_amount` DECIMAL(19,6) NOT NULL COMMENT 'Fineract source column principal_amount',
    -- column_id: e6422fb3-6437-4ecf-b64e-ee6e6164f178
    `max_principal_amount` DECIMAL(19,6) NULL COMMENT 'Fineract source column max_principal_amount',
    -- column_id: 626bd2ca-0cb5-42ed-9c07-7f8218b22a84
    `min_period_payment_rate` DECIMAL(19,6) NULL COMMENT 'Fineract source column min_period_payment_rate',
    -- column_id: cdbc3623-d3e5-4ddb-af8b-e22efc9085ff
    `period_payment_rate` DECIMAL(19,6) NOT NULL COMMENT 'Fineract source column period_payment_rate',
    -- column_id: 74c53ce1-bac3-4bc6-8d9d-04651446fd72
    `max_period_payment_rate` DECIMAL(19,6) NULL COMMENT 'Fineract source column max_period_payment_rate',
    -- column_id: 15b22ca6-435f-45e7-8d05-5e23c02c7d3a
    `discount` DECIMAL(19,6) NULL COMMENT 'Fineract source column discount',
    -- column_id: 5584b8f4-c170-4623-9c29-e8017cf62247
    `repayment_every` INT NOT NULL COMMENT 'Fineract source column repayment_every',
    -- column_id: 19a7ea36-8831-4a17-bfcb-3b366e2bfa06
    `repayment_frequency_enum` VARCHAR(50) NOT NULL COMMENT 'Fineract source column repayment_frequency_enum',
    -- column_id: af8c61a4-85ef-48e5-9e44-fafd5b14136f
    `delinquency_grace_days` INT NULL COMMENT 'Fineract source column delinquency_grace_days',
    -- column_id: 66f67d8d-3d61-4a74-b35c-488ae45fb5d7
    `delinquency_start_type` VARCHAR(20) NULL COMMENT 'Fineract source column delinquency_start_type',
    -- column_id: c045f929-12b7-4c2f-b2d9-bb4b3785a053
    `breach_id` BIGINT NULL COMMENT 'Fineract source column breach_id',
    -- column_id: 0891b4d5-43ba-4397-8c0c-0e068bc5e746
    `accounting_type` VARCHAR(20) NOT NULL COMMENT 'Fineract source column accounting_type',
    -- column_id: 9326fdcd-f8ff-4ddf-8cc7-76b4104e4825
    `near_breach_id` BIGINT NULL COMMENT 'Fineract source column near_breach_id',
    -- column_id: 0300d524-8756-4150-aa4f-e0f57bc49dbf
    `breach_grace_days` INT NULL COMMENT 'Fineract source column breach_grace_days',
    -- column_id: 692d6e8b-da16-4cf3-984a-2a42e7aa96fb
    `etl_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
