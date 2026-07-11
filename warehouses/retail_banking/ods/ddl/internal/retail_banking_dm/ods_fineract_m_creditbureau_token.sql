-- ODS mirror of Apache Fineract m_creditbureau_token (贷款与信贷)
DROP TABLE IF EXISTS retail_banking_dm.ods_fineract_m_creditbureau_token;
-- table_id: cefcfb3d-fa5b-4863-9394-773762b11e44
CREATE TABLE IF NOT EXISTS retail_banking_dm.ods_fineract_m_creditbureau_token (
    -- column_id: 19c83451-4813-4eed-84d6-2f8a0378a789
    `id` INT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: 1aafdbb9-f07c-45bd-b5b0-e285b82f4452
    `username` VARCHAR(128) NULL COMMENT 'Fineract source column username',
    -- column_id: 24c2cdfa-0191-4d97-9226-36dafb407289
    `token` STRING NULL COMMENT 'Fineract source column token',
    -- column_id: e69d461f-e02b-4caa-bd53-f9cb1fafea0c
    `token_type` VARCHAR(128) NULL COMMENT 'Fineract source column token_type',
    -- column_id: 92c46607-93e2-4f8e-83a9-f19c18e1bb34
    `expires_in` VARCHAR(128) NULL COMMENT 'Fineract source column expires_in',
    -- column_id: 9d096405-641e-46e1-b6b0-293d0bb4b96f
    `issued` VARCHAR(128) NULL COMMENT 'Fineract source column issued',
    -- column_id: e060e750-6e4c-425f-a2c0-7e6092b065bd
    `expiry_date` DATE NULL COMMENT 'Fineract source column expiry_date',
    -- column_id: 3c9551d1-7a6f-4a72-9bf8-ee511016f07c
    `load_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
