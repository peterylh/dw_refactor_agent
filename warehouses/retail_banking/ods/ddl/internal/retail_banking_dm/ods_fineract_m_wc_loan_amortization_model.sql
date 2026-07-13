-- ODS mirror of Apache Fineract m_wc_loan_amortization_model (营运资金贷款)
DROP TABLE IF EXISTS retail_banking_dm.ods_fineract_m_wc_loan_amortization_model;
-- table_id: d062a34a-7fd2-465e-8913-9782079a3faf
CREATE TABLE IF NOT EXISTS retail_banking_dm.ods_fineract_m_wc_loan_amortization_model (
    -- column_id: 81f676a8-8d8e-44e0-8ec6-6b21fb49b9f2
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: 35b6896a-568e-495e-b8d3-4fc97ed7953f
    `version` INT NOT NULL COMMENT 'Fineract source column version',
    -- column_id: aaff33f6-34b0-4fa7-85f8-ded5c4c10a30
    `loan_id` BIGINT NOT NULL COMMENT 'Fineract source column loan_id',
    -- column_id: 17574264-5f05-43ce-94b2-278660a80313
    `json_model` STRING NOT NULL COMMENT 'Fineract source column json_model',
    -- column_id: 673835e9-3010-45fc-a78d-99abba1f4982
    `business_date` DATE NOT NULL COMMENT 'Fineract source column business_date',
    -- column_id: e43f5b18-1404-42e5-8b85-fcde5eea359d
    `json_model_version` VARCHAR(10) NOT NULL COMMENT 'Fineract source column json_model_version',
    -- column_id: d774865e-e9a1-4ad5-977f-db076c09ca2d
    `last_modified_on_utc` DATETIME NOT NULL COMMENT 'Fineract source column last_modified_on_utc',
    -- column_id: b877b7b3-d3d1-4edf-a372-7e2f90e12b58
    `load_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
