-- Deterministic smoke data for Fineract m_report_mailing_job_run_history
TRUNCATE TABLE retail_banking_dm.ods_fineract_m_report_mailing_job_run_history;

INSERT INTO retail_banking_dm.ods_fineract_m_report_mailing_job_run_history (
    `id`,
    `job_id`,
    `start_datetime`,
    `end_datetime`,
    `status`,
    `error_message`,
    `error_log`,
    `load_time`
) VALUES
    (
        1,
        1,
        '2025-01-15 09:00:00',
        '2025-01-15 09:00:00',
        'm_report_m',
        'm_report_mailing_job_run_history_error_message_1',
        'm_report_mailing_job_run_history_error_log_1',
        '2025-01-15 00:00:00'
    );
