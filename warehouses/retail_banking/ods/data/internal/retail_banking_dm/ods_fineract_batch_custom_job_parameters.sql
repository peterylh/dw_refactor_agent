-- Deterministic smoke data for Fineract batch_custom_job_parameters
TRUNCATE TABLE retail_banking_dm.ods_fineract_batch_custom_job_parameters;

INSERT INTO retail_banking_dm.ods_fineract_batch_custom_job_parameters (
    `id`,
    `parameter_json`,
    `load_time`
) VALUES
    (
        1,
        '{}',
        '2025-01-15 00:00:00'
    );
