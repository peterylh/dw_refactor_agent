-- Deterministic smoke data for Fineract m_batch_business_steps
TRUNCATE TABLE retail_banking_dm.ods_fineract_m_batch_business_steps;

INSERT INTO retail_banking_dm.ods_fineract_m_batch_business_steps (
    `id`,
    `job_name`,
    `step_name`,
    `step_order`,
    `load_time`
) VALUES
    (
        1,
        'm_batch_business_steps_job_name_1',
        'm_batch_business_steps_step_name_1',
        1,
        '2025-01-15 00:00:00'
    );
