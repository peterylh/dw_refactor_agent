-- ODS mirror of Apache Fineract m_wc_loan_charge (营运资金贷款)
DROP TABLE IF EXISTS retail_banking_dm.ods_fineract_m_wc_loan_charge;
-- table_id: 5408076a-c2ce-4b63-9bec-5c47aa152937
CREATE TABLE IF NOT EXISTS retail_banking_dm.ods_fineract_m_wc_loan_charge (
    -- column_id: 514660f8-72b0-43ed-a7a3-c9f86f81a1b6
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: dd75292e-2828-46dc-9ce2-c54673600789
    `loan_id` BIGINT NOT NULL COMMENT 'Fineract source column loan_id',
    -- column_id: 38d158b7-532a-417a-bc54-c2777806df08
    `charge_id` BIGINT NOT NULL COMMENT 'Fineract source column charge_id',
    -- column_id: 641bce8d-ef2c-40d5-9188-dff3fd699b02
    `is_penalty` BOOLEAN NOT NULL COMMENT 'Fineract source column is_penalty',
    -- column_id: 46d3c66a-2ce1-42be-8f81-b4ed3c24723a
    `charge_time_type` SMALLINT NOT NULL COMMENT 'Fineract source column charge_time_type',
    -- column_id: befdbd95-49d9-454e-86eb-fd52e3d61fa9
    `charge_calculation_type` SMALLINT NOT NULL COMMENT 'Fineract source column charge_calculation_type',
    -- column_id: f7e1304f-912f-4064-b3e6-ac3f53a06509
    `charge_payment_mode` SMALLINT NOT NULL COMMENT 'Fineract source column charge_payment_mode',
    -- column_id: 6f425178-8b72-4b3a-b6e2-971118aba550
    `calculation_on_amount` DECIMAL(19,6) NULL COMMENT 'Fineract source column calculation_on_amount',
    -- column_id: bb0bf0fc-b1c2-4913-9714-02150379f7c7
    `amount_paid` DECIMAL(19,6) NULL COMMENT 'Fineract source column amount_paid',
    -- column_id: 1d375c44-1fb5-4e86-85b6-ac7760f2c664
    `amount` DECIMAL(19,6) NULL COMMENT 'Fineract source column amount',
    -- column_id: ca12e417-e6c1-4bfa-a89e-ae52e4f9ef73
    `is_paid` BOOLEAN NOT NULL COMMENT 'Fineract source column is_paid',
    -- column_id: a4c2b78a-8866-41e5-aab4-c937a368aad1
    `is_active` BOOLEAN NOT NULL COMMENT 'Fineract source column is_active',
    -- column_id: 370d5c1f-5f85-4623-8605-2e0455463538
    `due_date` DATE NULL COMMENT 'Fineract source column due_date',
    -- column_id: acec2eae-6b38-4165-a74c-c9d586c71d57
    `created_by` BIGINT NOT NULL COMMENT 'Fineract source column created_by',
    -- column_id: d949c9c3-b89c-437d-b821-8332077df750
    `last_modified_by` BIGINT NOT NULL COMMENT 'Fineract source column last_modified_by',
    -- column_id: 44fe2230-e149-4932-b8a9-9bd6a909c0f2
    `external_id` VARCHAR(100) NULL COMMENT 'Fineract source column external_id',
    -- column_id: 2fbcd361-c888-417c-b01d-650f5bc528ab
    `submitted_on_date` DATE NOT NULL COMMENT 'Fineract source column submitted_on_date',
    -- column_id: eb1d3db3-b1e8-4400-98bc-c201633040d8
    `created_on_utc` DATETIME NOT NULL COMMENT 'Fineract source column created_on_utc',
    -- column_id: 143150a4-2281-436e-9adf-f49ff069d4f4
    `last_modified_on_utc` DATETIME NOT NULL COMMENT 'Fineract source column last_modified_on_utc',
    -- column_id: 85699b3b-0e67-4dfc-9478-a1a342caba87
    `load_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
