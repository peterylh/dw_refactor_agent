-- ODS mirror of Apache Fineract m_client_attendance (客户与参与方)
DROP TABLE IF EXISTS retail_banking_dm.ods_fineract_m_client_attendance;
-- table_id: ad742dc8-5afa-418b-865c-6726c19325c7
CREATE TABLE IF NOT EXISTS retail_banking_dm.ods_fineract_m_client_attendance (
    -- column_id: 06f6f4f3-ac31-4bd0-91c7-d37534372ba8
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: 1d9f18d1-b57b-4e11-86f3-f8675449d0ea
    `client_id` BIGINT NOT NULL COMMENT 'Fineract source column client_id',
    -- column_id: f8a60d0a-b938-48cb-ba7f-df0dab707893
    `meeting_id` BIGINT NOT NULL COMMENT 'Fineract source column meeting_id',
    -- column_id: 08b81b8f-2bca-4e8a-a011-ae99fa461134
    `attendance_type_enum` SMALLINT NOT NULL COMMENT 'Fineract source column attendance_type_enum',
    -- column_id: d657b56f-bdbc-4b00-9d58-d3d7542d846b
    `load_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
