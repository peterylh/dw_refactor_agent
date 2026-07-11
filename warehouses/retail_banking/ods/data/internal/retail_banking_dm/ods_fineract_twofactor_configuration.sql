-- Deterministic smoke data for Fineract twofactor_configuration
TRUNCATE TABLE retail_banking_dm.ods_fineract_twofactor_configuration;

INSERT INTO retail_banking_dm.ods_fineract_twofactor_configuration (
    `id`,
    `name`,
    `value`,
    `load_time`
) VALUES
    (
        1,
        'Synthetic twofactor_configuration 1',
        'twofactor_configuration_value_1',
        '2025-01-15 00:00:00'
    );
