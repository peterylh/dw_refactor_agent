-- ODS mirror of Apache Fineract m_client_transfer_details (客户与参与方)
DROP TABLE IF EXISTS retail_banking_dm.ods_fineract_m_client_transfer_details;
-- table_id: 89e77e93-0098-4005-9cda-d7ece67de1c5
CREATE TABLE IF NOT EXISTS retail_banking_dm.ods_fineract_m_client_transfer_details (
    -- column_id: 5acd0418-0ed2-4266-af81-ea8235067c83
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: ac6d5295-a477-4739-8e73-b35ba95faa88
    `client_id` BIGINT NOT NULL COMMENT 'Fineract source column client_id',
    -- column_id: 984a4b55-4be2-4ece-8e36-f743d8b393b8
    `from_office_id` BIGINT NOT NULL COMMENT 'Fineract source column from_office_id',
    -- column_id: 5f10cab0-bf50-454e-93f6-c5a88b38740c
    `to_office_id` BIGINT NOT NULL COMMENT 'Fineract source column to_office_id',
    -- column_id: 3a0f6ead-2972-4a17-bd55-840f9a4bc7c2
    `proposed_transfer_date` DATE NULL COMMENT 'Fineract source column proposed_transfer_date',
    -- column_id: 0d455121-1558-4378-9fd6-48bf99c988e5
    `transfer_type` TINYINT NOT NULL COMMENT 'Fineract source column transfer_type',
    -- column_id: 30fefb03-72a8-4329-90f4-86dfdba62d9d
    `submitted_on` DATE NOT NULL COMMENT 'Fineract source column submitted_on',
    -- column_id: 46e971a6-e1e0-4576-b444-36080931d50f
    `submitted_by` BIGINT NOT NULL COMMENT 'Fineract source column submitted_by',
    -- column_id: 0b0eb715-ef57-4a41-b212-d61374b13f36
    `load_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
