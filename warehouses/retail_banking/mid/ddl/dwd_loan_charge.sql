SET allow_partition_column_nullable = true;

-- DWD generated from m_loan_charge
DROP TABLE IF EXISTS retail_banking_dm.dwd_loan_charge;
-- table_id: f9b39bfd-f83f-4597-bfb4-5339d3da7882
CREATE TABLE IF NOT EXISTS retail_banking_dm.dwd_loan_charge (
    -- column_id: 5d186f6d-4eb2-4272-b96a-96a328e34b8b
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: a3019a70-d756-434e-a963-64c3d9752d42
    `business_date` DATE NULL COMMENT 'Standardized business date from the semantic spec',
    -- column_id: aced73c2-1634-44b2-8fc4-2f6905f3664b
    `loan_id` BIGINT NOT NULL COMMENT 'Fineract source column loan_id',
    -- column_id: b2fb407a-9c9a-4be0-b926-e54a58e8e872
    `charge_id` BIGINT NOT NULL COMMENT 'Fineract source column charge_id',
    -- column_id: 4c5c2b02-1cd9-414f-8571-566eb07562c2
    `is_penalty` BOOLEAN NOT NULL COMMENT 'Fineract source column is_penalty',
    -- column_id: bea24e68-059d-4ecd-8c50-5b2212507716
    `charge_time_enum` SMALLINT NOT NULL COMMENT 'Fineract source column charge_time_enum',
    -- column_id: f8c3962d-dd22-4bbb-aece-7d147b7fc78e
    `due_for_collection_as_of_date` DATE NULL COMMENT 'Fineract source column due_for_collection_as_of_date',
    -- column_id: a164fe75-7bd9-464c-9da3-f0e190097220
    `charge_calculation_enum` SMALLINT NOT NULL COMMENT 'Fineract source column charge_calculation_enum',
    -- column_id: dee2e6ad-e98e-4e9d-912a-e9f7a616084e
    `charge_payment_mode_enum` SMALLINT NOT NULL COMMENT 'Fineract source column charge_payment_mode_enum',
    -- column_id: f0f43ce4-4a4b-4a35-b3f2-64e29dec4cc2
    `calculation_percentage` DECIMAL(19,6) NULL COMMENT 'Fineract source column calculation_percentage',
    -- column_id: fd350a51-c364-4d3b-ae7c-a758ca1a54cd
    `calculation_on_amount` DECIMAL(19,6) NULL COMMENT 'Fineract source column calculation_on_amount',
    -- column_id: b6019fe2-f0fb-4d86-bac5-b18bc11bdc20
    `charge_amount_or_percentage` DECIMAL(19,6) NULL COMMENT 'Fineract source column charge_amount_or_percentage',
    -- column_id: 0d34fb06-a474-4712-b7f5-2b0e693ff6e8
    `amount` DECIMAL(19,6) NOT NULL COMMENT 'Fineract source column amount',
    -- column_id: 50ef6ad2-a4b2-43b2-ae8c-22c76f7de422
    `amount_paid_derived` DECIMAL(19,6) NULL COMMENT 'Fineract source column amount_paid_derived',
    -- column_id: ad5de505-dd1d-42b5-95a6-3d148b1c8c20
    `amount_waived_derived` DECIMAL(19,6) NULL COMMENT 'Fineract source column amount_waived_derived',
    -- column_id: d93c9bc2-0354-4ae1-85b6-835b83c5d37d
    `amount_writtenoff_derived` DECIMAL(19,6) NULL COMMENT 'Fineract source column amount_writtenoff_derived',
    -- column_id: a901d21b-7a1f-4b81-830e-f14905967f1f
    `amount_outstanding_derived` DECIMAL(19,6) NOT NULL COMMENT 'Fineract source column amount_outstanding_derived',
    -- column_id: ed511795-2b54-4dc5-a59b-37888a34c900
    `is_paid_derived` BOOLEAN NOT NULL COMMENT 'Fineract source column is_paid_derived',
    -- column_id: 59b6e156-3dc4-46cf-95c2-e63fc07df143
    `waived` BOOLEAN NOT NULL COMMENT 'Fineract source column waived',
    -- column_id: b95bb9e6-9320-4ae1-9864-e9ec5332d5f7
    `min_cap` DECIMAL(19,6) NULL COMMENT 'Fineract source column min_cap',
    -- column_id: b7c2dc00-8564-4b1f-8dd9-6ed82d4aa932
    `max_cap` DECIMAL(19,6) NULL COMMENT 'Fineract source column max_cap',
    -- column_id: 289504d7-0d06-45f1-9ee8-7e4517803b63
    `is_active` BOOLEAN NOT NULL COMMENT 'Fineract source column is_active',
    -- column_id: 7c6dc848-43a3-4425-8b6f-3e5eff152bab
    `external_id` VARCHAR(64) NULL COMMENT 'Fineract source column external_id',
    -- column_id: 74054725-b579-4ab9-9b21-e7cb6112a9af
    `submitted_on_date` DATE NULL COMMENT 'Fineract source column submitted_on_date',
    -- column_id: 9b3baaf7-dacb-4a9f-b2f6-e7f116a0fe7f
    `created_on_utc` DATETIME NOT NULL COMMENT 'Fineract source column created_on_utc',
    -- column_id: c9fa0795-49f3-423d-a567-856a67d4f3e0
    `last_modified_on_utc` DATETIME NOT NULL COMMENT 'Fineract source column last_modified_on_utc',
    -- column_id: d06ff5c0-fbd1-49f6-915d-099d147cd26a
    `created_by` BIGINT NOT NULL COMMENT 'Fineract source column created_by',
    -- column_id: acd26c83-4645-44a7-bfb0-c6193cdc40d6
    `last_modified_by` BIGINT NOT NULL COMMENT 'Fineract source column last_modified_by',
    -- column_id: 10af08fb-5e3f-4a31-8ffc-ca9d202b7ce5
    `tax_amount` DECIMAL(19,6) NULL COMMENT 'Fineract source column tax_amount',
    -- column_id: 7669337d-31b7-4a75-9820-5b3dd7ec3057
    `etl_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`, `business_date`)
AUTO PARTITION BY LIST (`business_date`) ()
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
