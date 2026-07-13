-- DIM generated from acc_product_mapping
DROP TABLE IF EXISTS retail_banking_dm.bridge_product_gl_mapping;
-- table_id: bd015903-4be2-491c-b8aa-84244080472c
CREATE TABLE IF NOT EXISTS retail_banking_dm.bridge_product_gl_mapping (
    -- column_id: feef0b10-d172-46dd-b799-9af353e1befa
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: 025ba9e4-0aec-4369-92af-8cd65764463f
    `gl_account_id` BIGINT NULL COMMENT 'Fineract source column gl_account_id',
    -- column_id: acbe4f65-6637-44e2-b262-569e1fc762cf
    `product_id` BIGINT NULL COMMENT 'Fineract source column product_id',
    -- column_id: fa33cc3f-11e3-4f19-87c0-9777eabc64f2
    `product_type` SMALLINT NULL COMMENT 'Fineract source column product_type',
    -- column_id: 04613db5-6006-46e8-82e8-a2763c40bc20
    `payment_type` INT NULL COMMENT 'Fineract source column payment_type',
    -- column_id: 6a3b450b-f96c-4a79-8060-7feb8c219aa5
    `charge_id` BIGINT NULL COMMENT 'Fineract source column charge_id',
    -- column_id: 929f16bc-9af4-46fa-9733-c17a2967e01f
    `financial_account_type` SMALLINT NULL COMMENT 'Fineract source column financial_account_type',
    -- column_id: cf91c163-13c0-49bd-bdb6-a4f0f7a1fbe5
    `charge_off_reason_id` INT NULL COMMENT 'Fineract source column charge_off_reason_id',
    -- column_id: fcbb5b3a-3684-4d52-9d15-a63e3057f813
    `capitalized_income_classification_id` INT NULL COMMENT 'Fineract source column capitalized_income_classification_id',
    -- column_id: 1f701c74-5ef0-4465-85ec-a31bdef53056
    `buydown_fee_classification_id` INT NULL COMMENT 'Fineract source column buydown_fee_classification_id',
    -- column_id: 3f2e97e9-c9b9-467e-b6ca-a039961fd4d6
    `write_off_reason_id` BIGINT NULL COMMENT 'Fineract source column write_off_reason_id',
    -- column_id: 569fd2b6-5e9a-4d0c-acf8-8186d4514d97
    `etl_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
