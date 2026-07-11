-- ODS mirror of Apache Fineract m_client_charge_paid_by (客户与参与方)
DROP TABLE IF EXISTS retail_banking_dm.ods_fineract_m_client_charge_paid_by;
-- table_id: 0505a8b4-9b35-40c7-9505-ee7809c1bdc0
CREATE TABLE IF NOT EXISTS retail_banking_dm.ods_fineract_m_client_charge_paid_by (
    -- column_id: 99f1da5d-3855-4677-95d5-35cd990d028f
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: 5da89caa-d5e6-4bac-8bb1-0c84114f151c
    `client_transaction_id` BIGINT NOT NULL COMMENT 'Fineract source column client_transaction_id',
    -- column_id: 79d22dd2-3cfa-40c6-955e-c322ab3c9da3
    `client_charge_id` BIGINT NOT NULL COMMENT 'Fineract source column client_charge_id',
    -- column_id: f51f2945-ea96-48cc-a898-b8397dff2a27
    `amount` DECIMAL(19,6) NOT NULL COMMENT 'Fineract source column amount',
    -- column_id: 29fbb48a-434e-4d6d-879e-7ee8fa14495c
    `load_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
