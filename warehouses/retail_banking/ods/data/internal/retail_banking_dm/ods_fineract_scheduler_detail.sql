-- Deterministic smoke data for Fineract scheduler_detail
TRUNCATE TABLE retail_banking_dm.ods_fineract_scheduler_detail;

INSERT INTO retail_banking_dm.ods_fineract_scheduler_detail (
    `id`,
    `is_suspended`,
    `execute_misfired_jobs`,
    `reset_scheduler_on_bootup`,
    `load_time`
) VALUES
    (
        1,
        FALSE,
        FALSE,
        FALSE,
        '2025-01-15 00:00:00'
    );
