-- DWD generated from m_wc_loan_balance
DROP TABLE IF EXISTS retail_banking_dm.dwd_wc_loan_balance_snapshot;
-- table_id: 2e8ec3ee-bd1e-4259-b306-4818405c10f8
CREATE TABLE IF NOT EXISTS retail_banking_dm.dwd_wc_loan_balance_snapshot (
    -- column_id: 12dd5cef-1d70-4019-a907-d34718d850f3
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: 9a8a44eb-41e6-47b5-b864-e7970c31a058
    `wc_loan_id` BIGINT NOT NULL COMMENT 'Fineract source column wc_loan_id',
    -- column_id: 2f0e377c-744a-494d-aa3f-624eeb185221
    `principal_paid` DECIMAL(19,6) NOT NULL COMMENT 'Fineract source column principal_paid',
    -- column_id: 4853369e-9a16-4f5f-9b74-5a10cdd3b163
    `realized_income_from_discount_fee` DECIMAL(19,6) NOT NULL COMMENT 'Fineract source column realized_income_from_discount_fee',
    -- column_id: 755bedc2-b030-4b7f-92fa-7f9dccd7a641
    `version` INT NOT NULL COMMENT 'Fineract source column version',
    -- column_id: e313bed3-8855-4e53-ab84-609685c60e08
    `created_by` BIGINT NOT NULL COMMENT 'Fineract source column created_by',
    -- column_id: 1e383ddc-18dc-480f-bbcc-5a21a361109b
    `last_modified_by` BIGINT NOT NULL COMMENT 'Fineract source column last_modified_by',
    -- column_id: 00301970-fa43-4dfe-8b69-9186ad9d4cbd
    `created_on_utc` DATETIME NOT NULL COMMENT 'Fineract source column created_on_utc',
    -- column_id: 8c0379c6-97b2-4ba9-b302-529642af5982
    `last_modified_on_utc` DATETIME NOT NULL COMMENT 'Fineract source column last_modified_on_utc',
    -- column_id: 21b5ca9f-e1f1-4a42-98d2-c6570c9212b5
    `overpayment_amount` DECIMAL(19,6) NOT NULL COMMENT 'Fineract source column overpayment_amount',
    -- column_id: 713051dd-da8f-4f90-b857-74059056ba5a
    `principal` DECIMAL(19,6) NOT NULL COMMENT 'Fineract source column principal',
    -- column_id: 2832b48b-76bb-4615-a6a5-8cd2f5279a51
    `fee` DECIMAL(19,6) NOT NULL COMMENT 'Fineract source column fee',
    -- column_id: b8ed7be2-c2de-4c37-aaab-69cdd27433d4
    `fee_paid` DECIMAL(19,6) NOT NULL COMMENT 'Fineract source column fee_paid',
    -- column_id: eeb64c0d-bed6-4f9f-97d1-247b542f458f
    `penalty` DECIMAL(19,6) NOT NULL COMMENT 'Fineract source column penalty',
    -- column_id: 4caa8dd8-1fe5-4331-864d-df9676224dec
    `penalty_paid` DECIMAL(19,6) NOT NULL COMMENT 'Fineract source column penalty_paid',
    -- column_id: b550cb58-721c-4109-90bb-19bbe5eec00d
    `total_disbursement` DECIMAL(19,6) NOT NULL COMMENT 'Fineract source column total_disbursement',
    -- column_id: 4da15fc1-bedf-4d97-9249-b31b14d3e4c2
    `total_discount_fee` DECIMAL(19,6) NOT NULL COMMENT 'Fineract source column total_discount_fee',
    -- column_id: fb7b0701-ea6e-4cff-8c9c-548acfb16227
    `total_discount_fee_adjustment` DECIMAL(19,6) NOT NULL COMMENT 'Fineract source column total_discount_fee_adjustment',
    -- column_id: 56e1a5fc-0b9d-402c-843f-08dbd5f347d4
    `snapshot_date` DATE NULL COMMENT 'Standardized business date from the semantic spec',
    -- column_id: d696d983-6f20-459d-93d1-cdee44b1404e
    `etl_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
