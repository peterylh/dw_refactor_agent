-- ODS mirror of Apache Fineract m_savings_product_charge (存款与储蓄)
DROP TABLE IF EXISTS retail_banking_dm.ods_fineract_m_savings_product_charge;
-- table_id: aaf3146b-3b95-4156-877e-f8b0b885f943
CREATE TABLE IF NOT EXISTS retail_banking_dm.ods_fineract_m_savings_product_charge (
    -- column_id: 7c046d77-cd65-45e6-9978-489aecccabeb
    `savings_product_id` BIGINT NOT NULL COMMENT 'Fineract source column savings_product_id',
    -- column_id: ad62f90b-24b4-4b05-a40b-de92dd4fd3dd
    `charge_id` BIGINT NOT NULL COMMENT 'Fineract source column charge_id',
    -- column_id: 6faa971c-4e03-4013-9097-f20439c94d28
    `load_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`savings_product_id`, `charge_id`)
DISTRIBUTED BY HASH(`savings_product_id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
