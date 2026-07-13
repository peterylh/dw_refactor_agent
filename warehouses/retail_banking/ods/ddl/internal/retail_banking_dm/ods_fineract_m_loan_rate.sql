-- ODS mirror of Apache Fineract m_loan_rate (贷款与信贷)
DROP TABLE IF EXISTS retail_banking_dm.ods_fineract_m_loan_rate;
-- table_id: 96389107-4650-414c-9928-5c9a330a8070
CREATE TABLE IF NOT EXISTS retail_banking_dm.ods_fineract_m_loan_rate (
    -- column_id: fbe57933-60cc-4787-95bc-d40c5f7874fe
    `loan_id` BIGINT NOT NULL COMMENT 'Fineract source column loan_id',
    -- column_id: c8a6a64f-4275-4411-b871-797714d2f64e
    `rate_id` BIGINT NOT NULL COMMENT 'Fineract source column rate_id',
    -- column_id: d108c3bb-0db3-4dae-9b1c-000d9ce9039b
    `load_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`loan_id`, `rate_id`)
DISTRIBUTED BY HASH(`loan_id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
