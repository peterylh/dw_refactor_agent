-- Deterministic smoke data for Fineract scheduled_email_configuration
TRUNCATE TABLE retail_banking_dm.ods_fineract_scheduled_email_configuration;

INSERT INTO retail_banking_dm.ods_fineract_scheduled_email_configuration (
    `id`,
    `name`,
    `value`,
    `load_time`
) VALUES
    (
        1,
        'Synthetic scheduled_email_configuration 1',
        'scheduled_email_configuration_value_1',
        '2025-01-15 00:00:00'
    );
