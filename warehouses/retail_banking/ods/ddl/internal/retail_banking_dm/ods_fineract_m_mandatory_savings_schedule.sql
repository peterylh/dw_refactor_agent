-- ODS mirror of Apache Fineract m_mandatory_savings_schedule (存款与储蓄)
DROP TABLE IF EXISTS retail_banking_dm.ods_fineract_m_mandatory_savings_schedule;
-- table_id: 1a6ae2fe-2384-4749-8836-64741d6f19af
CREATE TABLE IF NOT EXISTS retail_banking_dm.ods_fineract_m_mandatory_savings_schedule (
    -- column_id: 5d3cac82-13f5-4cbc-a164-85bc1e384733
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: 51a265dd-24fe-4b0c-aed1-8d106801fcd0
    `savings_account_id` BIGINT NOT NULL COMMENT 'Fineract source column savings_account_id',
    -- column_id: 65b0e449-85a9-4693-9680-c28c72186012
    `fromdate` DATE NULL COMMENT 'Fineract source column fromdate',
    -- column_id: 91871123-2b40-45eb-987a-baad4cce0f18
    `duedate` DATE NOT NULL COMMENT 'Fineract source column duedate',
    -- column_id: 10f7b665-803a-433c-927e-cdf81a6faf50
    `installment` SMALLINT NOT NULL COMMENT 'Fineract source column installment',
    -- column_id: fa59c2a7-4ac3-4824-a3fe-cffccd5f670b
    `deposit_amount` DECIMAL(19,6) NULL COMMENT 'Fineract source column deposit_amount',
    -- column_id: 9088e761-311a-4a97-973c-87fd1196373f
    `deposit_amount_completed_derived` DECIMAL(19,6) NULL COMMENT 'Fineract source column deposit_amount_completed_derived',
    -- column_id: f5f9cb79-9ee8-4eb2-a53c-f2c03e15fa27
    `total_paid_in_advance_derived` DECIMAL(19,6) NULL COMMENT 'Fineract source column total_paid_in_advance_derived',
    -- column_id: 580b54cd-6f72-48e7-b470-6a36148192fb
    `total_paid_late_derived` DECIMAL(19,6) NULL COMMENT 'Fineract source column total_paid_late_derived',
    -- column_id: 82a0ea1f-4d16-453b-8887-dac90cb67847
    `completed_derived` BOOLEAN NOT NULL COMMENT 'Fineract source column completed_derived',
    -- column_id: d9c5e718-7dd6-4a2f-8416-e5a51f09faf2
    `obligations_met_on_date` DATE NULL COMMENT 'Fineract source column obligations_met_on_date',
    -- column_id: a656f102-9a5e-42f0-8515-70306eda1e8f
    `created_by` BIGINT NOT NULL COMMENT 'Fineract source column created_by',
    -- column_id: 4839b196-8289-4a9e-95c7-048abd52e16c
    `created_date` DATETIME NULL COMMENT 'Fineract source column created_date',
    -- column_id: c618ee6b-1ef4-4133-806f-a76e9606bd62
    `lastmodified_date` DATETIME NULL COMMENT 'Fineract source column lastmodified_date',
    -- column_id: 021ca1fd-661c-40c6-8ac5-110dd38c85c8
    `last_modified_by` BIGINT NOT NULL COMMENT 'Fineract source column last_modified_by',
    -- column_id: f4a848b1-6283-4ad0-9efc-265b88544b1d
    `created_on_utc` DATETIME NOT NULL COMMENT 'Fineract source column created_on_utc',
    -- column_id: 19d749b9-5aa6-4744-9f16-9859e11174f7
    `last_modified_on_utc` DATETIME NOT NULL COMMENT 'Fineract source column last_modified_on_utc',
    -- column_id: 3391fa4b-1a82-4e4b-b8e2-63ab3d4d2b20
    `load_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
