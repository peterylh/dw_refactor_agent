-- Deterministic smoke data for Fineract job_run_history
TRUNCATE TABLE retail_banking_dm.ods_fineract_job_run_history;

INSERT INTO retail_banking_dm.ods_fineract_job_run_history (
    `id`,
    `job_id`,
    `version`,
    `start_time`,
    `end_time`,
    `status`,
    `error_message`,
    `trigger_type`,
    `error_log`,
    `load_time`
) VALUES
    (
        1,
        1,
        1,
        '2025-01-15 09:00:00',
        '2025-01-15 09:00:00',
        'job_run_hi',
        'job_run_history_error_message_1',
        'job_run_history_trigger_t',
        'job_run_history_error_log_1',
        '2025-01-15 00:00:00'
    );
