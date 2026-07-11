-- ODS mirror of Apache Fineract m_wc_loan (营运资金贷款)
DROP TABLE IF EXISTS retail_banking_dm.ods_fineract_m_wc_loan;
-- table_id: 02e95c76-ea71-4a8c-bec6-9269097efaeb
CREATE TABLE IF NOT EXISTS retail_banking_dm.ods_fineract_m_wc_loan (
    -- column_id: 13a20b00-a809-4a26-a871-b72a2b7e0f7b
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: f4ec6049-e55f-42a6-9240-0956213a4431
    `version` INT NOT NULL COMMENT 'Fineract source column version',
    -- column_id: c8e23fdc-b1a6-40dd-9c90-f34a563245bb
    `created_by` BIGINT NOT NULL COMMENT 'Fineract source column created_by',
    -- column_id: f12470eb-c7f7-4dae-b9dd-d71c217455de
    `last_modified_by` BIGINT NOT NULL COMMENT 'Fineract source column last_modified_by',
    -- column_id: cf99de0e-6a49-4a6f-8f7a-497860f28449
    `created_on_utc` DATETIME NOT NULL COMMENT 'Fineract source column created_on_utc',
    -- column_id: 3c95d91d-e2ac-425d-9d6f-332d78f07036
    `last_modified_on_utc` DATETIME NOT NULL COMMENT 'Fineract source column last_modified_on_utc',
    -- column_id: 96fc51a3-a4f3-440f-a656-896655088e6d
    `loan_status_id` SMALLINT NOT NULL COMMENT 'Fineract source column loan_status_id',
    -- column_id: eb8ac5c8-c20e-4c79-8ba8-03a1c6237db9
    `last_closed_business_date` DATE NULL COMMENT 'Fineract source column last_closed_business_date',
    -- column_id: 19563f31-91b6-4c4e-8b68-269c0b7e96c4
    `account_no` VARCHAR(20) NOT NULL COMMENT 'Fineract source column account_no',
    -- column_id: 9ad79fe2-146e-40f1-8eff-42c1085630c3
    `external_id` VARCHAR(100) NULL COMMENT 'Fineract source column external_id',
    -- column_id: b337bf09-7c4d-4a1d-bc7c-1417094f7328
    `client_id` BIGINT NULL COMMENT 'Fineract source column client_id',
    -- column_id: 174386a2-da56-4db7-9e5f-9ce64d3c2e91
    `fund_id` BIGINT NULL COMMENT 'Fineract source column fund_id',
    -- column_id: c9c51060-15b1-452b-87c8-9624162cb564
    `product_id` BIGINT NOT NULL COMMENT 'Fineract source column product_id',
    -- column_id: 72696e6f-009c-4b74-8426-e1f6349adece
    `submittedon_date` DATE NULL COMMENT 'Fineract source column submittedon_date',
    -- column_id: deddcfb3-1093-4ea8-919c-1b1f0be1056a
    `rejectedon_date` DATE NULL COMMENT 'Fineract source column rejectedon_date',
    -- column_id: 339dfb06-38ea-4598-99f3-bf334dd79d8d
    `rejectedon_userid` BIGINT NULL COMMENT 'Fineract source column rejectedon_userid',
    -- column_id: 706d60eb-6cab-4146-8fb7-2dd90b177a0f
    `approvedon_date` DATE NULL COMMENT 'Fineract source column approvedon_date',
    -- column_id: 0b03542c-dba0-4dd6-9f21-d634ca68a65d
    `approvedon_userid` BIGINT NULL COMMENT 'Fineract source column approvedon_userid',
    -- column_id: eff95637-e361-45a0-8347-269ccf549210
    `closedon_date` DATE NULL COMMENT 'Fineract source column closedon_date',
    -- column_id: 889b14f9-8a6e-4e9e-a6aa-d341f7df7edd
    `closedon_userid` BIGINT NULL COMMENT 'Fineract source column closedon_userid',
    -- column_id: 12669be1-cf44-4e38-aa69-1e45dcaf91c4
    `expected_maturedon_date` DATE NULL COMMENT 'Fineract source column expected_maturedon_date',
    -- column_id: 927c1082-83a0-4f98-9690-9f385a10159c
    `maturedon_date` DATE NULL COMMENT 'Fineract source column maturedon_date',
    -- column_id: 59fd6bb6-dfc8-4cf4-b634-7fd1b8ebc6c5
    `principal_amount_proposed` DECIMAL(19,6) NOT NULL COMMENT 'Fineract source column principal_amount_proposed',
    -- column_id: 9a7d95f7-5725-4258-a054-23f904ec503e
    `approved_principal` DECIMAL(19,6) NOT NULL COMMENT 'Fineract source column approved_principal',
    -- column_id: 6acd34f6-3572-4e2d-8e24-2223e9293dbc
    `currency_code` VARCHAR(3) NULL COMMENT 'Fineract source column currency_code',
    -- column_id: 6f87cb89-6f7e-44fc-881d-dadb12c53bee
    `currency_digits` SMALLINT NULL COMMENT 'Fineract source column currency_digits',
    -- column_id: b3b691e3-307a-45a8-85ee-3ac7496a8fc8
    `currency_multiplesof` SMALLINT NULL COMMENT 'Fineract source column currency_multiplesof',
    -- column_id: 0b89c966-8ba6-481e-b9f7-03352026970a
    `principal_amount` DECIMAL(19,6) NULL COMMENT 'Fineract source column principal_amount',
    -- column_id: ae7a3c67-f6f1-4691-ae1d-2e789cae266c
    `period_payment_rate` DECIMAL(19,6) NULL COMMENT 'Fineract source column period_payment_rate',
    -- column_id: f314af41-2e05-46ec-a92f-62d71270ca66
    `repayment_every` INT NULL COMMENT 'Fineract source column repayment_every',
    -- column_id: bab69975-05eb-4c66-ab9f-1b049ca90f4e
    `repayment_frequency_enum` VARCHAR(50) NULL COMMENT 'Fineract source column repayment_frequency_enum',
    -- column_id: c86709c1-a278-41b5-83da-6c9346eacaa8
    `amortization_type` VARCHAR(50) NULL COMMENT 'Fineract source column amortization_type',
    -- column_id: 34274079-6a4c-431a-8f5b-3464aece1aee
    `npv_day_count` INT NULL COMMENT 'Fineract source column npv_day_count',
    -- column_id: e644d8aa-c325-4bf2-b342-256d13a77cb1
    `discount` DECIMAL(19,6) NULL COMMENT 'Fineract source column discount',
    -- column_id: 4058ca90-b417-461d-91a4-a02cba15d3c1
    `delinquency_bucket_classification_id` BIGINT NULL COMMENT 'Fineract source column delinquency_bucket_classification_id',
    -- column_id: 6bf400d4-052c-4964-9b12-3e2b761e4d76
    `loan_counter` INT NULL COMMENT 'Fineract source column loan_counter',
    -- column_id: 4f26d9ca-45ae-490e-9e38-f6f45a7680a1
    `loan_product_counter` INT NULL COMMENT 'Fineract source column loan_product_counter',
    -- column_id: 18d3b937-3f61-4f78-95ec-5ab5228f0be9
    `delinquency_grace_days` INT NULL COMMENT 'Fineract source column delinquency_grace_days',
    -- column_id: 9b5feccc-9579-4eef-b842-be9c0623da71
    `delinquency_start_type` VARCHAR(20) NULL COMMENT 'Fineract source column delinquency_start_type',
    -- column_id: 0b19ea84-ae3d-4e9c-86e3-8fe131c072ca
    `wc_loan_product_id` BIGINT NULL COMMENT 'Fineract source column wc_loan_product_id',
    -- column_id: feead2b0-010c-41f8-b7de-72a2cdc53f05
    `breach_id` BIGINT NULL COMMENT 'Fineract source column breach_id',
    -- column_id: 461d15af-ebb8-41f6-b639-5781134bd50c
    `near_breach_id` BIGINT NULL COMMENT 'Fineract source column near_breach_id',
    -- column_id: 73bc4854-2b78-4e09-a764-3afa1c4ca6b3
    `discount_proposed` DECIMAL(19,6) NULL COMMENT 'Fineract source column discount_proposed',
    -- column_id: 4333cf77-01f4-4cf9-bd45-b0c615725286
    `discount_approved` DECIMAL(19,6) NULL COMMENT 'Fineract source column discount_approved',
    -- column_id: d3bc11ea-9ca0-4f28-b228-ef638b03d251
    `total_payment_volume` DECIMAL(19,6) NULL COMMENT 'Fineract source column total_payment_volume',
    -- column_id: 0fad7aa1-02ff-4f86-a9b4-dc862dab6256
    `breach_grace_days` INT NULL COMMENT 'Fineract source column breach_grace_days',
    -- column_id: 36553476-1fac-4392-acba-1d7393fd7b1a
    `load_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
