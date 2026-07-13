-- DWD generated from m_loan_charge_paid_by
DROP TABLE IF EXISTS retail_banking_dm.dwd_loan_charge_allocation;
-- table_id: b5c6e5f9-94c6-4f4d-a6e8-89787056e603
CREATE TABLE IF NOT EXISTS retail_banking_dm.dwd_loan_charge_allocation (
    -- column_id: af19430e-880e-4ced-ae66-ad2d4c58510f
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: 9635d961-4125-4ada-b9b5-7722bb4af664
    `loan_transaction_id` BIGINT NOT NULL COMMENT 'Fineract source column loan_transaction_id',
    -- column_id: 5fb14a50-862f-4690-b6b0-135e2c6405d0
    `loan_charge_id` BIGINT NOT NULL COMMENT 'Fineract source column loan_charge_id',
    -- column_id: 516f3658-9616-4fed-a0b8-d4ca77a0f918
    `amount` DECIMAL(19,6) NOT NULL COMMENT 'Fineract source column amount',
    -- column_id: 4e004d56-429b-42a5-b9c8-daf91b3e305d
    `installment_number` SMALLINT NULL COMMENT 'Fineract source column installment_number',
    -- column_id: bd946483-23c4-4489-925e-dc01e97870d1
    `business_date` DATE NULL COMMENT 'Standardized business date from the semantic spec',
    -- column_id: e94bcbf0-9525-4598-a9c8-ce6f66f84f91
    `etl_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
