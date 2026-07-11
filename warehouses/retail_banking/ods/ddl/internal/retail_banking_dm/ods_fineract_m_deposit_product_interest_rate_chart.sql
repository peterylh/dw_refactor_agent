-- ODS mirror of Apache Fineract m_deposit_product_interest_rate_chart (存款与储蓄)
DROP TABLE IF EXISTS retail_banking_dm.ods_fineract_m_deposit_product_interest_rate_chart;
-- table_id: da721278-246d-4bfd-a2d0-634aebdf5dcc
CREATE TABLE IF NOT EXISTS retail_banking_dm.ods_fineract_m_deposit_product_interest_rate_chart (
    -- column_id: e4d81473-49e0-4940-aa15-ff78a772191d
    `deposit_product_id` BIGINT NOT NULL COMMENT 'Fineract source column deposit_product_id',
    -- column_id: 1772672a-78ee-4ca0-8700-28e8f508d9b6
    `interest_rate_chart_id` BIGINT NOT NULL COMMENT 'Fineract source column interest_rate_chart_id',
    -- column_id: 0a4f83fa-4622-426c-9b40-6580b19b615c
    `load_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`deposit_product_id`)
DISTRIBUTED BY HASH(`deposit_product_id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
