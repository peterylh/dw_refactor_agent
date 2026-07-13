-- ODS mirror of Apache Fineract m_report_mailing_job (公共参考与元数据)
DROP TABLE IF EXISTS retail_banking_dm.ods_fineract_m_report_mailing_job;
-- table_id: d0e88bec-b076-41d0-a93a-b889e0e7b20e
CREATE TABLE IF NOT EXISTS retail_banking_dm.ods_fineract_m_report_mailing_job (
    -- column_id: 0d7286aa-4330-4bbd-9323-bf6529c08782
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: d4f5e11b-eade-4885-83f2-b481fc49dc59
    `name` VARCHAR(100) NOT NULL COMMENT 'Fineract source column name',
    -- column_id: 1474db9b-bcd6-4213-b577-fadc928f85c6
    `description` STRING NULL COMMENT 'Fineract source column description',
    -- column_id: 5eff535c-2250-4788-8ea2-83d50518305c
    `start_datetime` DATETIME NOT NULL COMMENT 'Fineract source column start_datetime',
    -- column_id: 3df566e8-cabf-4591-a2a4-25d02beeef51
    `recurrence` VARCHAR(100) NULL COMMENT 'Fineract source column recurrence',
    -- column_id: d6e03b48-7432-41a8-811d-1df59c58fd32
    `created_date` DATE NOT NULL COMMENT 'Fineract source column created_date',
    -- column_id: e3ed2f17-bef0-48d1-a3dd-583d3546588e
    `createdby_id` BIGINT NOT NULL COMMENT 'Fineract source column createdby_id',
    -- column_id: c2c908d5-42e8-45d8-8b6c-24336fa165e3
    `lastmodified_date` DATE NULL COMMENT 'Fineract source column lastmodified_date',
    -- column_id: 4d89012a-3a66-428c-bf12-eec579cbadaf
    `lastmodifiedby_id` BIGINT NULL COMMENT 'Fineract source column lastmodifiedby_id',
    -- column_id: 40ed8792-6b89-4520-93f1-5c0ed766bc72
    `email_recipients` STRING NOT NULL COMMENT 'Fineract source column email_recipients',
    -- column_id: 068b0749-5fbc-49f4-9ecd-cc19e37020fa
    `email_subject` VARCHAR(100) NOT NULL COMMENT 'Fineract source column email_subject',
    -- column_id: 97166343-8af4-4aa5-b824-6d4c0dd0888f
    `email_message` STRING NOT NULL COMMENT 'Fineract source column email_message',
    -- column_id: 38781593-4d73-438c-adda-b209b597834c
    `email_attachment_file_format` VARCHAR(10) NOT NULL COMMENT 'Fineract source column email_attachment_file_format',
    -- column_id: 55ae300b-dd8e-483c-b1c8-52dcf42ddca7
    `stretchy_report_id` INT NOT NULL COMMENT 'Fineract source column stretchy_report_id',
    -- column_id: e3b01316-7c14-4f7a-87c9-e83cb969fc7a
    `stretchy_report_param_map` STRING NULL COMMENT 'Fineract source column stretchy_report_param_map',
    -- column_id: c3a672e7-ce85-48c9-92b9-24e44d0c5e5b
    `previous_run_datetime` DATETIME NULL COMMENT 'Fineract source column previous_run_datetime',
    -- column_id: dbce428d-371d-4f9c-bfab-593c877f8ace
    `next_run_datetime` DATETIME NULL COMMENT 'Fineract source column next_run_datetime',
    -- column_id: a5ef5ae3-1aeb-4a40-befc-0ab78f0c702e
    `previous_run_status` VARCHAR(10) NULL COMMENT 'Fineract source column previous_run_status',
    -- column_id: f84904eb-6716-4c8e-945d-d37417dde0c3
    `previous_run_error_log` STRING NULL COMMENT 'Fineract source column previous_run_error_log',
    -- column_id: 5163ff10-36e7-40ee-b88d-dcf06adc8829
    `previous_run_error_message` STRING NULL COMMENT 'Fineract source column previous_run_error_message',
    -- column_id: 0221f2a0-08e6-482b-9a3e-a9aeac9c3f08
    `number_of_runs` INT NOT NULL COMMENT 'Fineract source column number_of_runs',
    -- column_id: 7c2a61ee-dcee-45ea-9fce-65aeea194a33
    `is_active` BOOLEAN NOT NULL COMMENT 'Fineract source column is_active',
    -- column_id: c75109d0-957e-4687-b816-bbee7b5c52f2
    `is_deleted` BOOLEAN NOT NULL COMMENT 'Fineract source column is_deleted',
    -- column_id: 4c3dd43c-07b1-466a-af5c-e53b22862535
    `run_as_userid` BIGINT NOT NULL COMMENT 'Fineract source column run_as_userid',
    -- column_id: ba3a6d19-0aac-4fe4-b497-5b09d3396e39
    `load_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
