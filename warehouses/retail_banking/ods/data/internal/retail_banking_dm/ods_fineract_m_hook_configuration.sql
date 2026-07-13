-- Deterministic smoke data for Fineract m_hook_configuration
TRUNCATE TABLE retail_banking_dm.ods_fineract_m_hook_configuration;

INSERT INTO retail_banking_dm.ods_fineract_m_hook_configuration (
    `id`,
    `hook_id`,
    `field_type`,
    `field_name`,
    `field_value`,
    `load_time`
) VALUES
    (
        1,
        1,
        'm_hook_configuration_field_type_1',
        'm_hook_configuration_field_name_1',
        'm_hook_configuration_field_value_1',
        '2025-01-15 00:00:00'
    );
