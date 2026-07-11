-- ODS mirror of Apache Fineract m_product_loan_rate (贷款与信贷)
DROP TABLE IF EXISTS retail_banking_dm.ods_fineract_m_product_loan_rate;
-- table_id: a6304bdc-47ab-4066-8e0b-76293363dab7
CREATE TABLE IF NOT EXISTS retail_banking_dm.ods_fineract_m_product_loan_rate (
    -- column_id: 72b187d4-558c-4bdf-8c74-9157c6d36203
    `product_loan_id` BIGINT NOT NULL COMMENT 'Fineract source column product_loan_id',
    -- column_id: 3363d651-fa28-4ac6-9082-c653806164ad
    `rate_id` BIGINT NOT NULL COMMENT 'Fineract source column rate_id',
    -- column_id: 55b70f54-b885-4ecc-85ca-6a39532a9300
    `load_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`product_loan_id`, `rate_id`)
DISTRIBUTED BY HASH(`product_loan_id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
