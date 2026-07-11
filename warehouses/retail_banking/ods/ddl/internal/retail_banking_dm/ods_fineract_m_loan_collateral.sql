-- ODS mirror of Apache Fineract m_loan_collateral (贷款与信贷)
DROP TABLE IF EXISTS retail_banking_dm.ods_fineract_m_loan_collateral;
-- table_id: 72feeca6-37a2-4258-8195-67162e4e5290
CREATE TABLE IF NOT EXISTS retail_banking_dm.ods_fineract_m_loan_collateral (
    -- column_id: 6ecbf434-a82c-4f88-888a-c5462ada1bac
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: e5d99141-36bb-495b-80cf-6963dfe347e4
    `loan_id` BIGINT NOT NULL COMMENT 'Fineract source column loan_id',
    -- column_id: 6cfa0c49-1a36-4a8e-9025-34520d1a5301
    `type_cv_id` INT NOT NULL COMMENT 'Fineract source column type_cv_id',
    -- column_id: 0691ecdf-a25a-44a7-9bc0-5f46f66c9d56
    `value` DECIMAL(19,6) NULL COMMENT 'Fineract source column value',
    -- column_id: 8eacb4b9-3835-471b-af5d-225fa4a4fe0c
    `description` VARCHAR(500) NULL COMMENT 'Fineract source column description',
    -- column_id: 7781ae5b-d44f-41df-925a-3637e7b67fbc
    `load_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
