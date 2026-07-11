-- ODS mirror of Apache Fineract m_share_account_dividend_details (投资、份额与资产持有)
DROP TABLE IF EXISTS retail_banking_dm.ods_fineract_m_share_account_dividend_details;
-- table_id: c22cfabc-7e66-44e1-8208-03a289cbcc22
CREATE TABLE IF NOT EXISTS retail_banking_dm.ods_fineract_m_share_account_dividend_details (
    -- column_id: 3e3c7a79-313f-495b-a73b-5f7f644f5bb2
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: e98d4278-580a-46a4-a4eb-ee64f9fad4bf
    `dividend_pay_out_id` BIGINT NOT NULL COMMENT 'Fineract source column dividend_pay_out_id',
    -- column_id: a52a606a-7af6-420a-99c2-f395904b8d10
    `account_id` BIGINT NOT NULL COMMENT 'Fineract source column account_id',
    -- column_id: 4607a4e3-484c-431f-9fcb-ea25c98cf370
    `amount` DECIMAL(19,6) NOT NULL COMMENT 'Fineract source column amount',
    -- column_id: 7afc140d-41b2-41b1-8a64-7948372f1e6d
    `status` SMALLINT NOT NULL COMMENT 'Fineract source column status',
    -- column_id: b72bf258-0f08-4206-8e62-04b849b96a2a
    `savings_transaction_id` BIGINT NULL COMMENT 'Fineract source column savings_transaction_id',
    -- column_id: 44f2c925-0934-47ef-806d-2b9615abe47d
    `load_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
