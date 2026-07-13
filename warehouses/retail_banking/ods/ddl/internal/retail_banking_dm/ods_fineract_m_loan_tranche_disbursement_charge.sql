-- ODS mirror of Apache Fineract m_loan_tranche_disbursement_charge (贷款与信贷)
DROP TABLE IF EXISTS retail_banking_dm.ods_fineract_m_loan_tranche_disbursement_charge;
-- table_id: 75cea5fe-e10a-4ffa-8e68-82a1ce7d0c26
CREATE TABLE IF NOT EXISTS retail_banking_dm.ods_fineract_m_loan_tranche_disbursement_charge (
    -- column_id: 2a256025-f973-4c03-9197-7dd5f3de9a9c
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: 08da2175-0f4c-430c-8687-d418fc482f26
    `loan_charge_id` BIGINT NOT NULL COMMENT 'Fineract source column loan_charge_id',
    -- column_id: c02cd1bb-873b-410f-a528-51d87d85b371
    `disbursement_detail_id` BIGINT NULL COMMENT 'Fineract source column disbursement_detail_id',
    -- column_id: 5a888750-2602-480a-bd21-7da7013a395c
    `load_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
