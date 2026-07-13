-- ODS mirror of Apache Fineract m_product_loan_charge (贷款与信贷)
DROP TABLE IF EXISTS retail_banking_dm.ods_fineract_m_product_loan_charge;
-- table_id: 2c705dee-f599-4ef5-8af1-87a64b890db5
CREATE TABLE IF NOT EXISTS retail_banking_dm.ods_fineract_m_product_loan_charge (
    -- column_id: da82b753-22b3-4769-9a35-a5d607c501f6
    `product_loan_id` BIGINT NOT NULL COMMENT 'Fineract source column product_loan_id',
    -- column_id: 5d3675fd-d00c-41a5-83d8-35be6be6766b
    `charge_id` BIGINT NOT NULL COMMENT 'Fineract source column charge_id',
    -- column_id: 7393b016-d228-4054-8a0a-8ee74a35108a
    `load_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`product_loan_id`, `charge_id`)
DISTRIBUTED BY HASH(`product_loan_id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
