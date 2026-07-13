-- ODS mirror of Apache Fineract m_report_mailing_job_run_history (公共参考与元数据)
DROP TABLE IF EXISTS retail_banking_dm.ods_fineract_m_report_mailing_job_run_history;
-- table_id: 86d765f4-1c9e-4c22-8bfe-e04468f108b3
CREATE TABLE IF NOT EXISTS retail_banking_dm.ods_fineract_m_report_mailing_job_run_history (
    -- column_id: 4735d534-02f8-4ec7-bc1c-12e2bc485420
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: 6aff86b2-6d38-4791-9b85-82233902f3a2
    `job_id` BIGINT NOT NULL COMMENT 'Fineract source column job_id',
    -- column_id: c210b14c-1f81-45d7-863f-8e06fc73eb3f
    `start_datetime` DATETIME NOT NULL COMMENT 'Fineract source column start_datetime',
    -- column_id: 316add4e-74c8-4ce2-8252-03d6bee6d737
    `end_datetime` DATETIME NOT NULL COMMENT 'Fineract source column end_datetime',
    -- column_id: aef2f301-4325-49f1-b850-10e3660d020d
    `status` VARCHAR(10) NOT NULL COMMENT 'Fineract source column status',
    -- column_id: aaf420a5-b882-4e0e-aa47-dfe66c843ec7
    `error_message` STRING NULL COMMENT 'Fineract source column error_message',
    -- column_id: bfc8ec1e-dbcb-4b8b-a743-b6dea45c7ffd
    `error_log` STRING NULL COMMENT 'Fineract source column error_log',
    -- column_id: 9e46521d-e9a4-4320-a1e4-662a06dffa87
    `load_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
