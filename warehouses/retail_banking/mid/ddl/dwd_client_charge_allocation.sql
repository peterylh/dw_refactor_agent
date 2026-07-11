-- DWD generated from m_client_charge_paid_by
DROP TABLE IF EXISTS retail_banking_dm.dwd_client_charge_allocation;
-- table_id: 4c86a894-e5bb-4711-94c4-0ec9648e61b7
CREATE TABLE IF NOT EXISTS retail_banking_dm.dwd_client_charge_allocation (
    -- column_id: 2faa11b0-f809-4153-b307-e1f3b1203b9e
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: eb46ff6b-51b9-4892-83b6-432c7b7e1165
    `client_transaction_id` BIGINT NOT NULL COMMENT 'Fineract source column client_transaction_id',
    -- column_id: 945cbb5f-d05c-4cbd-8772-401cf6b18702
    `client_charge_id` BIGINT NOT NULL COMMENT 'Fineract source column client_charge_id',
    -- column_id: 0625ddab-5fce-409d-86cd-5718768168ed
    `amount` DECIMAL(19,6) NOT NULL COMMENT 'Fineract source column amount',
    -- column_id: 6259c5da-5faf-4a2e-9bc6-a634eae307c5
    `business_date` DATE NULL COMMENT 'Standardized business date from the semantic spec',
    -- column_id: 9d85e93a-d12a-497d-a033-9067b2dbdd41
    `etl_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
