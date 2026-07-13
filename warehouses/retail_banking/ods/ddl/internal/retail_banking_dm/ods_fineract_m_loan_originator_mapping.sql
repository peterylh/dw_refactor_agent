-- ODS mirror of Apache Fineract m_loan_originator_mapping (贷款与信贷)
DROP TABLE IF EXISTS retail_banking_dm.ods_fineract_m_loan_originator_mapping;
-- table_id: 82a84ca6-f5d8-445d-b07f-f8bfd30787a5
CREATE TABLE IF NOT EXISTS retail_banking_dm.ods_fineract_m_loan_originator_mapping (
    -- column_id: 82c19d03-6d56-44b1-90c8-6857e489a1f4
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: 833529a4-98a9-4d71-a8a3-c732f5e38f37
    `loan_id` BIGINT NOT NULL COMMENT 'Fineract source column loan_id',
    -- column_id: ce3d5fe5-0c5e-48f3-9904-a2cc3d7fea1a
    `originator_id` BIGINT NOT NULL COMMENT 'Fineract source column originator_id',
    -- column_id: b99ff547-dbaa-4f94-81e8-0c7bf6bc3acd
    `created_on_utc` DATETIME NOT NULL COMMENT 'Fineract source column created_on_utc',
    -- column_id: 36c01cdd-5575-49ca-815b-868bafd8f31e
    `created_by` BIGINT NOT NULL COMMENT 'Fineract source column created_by',
    -- column_id: a70d8797-161e-475d-b217-89e207a27bf3
    `last_modified_on_utc` DATETIME NOT NULL COMMENT 'Fineract source column last_modified_on_utc',
    -- column_id: 538ac88a-4f13-422d-a953-893e7611fa5d
    `last_modified_by` BIGINT NOT NULL COMMENT 'Fineract source column last_modified_by',
    -- column_id: 70449885-06ca-4038-87e0-a0cacf00b924
    `load_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
