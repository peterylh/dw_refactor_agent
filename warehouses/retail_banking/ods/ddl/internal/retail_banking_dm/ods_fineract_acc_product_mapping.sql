-- ODS mirror of Apache Fineract acc_product_mapping (总账与财务)
DROP TABLE IF EXISTS retail_banking_dm.ods_fineract_acc_product_mapping;
-- table_id: 3897ab20-9db9-4762-a01a-44e2eede5122
CREATE TABLE IF NOT EXISTS retail_banking_dm.ods_fineract_acc_product_mapping (
    -- column_id: 34e19c60-05ee-4071-9053-ffc313299ed5
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: f927e591-87b3-44de-8e23-51d0acd1ca50
    `gl_account_id` BIGINT NULL COMMENT 'Fineract source column gl_account_id',
    -- column_id: 09dae411-3af7-4cbf-a45c-a8e676dbe789
    `product_id` BIGINT NULL COMMENT 'Fineract source column product_id',
    -- column_id: e5679b71-9d6d-441b-b7e9-6b161d8e2dbd
    `product_type` SMALLINT NULL COMMENT 'Fineract source column product_type',
    -- column_id: d843b50e-37a5-4788-8311-4606847ae457
    `payment_type` INT NULL COMMENT 'Fineract source column payment_type',
    -- column_id: ebdc7f32-2101-4ee4-8bcb-2093922ef77b
    `charge_id` BIGINT NULL COMMENT 'Fineract source column charge_id',
    -- column_id: 69ba3705-64aa-4187-a696-b6fefb481a65
    `financial_account_type` SMALLINT NULL COMMENT 'Fineract source column financial_account_type',
    -- column_id: 711b49a9-dd07-4de2-af24-575287c01928
    `charge_off_reason_id` INT NULL COMMENT 'Fineract source column charge_off_reason_id',
    -- column_id: 521ccdf1-8718-4e0e-aafa-9eb4e6805682
    `capitalized_income_classification_id` INT NULL COMMENT 'Fineract source column capitalized_income_classification_id',
    -- column_id: b72857b1-7645-4a5e-8cb9-28f97c6adc4e
    `buydown_fee_classification_id` INT NULL COMMENT 'Fineract source column buydown_fee_classification_id',
    -- column_id: a39dbee7-0b7f-4fd1-918c-530a1bc76683
    `write_off_reason_id` BIGINT NULL COMMENT 'Fineract source column write_off_reason_id',
    -- column_id: 7da9fe4d-7552-4765-b9b5-c6ea0eea00a8
    `load_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
