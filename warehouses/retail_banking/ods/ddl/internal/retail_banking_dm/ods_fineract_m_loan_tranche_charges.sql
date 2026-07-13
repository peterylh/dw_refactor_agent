-- ODS mirror of Apache Fineract m_loan_tranche_charges (贷款与信贷)
DROP TABLE IF EXISTS retail_banking_dm.ods_fineract_m_loan_tranche_charges;
-- table_id: e7964fb0-086a-49c8-b315-470024dab929
CREATE TABLE IF NOT EXISTS retail_banking_dm.ods_fineract_m_loan_tranche_charges (
    -- column_id: 45608e90-ff7a-43d7-8378-e012a3f8fbf3
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: efaec21f-1908-41fb-82ff-ded5cb4f88d0
    `loan_id` BIGINT NOT NULL COMMENT 'Fineract source column loan_id',
    -- column_id: 40a057f7-92d0-499c-a79e-842ec84b656e
    `charge_id` BIGINT NOT NULL COMMENT 'Fineract source column charge_id',
    -- column_id: 5c0dc674-fff6-4ee5-9e6c-7d483d940fd9
    `load_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
