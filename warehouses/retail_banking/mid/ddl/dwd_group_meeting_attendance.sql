SET allow_partition_column_nullable = true;

-- DWD generated from m_client_attendance
DROP TABLE IF EXISTS retail_banking_dm.dwd_group_meeting_attendance;
-- table_id: ff34871b-f81f-48d4-a836-94622936471e
CREATE TABLE IF NOT EXISTS retail_banking_dm.dwd_group_meeting_attendance (
    -- column_id: e762e186-0010-433b-a42b-dac27afd6d46
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: 9cf99156-7d24-4263-85c1-00fdc8748cf8
    `business_date` DATE NULL COMMENT 'Standardized business date from the semantic spec',
    -- column_id: b313347b-5f0c-4fec-8213-c7678271f32b
    `client_id` BIGINT NOT NULL COMMENT 'Fineract source column client_id',
    -- column_id: 78a08034-2fa4-424c-941e-6b3b1422cf83
    `meeting_id` BIGINT NOT NULL COMMENT 'Fineract source column meeting_id',
    -- column_id: a68671d9-b5e4-443d-a69f-8d7c460b64fb
    `attendance_type_enum` SMALLINT NOT NULL COMMENT 'Fineract source column attendance_type_enum',
    -- column_id: 9e3ed8c3-0d54-49b2-83c5-4b574ebb20d5
    `etl_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`, `business_date`)
AUTO PARTITION BY LIST (`business_date`) ()
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
