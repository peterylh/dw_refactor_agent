-- Deterministic smoke data for Fineract c_configuration
TRUNCATE TABLE retail_banking_dm.ods_fineract_c_configuration;

INSERT INTO retail_banking_dm.ods_fineract_c_configuration (
    `id`,
    `name`,
    `value`,
    `date_value`,
    `string_value`,
    `enabled`,
    `is_trap_door`,
    `description`,
    `load_time`
) VALUES
    (
        1,
        'Synthetic c_configuration 1',
        1,
        '2025-01-15',
        'c_configuration_string_value_1',
        FALSE,
        FALSE,
        'c_configuration_description_1',
        '2025-01-15 00:00:00'
    );
