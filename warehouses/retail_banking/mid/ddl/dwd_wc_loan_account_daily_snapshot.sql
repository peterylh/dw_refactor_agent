-- DWD account snapshot generated from m_wc_loan
DROP TABLE IF EXISTS retail_banking_dm.dwd_wc_loan_account_daily_snapshot;
-- table_id: f3e3c94f-6344-41d8-9db5-edbfd8e67381
CREATE TABLE IF NOT EXISTS retail_banking_dm.dwd_wc_loan_account_daily_snapshot (
    -- column_id: 76709d47-91c8-4180-a128-d71fef946699
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: 54f33473-0154-4248-88d5-6ba5cd9fe73f
    `snapshot_date` DATE NOT NULL COMMENT 'Warehouse account snapshot date',
    -- column_id: 7080c8bd-439c-450c-92fc-f662e525335d
    `version` INT NOT NULL COMMENT 'Fineract source column version',
    -- column_id: 265fad83-2673-44be-a486-994f374ee33a
    `created_by` BIGINT NOT NULL COMMENT 'Fineract source column created_by',
    -- column_id: cc4d26c2-a4ce-480d-be97-e01e10673a93
    `last_modified_by` BIGINT NOT NULL COMMENT 'Fineract source column last_modified_by',
    -- column_id: 68e05b1f-aef5-4651-ad52-6b6d65e5ffed
    `created_on_utc` DATETIME NOT NULL COMMENT 'Fineract source column created_on_utc',
    -- column_id: 0cb688a8-69de-4791-8fe6-8552c9d121dd
    `last_modified_on_utc` DATETIME NOT NULL COMMENT 'Fineract source column last_modified_on_utc',
    -- column_id: 278886fc-bda1-478e-921a-f83ba4de5ec2
    `loan_status_id` SMALLINT NOT NULL COMMENT 'Fineract source column loan_status_id',
    -- column_id: 900a8b8c-a8f2-4160-894a-bb30898dba1d
    `last_closed_business_date` DATE NULL COMMENT 'Fineract source column last_closed_business_date',
    -- column_id: b885cefd-f8cf-4f37-a9de-050d87bca0cc
    `account_no` VARCHAR(64) NOT NULL COMMENT 'Fineract source column account_no',
    -- column_id: 4fde0247-549b-44a2-a095-b723fa3daa52
    `external_id` VARCHAR(64) NULL COMMENT 'Fineract source column external_id',
    -- column_id: 7fa31155-c9a2-4e4e-8f15-a8f91d51e51f
    `client_id` BIGINT NULL COMMENT 'Fineract source column client_id',
    -- column_id: a27af037-a224-4ca1-9fce-cc1c65dd3e72
    `fund_id` BIGINT NULL COMMENT 'Fineract source column fund_id',
    -- column_id: a72090c3-9857-4b79-b061-8796ac812da0
    `product_id` BIGINT NOT NULL COMMENT 'Fineract source column product_id',
    -- column_id: 1843dc2c-5f38-405a-84c2-d573e6309833
    `submittedon_date` DATE NULL COMMENT 'Fineract source column submittedon_date',
    -- column_id: 492beb97-860c-4e1a-851d-cbcdeac1b094
    `rejectedon_date` DATE NULL COMMENT 'Fineract source column rejectedon_date',
    -- column_id: f90b6edc-7512-46de-99dc-d8b0a46e44ed
    `rejectedon_userid` BIGINT NULL COMMENT 'Fineract source column rejectedon_userid',
    -- column_id: 5f61c1d5-914f-4724-acc8-b63776886c9f
    `approvedon_date` DATE NULL COMMENT 'Fineract source column approvedon_date',
    -- column_id: 6a1cd4f2-a064-41f2-abf3-a32584cbbd4f
    `approvedon_userid` BIGINT NULL COMMENT 'Fineract source column approvedon_userid',
    -- column_id: da2521aa-3811-416d-bc78-83374a287c55
    `closedon_date` DATE NULL COMMENT 'Fineract source column closedon_date',
    -- column_id: 2e250943-ac19-46e5-b46c-f39cd1cfb0a8
    `closedon_userid` BIGINT NULL COMMENT 'Fineract source column closedon_userid',
    -- column_id: 4bb925d6-519e-4fac-8963-57d131052e4d
    `expected_maturedon_date` DATE NULL COMMENT 'Fineract source column expected_maturedon_date',
    -- column_id: 940149f4-97b7-4df5-858d-b1ce131e2759
    `maturedon_date` DATE NULL COMMENT 'Fineract source column maturedon_date',
    -- column_id: 91ad6872-b095-4d5f-9ece-f37a20a4fa98
    `principal_amount_proposed` DECIMAL(19,6) NOT NULL COMMENT 'Fineract source column principal_amount_proposed',
    -- column_id: 03ad0a37-56a8-4bee-af92-74908b414833
    `approved_principal` DECIMAL(19,6) NOT NULL COMMENT 'Fineract source column approved_principal',
    -- column_id: 883d9eab-a1da-4cba-a2f0-7382e0f28cb0
    `currency_code` VARCHAR(3) NULL COMMENT 'Fineract source column currency_code',
    -- column_id: cb77749d-1d08-4925-89fb-e7e95418fb98
    `currency_digits` SMALLINT NULL COMMENT 'Fineract source column currency_digits',
    -- column_id: de52c9dd-d540-4a90-beab-e7a76abd949a
    `currency_multiplesof` SMALLINT NULL COMMENT 'Fineract source column currency_multiplesof',
    -- column_id: 041135bb-3c00-44ea-b51e-4805f80d4cb2
    `principal_amount` DECIMAL(19,6) NULL COMMENT 'Fineract source column principal_amount',
    -- column_id: ecb59215-98ed-4a29-add3-ee8d0e3f2145
    `period_payment_rate` DECIMAL(19,6) NULL COMMENT 'Fineract source column period_payment_rate',
    -- column_id: ba28d02e-3493-4245-8ad0-976ace8de145
    `repayment_every` INT NULL COMMENT 'Fineract source column repayment_every',
    -- column_id: d566729c-72b1-4604-8bb3-6360dd3589d6
    `repayment_frequency_enum` VARCHAR(50) NULL COMMENT 'Fineract source column repayment_frequency_enum',
    -- column_id: b51b99c2-6a49-49d5-8c6c-f9c6057047ec
    `amortization_type` VARCHAR(50) NULL COMMENT 'Fineract source column amortization_type',
    -- column_id: a8cbb5b5-da3f-4824-aa26-49061a4244e9
    `npv_day_count` INT NULL COMMENT 'Fineract source column npv_day_count',
    -- column_id: be5db80b-8bec-4da0-b550-9086701126cb
    `discount` DECIMAL(19,6) NULL COMMENT 'Fineract source column discount',
    -- column_id: 06ac28fb-7604-4cd9-aff6-0c15e8b2f198
    `delinquency_bucket_classification_id` BIGINT NULL COMMENT 'Fineract source column delinquency_bucket_classification_id',
    -- column_id: 7b8a4f75-1ab8-438d-b65c-8593860bf303
    `loan_counter` INT NULL COMMENT 'Fineract source column loan_counter',
    -- column_id: 4fd657fc-b567-4963-b8ac-1445ee394cc2
    `loan_product_counter` INT NULL COMMENT 'Fineract source column loan_product_counter',
    -- column_id: 086ba73a-0b56-4e5d-aafa-6f8ba9962707
    `delinquency_grace_days` INT NULL COMMENT 'Fineract source column delinquency_grace_days',
    -- column_id: 40240e51-3317-48ec-956b-e4d34c62af92
    `delinquency_start_type` VARCHAR(20) NULL COMMENT 'Fineract source column delinquency_start_type',
    -- column_id: b0a81bf6-be87-4157-95eb-7d46be7042df
    `wc_loan_product_id` BIGINT NULL COMMENT 'Fineract source column wc_loan_product_id',
    -- column_id: 1d75d4ae-6783-403d-bcab-bf2c3af8e9c0
    `breach_id` BIGINT NULL COMMENT 'Fineract source column breach_id',
    -- column_id: 03a32bc4-f3b0-47e1-a2cc-c547bde5aa79
    `near_breach_id` BIGINT NULL COMMENT 'Fineract source column near_breach_id',
    -- column_id: 4e15e69e-323f-487c-b565-d22dde282ab7
    `discount_proposed` DECIMAL(19,6) NULL COMMENT 'Fineract source column discount_proposed',
    -- column_id: 638b83cf-087d-4363-92d3-14e36487e2bf
    `discount_approved` DECIMAL(19,6) NULL COMMENT 'Fineract source column discount_approved',
    -- column_id: 910a3f94-154a-4d4d-a96b-745d6829b7ed
    `total_payment_volume` DECIMAL(19,6) NULL COMMENT 'Fineract source column total_payment_volume',
    -- column_id: 89dd1b1f-4fd1-4e42-9b7b-2e5fe396fddc
    `breach_grace_days` INT NULL COMMENT 'Fineract source column breach_grace_days',
    -- column_id: 729becac-dc44-4bea-bf3e-2471cc7b386c
    `etl_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`, `snapshot_date`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
