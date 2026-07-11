-- ODS mirror of Apache Fineract m_share_product_charge (投资、份额与资产持有)
DROP TABLE IF EXISTS retail_banking_dm.ods_fineract_m_share_product_charge;
-- table_id: d933803c-8716-429a-b526-49e3bcbf69c5
CREATE TABLE IF NOT EXISTS retail_banking_dm.ods_fineract_m_share_product_charge (
    -- column_id: fcd1841c-8825-42c5-a783-66efd60e8bb0
    `product_id` BIGINT NOT NULL COMMENT 'Fineract source column product_id',
    -- column_id: 09432853-df40-42ee-8f81-f59d1cc7e193
    `charge_id` BIGINT NOT NULL COMMENT 'Fineract source column charge_id',
    -- column_id: 72e04133-f383-41ac-8481-fed1a97aad53
    `load_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`product_id`, `charge_id`)
DISTRIBUTED BY HASH(`product_id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
