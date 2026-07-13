-- Deterministic smoke data for Fineract job
TRUNCATE TABLE retail_banking_dm.ods_fineract_job;

INSERT INTO retail_banking_dm.ods_fineract_job (
    `id`,
    `name`,
    `display_name`,
    `cron_expression`,
    `create_time`,
    `task_priority`,
    `group_name`,
    `previous_run_start_time`,
    `next_run_time`,
    `job_key`,
    `initializing_errorlog`,
    `is_active`,
    `currently_running`,
    `updates_allowed`,
    `scheduler_group`,
    `is_misfired`,
    `node_id`,
    `is_mismatched_job`,
    `short_name`,
    `load_time`
) VALUES
    (
        1,
        'Synthetic job 1',
        'Synthetic job 1',
        'job_cron_expression_',
        '2025-01-15 09:00:00',
        1,
        'job_group_name_1',
        '2025-01-15 09:00:00',
        '2025-01-15 09:00:00',
        'job_job_key_1',
        'job_initializing_errorlog_1',
        FALSE,
        FALSE,
        FALSE,
        1,
        FALSE,
        1,
        FALSE,
        'job_shor',
        '2025-01-15 00:00:00'
    );
