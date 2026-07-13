-- ODS mirror of Apache Fineract m_share_account (投资、份额与资产持有)
DROP TABLE IF EXISTS retail_banking_dm.ods_fineract_m_share_account;
-- table_id: c80f215c-6b5d-46cd-b353-96af01ddf74f
CREATE TABLE IF NOT EXISTS retail_banking_dm.ods_fineract_m_share_account (
    -- column_id: 28876540-0823-4f85-a851-43028f6480b7
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: 998ef77e-0c2d-4f71-8fcf-24cb8c39c9b3
    `account_no` VARCHAR(50) NOT NULL COMMENT 'Fineract source column account_no',
    -- column_id: 2c5d5716-9d52-47cb-a423-e158485eed76
    `product_id` BIGINT NOT NULL COMMENT 'Fineract source column product_id',
    -- column_id: 350da534-151c-43a5-96a3-786ec5751b8c
    `client_id` BIGINT NOT NULL COMMENT 'Fineract source column client_id',
    -- column_id: c412431b-779a-4f89-ab77-2c3661b0c12a
    `external_id` VARCHAR(100) NULL COMMENT 'Fineract source column external_id',
    -- column_id: bc82b25e-5e2e-49e0-b63f-8704f2f2a0ff
    `status_enum` SMALLINT NOT NULL COMMENT 'Fineract source column status_enum',
    -- column_id: df58ac84-df58-4b64-811b-d95d714b85e6
    `total_approved_shares` BIGINT NULL COMMENT 'Fineract source column total_approved_shares',
    -- column_id: c7c0ae41-26e6-4bf5-b5b6-2d9e0fe7f341
    `total_pending_shares` BIGINT NULL COMMENT 'Fineract source column total_pending_shares',
    -- column_id: f4c916d8-280b-478c-9506-2caef18e7f9e
    `submitted_date` DATE NOT NULL COMMENT 'Fineract source column submitted_date',
    -- column_id: 2dce9fde-6315-4307-9529-9dacd36782af
    `submitted_userid` BIGINT NULL COMMENT 'Fineract source column submitted_userid',
    -- column_id: fa5c1d05-62c5-4286-8b5f-feb77a5bc8b0
    `approved_date` DATE NULL COMMENT 'Fineract source column approved_date',
    -- column_id: c5cf07d6-b962-45de-a04c-5ef833e632d7
    `approved_userid` BIGINT NULL COMMENT 'Fineract source column approved_userid',
    -- column_id: 119ba2b4-4af4-4f3c-a7ce-91be9175eb04
    `rejected_date` DATE NULL COMMENT 'Fineract source column rejected_date',
    -- column_id: 1af5654f-68c4-4578-aa19-71530f9423e1
    `rejected_userid` BIGINT NULL COMMENT 'Fineract source column rejected_userid',
    -- column_id: 72dd25af-ee77-49d8-9668-7d55a156eff1
    `activated_date` DATE NULL COMMENT 'Fineract source column activated_date',
    -- column_id: 01ee9683-cac5-41c7-b9d2-ef474c055511
    `activated_userid` BIGINT NULL COMMENT 'Fineract source column activated_userid',
    -- column_id: c7aca5e5-0182-4a11-85ac-a9c3a060f816
    `closed_date` DATE NULL COMMENT 'Fineract source column closed_date',
    -- column_id: 834fa3d1-c2a2-4be4-819c-44a4f57d0432
    `closed_userid` BIGINT NULL COMMENT 'Fineract source column closed_userid',
    -- column_id: f829b6ae-2147-421a-9da3-b9d811d6a4e1
    `currency_code` VARCHAR(3) NOT NULL COMMENT 'Fineract source column currency_code',
    -- column_id: 0ecd4070-de62-400a-89f3-c81c5be7491c
    `currency_digits` SMALLINT NOT NULL COMMENT 'Fineract source column currency_digits',
    -- column_id: faa1a799-11ca-46ea-8b66-227ac87b7be1
    `currency_multiplesof` SMALLINT NULL COMMENT 'Fineract source column currency_multiplesof',
    -- column_id: 524eb781-88e5-4db6-b54e-b460a0198b0d
    `savings_account_id` BIGINT NOT NULL COMMENT 'Fineract source column savings_account_id',
    -- column_id: 6b1750bb-c756-4c4a-88e5-509776b34621
    `minimum_active_period_frequency` DECIMAL(19,6) NULL COMMENT 'Fineract source column minimum_active_period_frequency',
    -- column_id: 5e11b353-68a5-46b9-9bb5-09152c4480f2
    `minimum_active_period_frequency_enum` SMALLINT NULL COMMENT 'Fineract source column minimum_active_period_frequency_enum',
    -- column_id: 1fce87bc-04ed-41a2-8d40-cd4cfd74f33a
    `lockin_period_frequency` DECIMAL(19,6) NULL COMMENT 'Fineract source column lockin_period_frequency',
    -- column_id: 4bcbee14-6ddd-4333-b189-6a3a8a433b63
    `lockin_period_frequency_enum` SMALLINT NULL COMMENT 'Fineract source column lockin_period_frequency_enum',
    -- column_id: 2f290900-9cac-439e-b46a-49486d4dc7b1
    `allow_dividends_inactive_clients` BOOLEAN NULL COMMENT 'Fineract source column allow_dividends_inactive_clients',
    -- column_id: d09bedc3-e294-432d-9997-cf224de0a686
    `created_date` DATETIME NULL COMMENT 'Fineract source column created_date',
    -- column_id: 3bd3be7e-8681-4d11-87f2-d5341d6adc31
    `lastmodifiedby_id` BIGINT NULL COMMENT 'Fineract source column lastmodifiedby_id',
    -- column_id: d457216a-330d-4417-a2e7-e09aba0c4d8b
    `lastmodified_date` DATETIME NULL COMMENT 'Fineract source column lastmodified_date',
    -- column_id: e2572f9e-f2df-475d-9bae-f75dc59a6c5e
    `load_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
