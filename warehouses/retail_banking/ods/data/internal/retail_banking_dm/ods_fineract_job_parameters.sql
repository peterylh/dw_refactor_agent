-- Deterministic smoke data for Fineract job_parameters
TRUNCATE TABLE retail_banking_dm.ods_fineract_job_parameters;

INSERT INTO retail_banking_dm.ods_fineract_job_parameters (
    `id`,
    `job_id`,
    `parameter_name`,
    `parameter_value`,
    `load_time`
) VALUES
    (
        1,
        1,
        'job_parameters_parameter_name_1',
        'job_parameters_parameter_value_1',
        '2025-01-15 00:00:00'
    );
