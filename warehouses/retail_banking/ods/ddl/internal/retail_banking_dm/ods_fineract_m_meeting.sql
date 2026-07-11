-- ODS mirror of Apache Fineract m_meeting (渠道与客户服务)
DROP TABLE IF EXISTS retail_banking_dm.ods_fineract_m_meeting;
-- table_id: c6d5b9c7-9e35-4688-9065-f32025e1423d
CREATE TABLE IF NOT EXISTS retail_banking_dm.ods_fineract_m_meeting (
    -- column_id: 014c22d8-a450-486b-9b7d-d39cf2a46c79
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: d5963f61-07e1-4db2-959f-13efa23f078d
    `calendar_instance_id` BIGINT NOT NULL COMMENT 'Fineract source column calendar_instance_id',
    -- column_id: 8f44fd78-9625-4ef5-9b13-82ce1c357b8f
    `meeting_date` DATE NOT NULL COMMENT 'Fineract source column meeting_date',
    -- column_id: f7aa2255-6747-49aa-a4c8-b73f93fadbea
    `load_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
