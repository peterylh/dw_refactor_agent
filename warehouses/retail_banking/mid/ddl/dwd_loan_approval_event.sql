-- DWD generated from m_loan_approved_amount_history
DROP TABLE IF EXISTS retail_banking_dm.dwd_loan_approval_event;
-- table_id: 136bd29d-a2f7-4121-b6ad-fc7b4dd7ee6f
CREATE TABLE IF NOT EXISTS retail_banking_dm.dwd_loan_approval_event (
    -- column_id: b8725e5e-4826-450c-9b30-e872d5b4c440
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: 4c9de254-83cf-4529-a5d1-a6765000b367
    `loan_id` BIGINT NOT NULL COMMENT 'Fineract source column loan_id',
    -- column_id: d650795b-fc8c-4a7f-b529-0740f5e05607
    `new_approved_amount` DECIMAL(19,6) NOT NULL COMMENT 'Fineract source column new_approved_amount',
    -- column_id: ec440387-13d0-455e-b4d8-d860151c14cf
    `old_approved_amount` DECIMAL(19,6) NOT NULL COMMENT 'Fineract source column old_approved_amount',
    -- column_id: fe656a55-ab47-4112-8dc6-316ce320b08f
    `created_by` BIGINT NULL COMMENT 'Fineract source column created_by',
    -- column_id: b1c3b7c0-dd77-4ed8-9622-561407537d96
    `created_on_utc` DATETIME NULL COMMENT 'Fineract source column created_on_utc',
    -- column_id: 2eab2624-d443-4a35-b194-8ce7fb3788ac
    `last_modified_by` BIGINT NULL COMMENT 'Fineract source column last_modified_by',
    -- column_id: a7492908-0d21-4bd9-8128-027e7fd8cc7e
    `last_modified_on_utc` DATETIME NULL COMMENT 'Fineract source column last_modified_on_utc',
    -- column_id: b883ff09-56d2-44fd-b811-4fda32509029
    `business_date` DATE NULL COMMENT 'Standardized business date from the semantic spec',
    -- column_id: 0cb784c3-5d9e-4112-ab48-6d5d6e1e9613
    `etl_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
