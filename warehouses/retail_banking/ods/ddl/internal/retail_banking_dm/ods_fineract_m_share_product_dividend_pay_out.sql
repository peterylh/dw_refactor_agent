-- ODS mirror of Apache Fineract m_share_product_dividend_pay_out (投资、份额与资产持有)
DROP TABLE IF EXISTS retail_banking_dm.ods_fineract_m_share_product_dividend_pay_out;
-- table_id: a527fe7c-9fe2-4444-beba-c5e77e4e639b
CREATE TABLE IF NOT EXISTS retail_banking_dm.ods_fineract_m_share_product_dividend_pay_out (
    -- column_id: 0ef80091-f484-489b-afc5-f69a0cdcbde3
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: 76fae89e-b4db-4e6f-8aed-3d928dda090a
    `product_id` BIGINT NOT NULL COMMENT 'Fineract source column product_id',
    -- column_id: 3f0115dc-a86b-4e6b-b508-edf65f8da636
    `amount` DECIMAL(19,6) NOT NULL COMMENT 'Fineract source column amount',
    -- column_id: 5d2cabec-5b49-43ca-9db0-49d01df4ca87
    `dividend_period_start_date` DATE NOT NULL COMMENT 'Fineract source column dividend_period_start_date',
    -- column_id: 22a9b082-3555-4d1c-b338-aed82a030ae1
    `dividend_period_end_date` DATE NOT NULL COMMENT 'Fineract source column dividend_period_end_date',
    -- column_id: 93ddeae2-4c1a-4230-a728-234319ff956b
    `status` SMALLINT NOT NULL COMMENT 'Fineract source column status',
    -- column_id: 006c1260-1ebb-4188-a6fe-3d39d02ce509
    `createdby_id` BIGINT NULL COMMENT 'Fineract source column createdby_id',
    -- column_id: e475f870-183d-45fe-9c55-389bd3f3893d
    `created_date` DATETIME NULL COMMENT 'Fineract source column created_date',
    -- column_id: 22dab742-08db-4eb6-8d95-aae039ce0891
    `lastmodifiedby_id` BIGINT NULL COMMENT 'Fineract source column lastmodifiedby_id',
    -- column_id: 1e535977-de9f-41ad-9700-3ba8ae30fb93
    `lastmodified_date` DATETIME NULL COMMENT 'Fineract source column lastmodified_date',
    -- column_id: 3fa4b110-c327-4cb8-83a7-501d41993fa9
    `load_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
