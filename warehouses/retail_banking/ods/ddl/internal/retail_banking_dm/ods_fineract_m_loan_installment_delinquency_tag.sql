-- ODS mirror of Apache Fineract m_loan_installment_delinquency_tag (贷款与信贷)
DROP TABLE IF EXISTS retail_banking_dm.ods_fineract_m_loan_installment_delinquency_tag;
-- table_id: 8aff4337-fd2b-439d-a65f-ea78bae9a44b
CREATE TABLE IF NOT EXISTS retail_banking_dm.ods_fineract_m_loan_installment_delinquency_tag (
    -- column_id: 59a08db4-369a-46d4-a4a0-c12b78f52960
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: 7ddf071a-3780-4702-8dd7-5ebaccbe73a9
    `delinquency_range_id` BIGINT NOT NULL COMMENT 'Fineract source column delinquency_range_id',
    -- column_id: 8f2b45a2-fe03-4c5b-afd0-8a24513a5b7d
    `loan_id` BIGINT NOT NULL COMMENT 'Fineract source column loan_id',
    -- column_id: a4815415-f5c6-4d5f-8321-505f96e2c997
    `installment_id` BIGINT NOT NULL COMMENT 'Fineract source column installment_id',
    -- column_id: ffa10f51-f683-4be5-a0ea-e00b95a6479b
    `addedon_date` DATE NOT NULL COMMENT 'Fineract source column addedon_date',
    -- column_id: a1ae183c-77e4-4548-955c-f04e597569a2
    `first_overdue_date` DATE NOT NULL COMMENT 'Fineract source column first_overdue_date',
    -- column_id: 99b9f420-88d7-4fbc-a736-c83bfc6b8cfe
    `outstanding_amount` DECIMAL(19,6) NOT NULL COMMENT 'Fineract source column outstanding_amount',
    -- column_id: 0189b1b6-66c8-46d0-bab4-90a4f8ba78cb
    `liftedon_date` DATE NULL COMMENT 'Fineract source column liftedon_date',
    -- column_id: 312f1715-253f-4f9b-8b52-9a6cc53eb41a
    `created_by` BIGINT NOT NULL COMMENT 'Fineract source column created_by',
    -- column_id: f6d7af1b-9731-4016-8f41-dea870831da7
    `version` BIGINT NOT NULL COMMENT 'Fineract source column version',
    -- column_id: 042ca8a3-5630-4fe8-ad5a-fafbba47b3d9
    `last_modified_by` BIGINT NOT NULL COMMENT 'Fineract source column last_modified_by',
    -- column_id: 1d1589ee-e01b-4560-9238-8f60438e0c00
    `created_on_utc` DATETIME NOT NULL COMMENT 'Fineract source column created_on_utc',
    -- column_id: 6d944f52-883c-4b95-a681-afd8e1919133
    `last_modified_on_utc` DATETIME NOT NULL COMMENT 'Fineract source column last_modified_on_utc',
    -- column_id: 06cae9f8-1069-4b09-9a9b-97f18ca58c0b
    `load_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
